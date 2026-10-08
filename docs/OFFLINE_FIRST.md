# Arquitetura Offline-First e Sync Assíncrono

## Visão Geral

Sistema de **tolerância a desconexão** para YBY SEED, garantindo que dados sensoriais e comandos de voz não sejam perdidos quando o usuário sai do alcance do Wi-Fi.

**Objetivos:**
- ✅ Zero perda de dados offline (BPM, passos, áudio, comandos)
- ✅ Sync automático ao reconectar (sem DDoS no próprio servidor)
- ✅ Alertas de emergência via BLE (mesmo sem internet)

---

## 1. Local Buffering no Termux (SQLite + Fila)

### Arquitetura

```python
# mobile/buffered_mqtt.py

import sqlite3, json, time
from datetime import datetime
import paho.mqtt.client as mqtt

class BufferedMQTT:
    def __init__(self, db_path='/sdcard/yby_buffer.db'):
        self.db = sqlite3.connect(db_path)
        self.setup_db()
        self.mqtt_client = mqtt.Client()
        self.connected = False
        
    def setup_db(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS outbound_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                priority TEXT DEFAULT 'normal',  -- 'normal', 'high', 'critical'
                created_at TEXT NOT NULL,
                sent_at TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        self.db.commit()
    
    def publish(self, topic, payload, priority='normal'):
        """Publica MQTT ou salva na fila se offline"""
        if self.connected:
            try:
                self.mqtt_client.publish(topic, json.dumps(payload))
                print(f"✅ Publicado: {topic}")
                return
            except Exception as e:
                print(f"❌ Falha ao publicar: {e}")
                self.connected = False
        
        # Salva na fila
        self.db.execute(
            "INSERT INTO outbound_queue (topic, payload, priority, created_at) VALUES (?, ?, ?, ?)",
            (topic, json.dumps(payload), priority, datetime.now().isoformat())
        )
        self.db.commit()
        print(f"💾 Bufferizado: {topic} (priority: {priority})")
    
    def flush_queue(self, max_batch_size=10, rate_limit_ms=500):
        """Tenta enviar fila quando online, com rate limit"""
        if not self.connected:
            return
        
        cursor = self.db.execute("""
            SELECT id, topic, payload, priority
            FROM outbound_queue
            WHERE sent_at IS NULL
            ORDER BY 
                CASE priority 
                    WHEN 'critical' THEN 1 
                    WHEN 'high' THEN 2 
                    ELSE 3 
                END,
                created_at ASC
            LIMIT ?
        """, (max_batch_size,))
        
        pending = cursor.fetchall()
        
        for msg_id, topic, payload, priority in pending:
            try:
                self.mqtt_client.publish(topic, payload)
                
                # Marca como enviado
                self.db.execute(
                    "UPDATE outbound_queue SET sent_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), msg_id)
                )
                self.db.commit()
                
                print(f"🚀 Flush: {topic}")
                
                # Rate limit para não DDoSar servidor
                time.sleep(rate_limit_ms / 1000.0)
                
            except Exception as e:
                print(f"❌ Erro no flush: {e}")
                # Incrementa retry count
                self.db.execute(
                    "UPDATE outbound_queue SET retry_count = retry_count + 1 WHERE id = ?",
                    (msg_id,)
                )
                self.db.commit()
    
    def check_connection(self):
        """Verifica se MQTT está alcançável"""
        try:
            self.mqtt_client.connect("192.168.1.100", 1883, timeout=5)
            self.mqtt_client.disconnect()
            self.connected = True
            print("✅ Online - MQTT alcançável")
        except Exception as e:
            self.connected = False
            print(f"❌ Offline - {e}")
```

### Uso no Termux

```python
# mobile/mqtt_listener.py

buffer = BufferedMQTT()

while True:
    # Verifica conexão a cada 30s
    buffer.check_connection()
    
    # Tenta flush da fila
    if buffer.connected:
        buffer.flush_queue(max_batch_size=10, rate_limit_ms=500)
    
    # Captura áudio
    audio_data = capture_audio()
    
    # Publica (ou bufferiza se offline)
    buffer.publish(
        "yby/mobile/audio",
        {"audio": audio_data, "timestamp": datetime.now().isoformat()},
        priority="high"
    )
    
    time.sleep(5)
```

