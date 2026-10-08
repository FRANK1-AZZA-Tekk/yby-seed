"""
Firmware YBY SEED — LilyGO T-Watch S3 Plus (ESP32-S3)

Responsabilidade:
- Capturar telemetria (batimentos, SpO2, passos, bateria)
- Publicar via MQTT+TLS (MQTTS) no broker
- Entrar em Deep Sleep periódico (economia de energia)
- Reconectar automaticamente após wake-up

Arquitetura:
[Sensores] → [ESP32-S3] → [MQTTS] → [Broker] → [Gateway FastAPI]

Otimizações:
- Disconnect Wi-Fi antes de Deep Sleep (evitar brownout)
- Backoff exponencial em reconexões (evitar flood)
- Buffer em NVS se MQTT offline (garantir entrega)

Licença: MIT
"""

#include <Arduino.h>
#include <WiFi.h>
#include <MQTT.h>
#include <esp_system.h>
#include <esp_sleep.h>
#include <nvs_flash.h>

#include "config.h"
#include "sensors.h"
#include "mqtt_client.h"
#include "display.h"
#include "power.h"

// Estado global
static unsigned long last_publish_time = 0;
static int reconnect_attempts = 0;
static const int MAX_RECONNECT_ATTEMPTS = 5;

// Protótipos
void setupWiFi();
void setupMQTT();
void enterDeepSleep();
void publishTelemetry();


void setup() {
  // Inicializar serial (debug)
  Serial.begin(115200);
  Serial.println("\n🚀 YBY SEED Firmware v1.1.0");
  Serial.println("📦 LilyGO T-Watch S3 Plus (ESP32-S3)");
  
  // Inicializar NVS (Non-Volatile Storage)
  esp_err_t ret = nvs_flash_init();
  if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    Serial.println("⚠️  NVS corrompido, apagando...");
    ESP_ERROR_CHECK(nvs_flash_erase());
    ret = nvs_flash_init();
  }
  ESP_ERROR_CHECK(ret);
  Serial.println("✅ NVS inicializado");
  
  // Inicializar display
  display_init();
  display_show_logo();
  
  // Inicializar sensores
  sensors_init();
  
  // Inicializar Wi-Fi
  setupWiFi();
  
  // Inicializar MQTT
  setupMQTT();
  
  Serial.println("✅ Setup concluído");
}


void loop() {
  // Publicar telemetria a cada PUBLISH_INTERVAL (30s)
  if (millis() - last_publish_time >= PUBLISH_INTERVAL) {
    publishTelemetry();
    last_publish_time = millis();
    
    // Resetar contador de reconexão após publish bem-sucedido
    reconnect_attempts = 0;
  }
  
  // Manter loop MQTT
  mqttClient.loop();
  
  // Entrar em Deep Sleep após DEEP_SLEEP_TIMEOUT (5min)
  if (millis() > DEEP_SLEEP_TIMEOUT) {
    Serial.println("😴 Entrando em Deep Sleep...");
    enterDeepSleep();
  }
}


void setupWiFi() {
  Serial.print("📶 Conectando Wi-Fi...");
  
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  WiFi.setSleep(WIFI_PS_NONE);  // Desativar power save (menor latência)
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 10) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("✅ Wi-Fi conectado");
    Serial.print("🌐 IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("❌ Falha ao conectar Wi-Fi");
  }
}


void setupMQTT() {
  Serial.print("📡 Conectando MQTT...");
  
  mqttClient.begin(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  mqttClient.onMessage(messageHandler);
  
  // MQTT+TLS (habilitar em produção)
  #ifdef MQTT_SECURE
  mqttClient.setSecure(true);
  // mqttClient.setCACert(MQTT_CA_CERT);  // Certificado CA em produção
  #endif
  
  // Last Will Testament (LWT)
  mqttClient.setWill(MQTT_TOPIC_STATUS, "offline", true, 1);
  
  // Auto-reconnect com backoff exponencial
  mqttClient.setOptions(60, true, 1000 * (1 << reconnect_attempts));  // keepalive, clean_session, timeout
  
  while (!mqttClient.connect() && reconnect_attempts < MAX_RECONNECT_ATTEMPTS) {
    delay(1000 * (1 << reconnect_attempts));  // Backoff exponencial
    Serial.print(".");
    reconnect_attempts++;
  }
  
  if (mqttClient.connected()) {
    Serial.println("✅ MQTT conectado");
    
    // Assinar tópicos de comando
    mqttClient.subscribe(MQTT_TOPIC_COMMANDS);
    
    // Publicar status online
    mqttClient.publish(MQTT_TOPIC_STATUS, "online", true);
  } else {
    Serial.println("❌ Falha ao conectar MQTT");
  }
}


void messageHandler(String &topic, String &payload) {
  // Callback: mensagem MQTT recebida
  Serial.println("📨 MQTT mensagem recebida: " + topic);
  
  // Exemplo: comando para mudar intervalo de publish
  if (topic == MQTT_TOPIC_COMMANDS) {
    if (payload == "sleep_now") {
      Serial.println("😴 Comando recebido: entrar em sleep agora");
      enterDeepSleep();
    }
  }
}


void publishTelemetry() {
  Serial.println("📤 Publicando telemetria...");
  
  // Ler sensores
  int heart_rate = sensors_read_heart_rate();
  int spo2 = sensors_read_spo2();
  int battery = power_read_battery();
  int steps = sensors_read_steps();
  
  // Construir payload JSON
  String payload = "{";
  payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  payload += "\"timestamp\":\"" + String(millis()) + "\",";
  payload += "\"metrics\":{";
  payload += "\"heart_rate\":" + String(heart_rate) + ",";
  payload += "\"spo2\":" + String(spo2) + ",";
  payload += "\"battery\":" + String(battery) + ",";
  payload += "\"steps\":" + String(steps);
  payload += "}}";
  
  // Publicar
  if (mqttClient.publish(MQTT_TOPIC_TELEMETRY, payload)) {
    Serial.println("✅ Telemetria publicada");
    display_show_telemetry(heart_rate, spo2, battery);
  } else {
    Serial.println("❌ Falha ao publicar telemetria");
    
    // Buffer em NVS (fallback)
    nvs_store_telemetry(payload);
  }
}


void enterDeepSleep() {
  Serial.println("😴 Preparando Deep Sleep...");
  
  // 1. Desligar periféricos
  display_off();
  sensors_off();
  
  // 2. Disconnect Wi-Fi (evitar brownout)
  WiFi.disconnect(true);
  delay(100);
  
  // 3. Disconnect MQTT
  mqttClient.disconnect();
  
  // 4. Publicar status offline
  mqttClient.publish(MQTT_TOPIC_STATUS, "sleeping", true);
  delay(100);
  
  // 5. Configurar wake-up por timer
  esp_sleep_enable_timer_wakeup(DEEP_SLEEP_TIMEOUT * 1000);  // Converter para microseconds
  
  // 6. Power down RTC memory (opcional, economiza 0.5mA)
  esp_sleep_pd_config(RTC_SLOW_MEM_PD, RTC_SLEEP_PD_DEFAULT);
  
  // 7. Entrar em Deep Sleep
  Serial.println("😴 Deep Sleep iniciado...");
  esp_deep_sleep_start();
}
