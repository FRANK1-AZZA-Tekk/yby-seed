# Arquitetura do YBY SEED

## Visão Geral

O YBY SEED é a interface de **Natural Language Programming** do exocórtex YBY, permitindo que não-programadores criem automações através de comandos de voz ou texto.

## Componentes Principais

### 1. LLM Engine (Qwen2.5-Coder-3B-Instruct)

**Por que este modelo?**
- 84% no HumanEval (melhor que Llama 3.2 3B e DeepSeek-Coder-1.3B)
- Consome apenas 2.5GB VRAM (Q4_K_M) na GTX 1650
- ~40 tokens/segundo de inferência
- Especializado em geração de código Python

**Configuração Ollama:**
```yaml
# docker-compose.yml
ollama:
  image: ollama/ollama
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  volumes:
    - ollama_data:/root/.ollama
  environment:
    - OLLAMA_HOST=0.0.0.0
```

### 2. Gateway de Roteamento (LiteLLM Proxy)

**Função:** Unificar Ollama + Groq + OpenRouter atrás de uma API OpenAI-compatible.

**Configuração de fallback:**
```yaml
# litellm_config.yaml
model_list:
  - model_name: yby-default
    litellm_params:
      model: ollama_chat/qwen2.5-coder:3b-instruct-q4_K_M
      api_base: http://ollama:11434
      timeout: 3  # Fallback após 3s

  - model_name: yby-default
    litellm_params:
      model: groq/llama-3.1-8b-instant
      api_key: os.environ/GROQ_API_KEY

  - model_name: yby-default
    litellm_params:
      model: openrouter/meta-llama/llama-3.1-8b-instruct
      api_key: os.environ/OPENROUTER_API_KEY
```

### 3. Orquestrador (Node-RED)

**Função:** Roteamento MQTT → HTTP → MQTT, gerenciamento de fluxos de automação.

**Fluxo principal:**
```
MQTT In (yby/user/prompt)
    ↓
HTTP Request (Ollama/LiteLLM)
    ↓
Function Node (Security Linter)
    ↓
Exec Node (subprocess com resource limits)
    ↓
MQTT Out (yby/agent/response)
```

### 4. Registry SQLite

**Schema:**
```sql
CREATE TABLE seeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_triggered TIMESTAMP,
    trigger_count INTEGER DEFAULT 0,
    metadata JSON
);
```

**Função:** Persistir metadados de automações ativas para consulta pelo LLM.

### 5. Process Manager

**Função:** Gerenciar subprocessos Python persistentes (automações em loop).

**Arquitetura:**
```python
active_processes = {seed_id: subprocess.Popen}

# Monitora e reinicia se morrer
for seed_id, proc in active_processes.items():
    if proc.poll() is not None:
        restart_seed(seed_id)
```

## Fluxo de Dados

### Criar Automação
```
Usuário: "Crie um alerta se BPM > 120"
    ↓
Node-RED → Ollama (Qwen2.5-Coder)
    ↓
Código Python gerado:
    import paho.mqtt.client as mqtt
    def on_message_bpm(client, userdata, msg):
        bpm = json.loads(msg.payload)['bpm']
        if bpm > 120:
            client.publish('yby/mobile/alert', '{"message":"BPM elevado!"}')
    ↓
Security Linter → Valida
    ↓
SQLite INSERT → Registra seed
    ↓
Process Manager → Inicia subprocesso
    ↓
MQTT Publish → Confirmação
```

### Atualizar Automação
```
Usuário: "Mude o alerta para 140"
    ↓
Node-RED → Ollama → Novo código
    ↓
Process Manager → Mata subprocesso antigo
    ↓
SQLite UPDATE → Atualiza código + metadata
    ↓
Process Manager → Reinicia subprocesso
    ↓
MQTT Publish → Confirmação
```

## Segurança

### Sandbox de Execução

**Camada 1: Linter Estático**
```python
DANGEROUS_PATTERNS = [
    "os.system", "os.popen", "subprocess.call",
    "shutil.rmtree", "eval(", "exec(", "__import__"
]
```

**Camada 2: Limites de Recursos**
```python
resource.setrlimit(resource.RLIMIT_AS, (128*1024*1024, 128*1024*1024))  # 128MB RAM
resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))  # Timeout
```

**Camada 3: Usuário Não-Root**
- Scripts rodam como usuário `yby-executor` sem acesso a `/`, `/etc`, `/home`.

## Wearable (LilyGO T-Watch S3 Plus)

### Máquina de Estados
```
[Deep Sleep] --timer 5min ou botão--▶ [Wi-Fi On]
    ▲                                      │
    │                                      ▼
    │                               [Conectar MQTT]
    │                                      │
    │                                      ▼
    │                               [Publicar status]
    │                                      │
    │                                      ▼
    │                               [Verificar mensagens]
    │                                      │
    │                                      ▼
    └────────────────────────────── [Wi-Fi Off]
```

### Autonomia Estimada
- Deep Sleep (23h50min/dia): 0.02mA × 23.83h = 0.48mAh
- Wi-Fi On (10min/dia): 100mA × 0.17h = 17mAh
- **Total:** ~17.5mAh/dia → **28 dias** (teórico), 14-20h (prático com margem)

## Nó Móvel (Xiaomi 12 + Termux)

### Blindagem contra MIUI/HyperOS

**Camada 1: Termux:Boot**
```bash
mkdir -p ~/.termux/boot
echo "python mqtt_listener.py &" >> ~/.termux/boot/start.sh
```

**Camada 2: Wake Lock**
```bash
termux-wake-lock
termux-notification --id 1 --title "YBY Node" --ongoing true
```

**Camada 3: Supervisor**
```python
while True:
    if proc.poll() is not None:
        proc = subprocess.Popen(["python", "mqtt_listener.py"])
```

## Pipeline de Áudio

```
Xiaomi 12 (Termux)
    ↓
Silero VAD (detecta voz)
    ↓
ffmpeg (Opus 16kHz, 2-4KB/s)
    ↓
MQTT Publish (yby/mobile/audio)
    ↓
Ubuntu Server (faster-whisper CPU)
    ↓
Texto transcrito → MQTT (yby/mobile/transcription)
```

---

**Princípio:** _Function Over Form_ 🚀