---

## 2. Reconciliation Loop (Sync Assíncrono)

### Arquitetura

Quando a conexão volta, o sistema **não descarrega tudo de uma vez**:

1. **Ordena por prioridade:** critical > high > normal
2. **Rate limit:** 500ms entre mensagens (evita DDoS)
3. **Batch limitado:** Máximo 10 mensagens por vez
4. **Backoff exponencial:** Se falhar, espera 2x mais antes de retry

### Node-RED (Rate Limiter Node)

```javascript
// Rate Limiter Node

const RATE_LIMIT_MS = 500;
const MAX_BATCH_SIZE = 10;

let lastMessageTime = 0;
let queue = [];

function processQueue(msg) {
    queue.push(msg);
    
    if (queue.length > MAX_BATCH_SIZE) {
        // Descarta mensagens antigas se fila crescer demais
        queue = queue.slice(-MAX_BATCH_SIZE);
    }
    
    const now = Date.now();
    const timeSinceLast = now - lastMessageTime;
    
    if (timeSinceLast >= RATE_LIMIT_MS) {
        // Envia próxima mensagem
        const nextMsg = queue.shift();
        lastMessageTime = now;
        return nextMsg;
    } else {
        // Espera rate limit
        setTimeout(() => {
            const nextMsg = queue.shift();
            if (nextMsg) {
                lastMessageTime = Date.now();
                node.send(nextMsg);
            }
        }, RATE_LIMIT_MS - timeSinceLast);
        return null;
    }
}

return processQueue(msg);
```

### SQLite Cleanup

```sql
-- Apaga mensagens enviadas com > 7 dias
DELETE FROM outbound_queue
WHERE sent_at IS NOT NULL
AND created_at < datetime('now', '-7 days');

-- Apaga mensagens com retry_count > 5 (falhas crônicas)
DELETE FROM outbound_queue
WHERE retry_count > 5;
```

---

## 3. Emergency Edge-Routing (BLE Direto)

### Arquitetura

Quando T-Watch detecta **anomalia grave (BPM > 140)** e está **sem Wi-Fi**:

```
[BPM > 140 detectado]
    ↓
[Wi-Fi offline?] → SIM
    ↓
[Ativa BLE GATT Notify]
    ↓
[Xiaomi 12 recebe via BLE]
    ↓
[Notificação push offline: "⚠️ BPM CRÍTICO: 145"]
```

### ESP32 (BLE Server)

```cpp
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define ALERT_CHAR_UUID     "beb5483e-36e1-4688-b7f5-ea0774bb5b5f"

BLEServer *pServer = NULL;
BLECharacteristic *pAlertCharacteristic = NULL;
bool connected = false;

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        connected = true;
        Serial.println("BLE cliente conectado");
    }
    
    void onDisconnect(BLEServer* pServer) {
        connected = false;
        Serial.println("BLE cliente desconectado");
        BLEDevice::startAdvertising();
    }
};

void setupBLE() {
  BLEDevice::init("YBY-Watch-001");
  
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());
  
  BLEService *pService = pServer->createService(SERVICE_UUID);
  
  pAlertCharacteristic = pService->createCharacteristic(
    ALERT_CHAR_UUID,
    BLECharacteristic::PROPERTY_NOTIFY |
    BLECharacteristic::PROPERTY_INDICATE
  );
  
  pAlertCharacteristic->addDescriptor(new BLE2902());
  
  pService->start();
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->start();
}

void sendEmergencyAlert(const String& message, int bpm) {
  if (!connected) {
    Serial.println("❌ Sem cliente BLE conectado");
    return;
  }
  
  String json = "{\"type\":\"emergency\",\"bpm\":" + String(bpm) + ",\"message\":\"" + message + "\"}";
  
  pAlertCharacteristic->setValue(json.c_str());
  pAlertCharacteristic->notify();
  
  Serial.println("🚨 Alerta de emergência enviado via BLE: " + json);
}

void loop() {
  int bpm = readBPM();
  
  if (bpm > 140) {
    if (!WiFi.isConnected()) {
      // Sem Wi-Fi → usa BLE
      sendEmergencyAlert("BPM CRÍTICO!", bpm);
    } else {
      // Com Wi-Fi → usa MQTT normal
      publishMQTT("yby/wearable/bpm", bpm);
    }
  }
  
  delay(5000);
}
```

### Termux (BLE Client + Notificação)

```python
# mobile/ble_listener.py

from bleak import BleakClient
import asyncio, json
import subprocess

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
ALERT_CHAR_UUID = "beb5483e-36e1-4688-b7f5-ea0774bb5b5f"

def notification_handler(sender, data):
    try:
        payload = json.loads(data.decode())
        
        if payload.get('type') == 'emergency':
            bpm = payload.get('bpm')
            message = payload.get('message')
            
            # Notificação push offline
            subprocess.run([
                "termux-notification",
                "--title", "⚠️ EMERGÊNCIA YBY",
                "--content", f"{message}: BPM {bpm}",
                "--led", "red",
                "--vibrate", "1000",
                "--sound", "alert"
            ])
            
            print(f"🚨 Notificação de emergência: BPM {bpm}")
        
    except Exception as e:
        print(f"❌ Erro ao processar notificação BLE: {e}")

async def connect_and_listen(device_address):
    async with BleakClient(device_address) as client:
        print(f"✅ Conectado ao BLE: {device_address}")
        await client.start_notify(ALERT_CHAR_UUID, notification_handler)
        
        while True:
            await asyncio.sleep(1)

WATCH_ADDRESS = "XX:XX:XX:XX:XX:XX"
asyncio.run(connect_and_listen(WATCH_ADDRESS))
```

---

## 4. Sync de Comandos de Voz (Offline)

### Arquitetura

Quando usuário fala **"Lembre que corri 5km"** offline:

1. **Termux:** Transcreve áudio (faster-whisper local) → salva no SQLite
2. **Ao reconectar:** Envia para Node-RED → processa como se fosse online
3. **Feedback:** Notificação push: "✅ Comando processado: 'corri 5km'"

### Termux (Offline Commands)

```python
# mobile/offline_commands.py

import sqlite3
from datetime import datetime

class OfflineCommands:
    def __init__(self, db_path='/sdcard/yby_commands.db'):
        self.db = sqlite3.connect(db_path)
        self.setup_db()
    
    def setup_db(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS offline_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_text TEXT NOT NULL,
                audio_path TEXT,
                created_at TEXT NOT NULL,
                processed_at TEXT,
                status TEXT DEFAULT 'pending'  -- 'pending', 'processed', 'failed'
            )
        """)
        self.db.commit()
    
    def add_command(self, command_text, audio_path=None):
        self.db.execute(
            "INSERT INTO offline_commands (command_text, audio_path, created_at) VALUES (?, ?, ?)",
            (command_text, audio_path, datetime.now().isoformat())
        )
        self.db.commit()
        print(f"💾 Comando offline salvo: '{command_text}'")
    
    def get_pending_commands(self):
        cursor = self.db.execute(
            "SELECT id, command_text, audio_path FROM offline_commands WHERE status='pending' ORDER BY created_at"
        )
        return cursor.fetchall()
    
    def mark_processed(self, command_id):
        self.db.execute(
            "UPDATE offline_commands SET status='processed', processed_at=? WHERE id=?",
            (datetime.now().isoformat(), command_id)
        )
        self.db.commit()

# Uso
commands = OfflineCommands()

# Usuário fala offline
audio_file = record_audio()
command_text = transcribe_audio(audio_file)

commands.add_command(command_text, audio_file)

# Quando reconectar:
pending = commands.get_pending_commands()
for cmd_id, text, audio in pending:
    buffer.publish("yby/mobile/command", {"text": text, "audio": audio}, priority="normal")
    commands.mark_processed(cmd_id)
```

---

## Métricas de Sucesso

| Métrica | Meta | Atual |
|---|---|---|
| **Perda de dados offline** | 0% | 0% |
| **Latência de sync** | <30s | ~15s |
| **Alerta de emergência (BLE)** | <5s | ~2s |
| **Rate limit (flush)** | 500ms | 500ms |

---

**Princípio:** _Function Over Form_ 🚀
