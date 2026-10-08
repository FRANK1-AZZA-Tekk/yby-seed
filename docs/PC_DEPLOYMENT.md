# Deploy no PC Desktop (MVP YBY SEED)

## Visão Geral

Este guia foca **exclusivamente no PC Desktop** como núcleo de inferência do YBY SEED. Wearable e mobile serão adicionados depois.

**Hardware:** Ryzen 5 4600G, 16GB RAM, GTX 1650 4GB, Ubuntu 26.04

---

## 1. Instalação Base

### 1.1. Docker + Docker Compose

```bash
# Atualiza sistema
sudo apt update && sudo apt upgrade -y

# Instala Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Adiciona usuário ao grupo Docker
sudo usermod -aG docker $USER
newgrp docker

# Instala Docker Compose
sudo apt install docker-compose-plugin -y

# Verifica instalação
docker --version
docker compose version
```

### 1.2. NVIDIA Container Toolkit (GPU no Docker)

```bash
# Adiciona repositório NVIDIA
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit.gpg
echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit.gpg] https://nvidia.github.io/libnvidia-container/stable/deb $(lsb_release -cs) contrib" | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Instala toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configura Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Testa GPU no Docker
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### 1.3. Ollama (LLM Local)

```bash
# Instala Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Baixa modelos otimizados para GTX 1650
ollama pull llama3.2:3b-instruct-q4_K_M
ollama pull qwen2.5-coder:3b-instruct-q4_K_M

# Testa modelos
ollama run llama3.2:3b-instruct-q4_K_M "Olá, YBY SEED!"
```

---

## 2. Configuração Otimizada para 4GB VRAM

### 2.1. Ollama com KV Cache Q8_0 + Flash Attention

```bash
# Cria arquivo de configuração
sudo nano /etc/ollama/config.json
```

**Conteúdo:**
```json
{
  "num_thread": 12,
  "num_gpu": 1,
  "main_gpu": 0,
  "low_vram": false,
  "f16_kv": false,
  "use_mmap": true,
  "use_mlock": false,
  "num_batch": 512,
  "num_ctx": 8192,
  "n_gpu_layers": 35
}
```

**Reinicia Ollama:**
```bash
sudo systemctl restart ollama
```

### 2.2. Teste de VRAM

```bash
# Monitora VRAM em tempo real
watch -n 1 nvidia-smi

# Em outro terminal, roda modelo
ollama run llama3.2:3b-instruct-q4_K_M "Teste de carga"

# Verifica se VRAM não excede 4GB
```

---

## 3. SQLite como Único Banco (Zero ChromaDB)

### 3.1. Schema Otimizado

```sql
-- /opt/yby/registry/yby_seeds.db

-- Tabela de comandos (com FTS5)
CREATE TABLE offline_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    processed_at TEXT,
    status TEXT DEFAULT 'pending'
);

-- FTS5 para busca full-text
CREATE VIRTUAL TABLE commands_fts USING fts5(
    command_text,
    content='offline_commands',
    content_rowid='id'
);

-- Tabela de memória consolidada (resumos diários)
CREATE TABLE memory_consolidated (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    summary TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de telemetria (dados quentes + frios)
CREATE TABLE telemetry_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    bpm INTEGER,
    steps INTEGER,
    timestamp TEXT NOT NULL
);

CREATE TABLE telemetry_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    avg_bpm REAL,
    max_bpm INTEGER,
    total_steps INTEGER
);

-- Índices
CREATE INDEX idx_commands_created ON offline_commands(created_at);
CREATE INDEX idx_telemetry_timestamp ON telemetry_raw(timestamp);
CREATE INDEX idx_telemetry_date ON telemetry_daily(date);
```

### 3.2. Scripts de Pruning Automático

```bash
# /etc/cron.daily/yby-seed-pruning

#!/usr/bin/env bash
set -e

DB_PATH="/opt/yby/registry/yby_seeds.db"

echo "[YBY Pruning] Iniciando..."

# Apaga comandos processados com > 30 dias
sqlite3 "$DB_PATH" <<EOF
DELETE FROM offline_commands 
WHERE processed_at IS NOT NULL 
AND processed_at < datetime('now', '-30 days');
VACUUM;
EOF

# Apaga telemetria raw com > 7 dias
sqlite3 "$DB_PATH" <<EOF
DELETE FROM telemetry_raw 
WHERE timestamp < datetime('now', '-7 days');
VACUUM;
EOF

# Apaga telemetria daily com > 90 dias
sqlite3 "$DB_PATH" <<EOF
DELETE FROM telemetry_daily 
WHERE date < date('now', '-90 days');
VACUUM;
EOF

echo "[YBY Pruning] Concluído!"
```

---

## 4. Node-RED + MQTT (Orquestração)

### 4.1. Docker Compose

```yaml
# docker-compose.yml

version: '3.8'

services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: yby-mosquitto
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/config:/mosquitto/config
    restart: unless-stopped

  node-red:
    image: nodered/node-red:latest
    container_name: yby-node-red
    ports:
      - "1880:1880"
    volumes:
      - ./node-red/data:/data
    environment:
      - TZ=America/Sao_Paulo
    restart: unless-stopped
    depends_on:
      - mosquitto

  ollama:
    image: ollama/ollama:latest
    container_name: yby-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
        limits:
          cpus: '8.0'
    environment:
      - OLLAMA_HOST=0.0.0.0
    restart: unless-stopped

volumes:
  ollama_data:
```

### 4.2. Inicia Serviços

```bash
# Cria diretórios
mkdir -p mosquitto/config node-red/data

# Inicia
docker compose up -d

# Verifica status
docker compose ps

# Logs
docker compose logs -f ollama
```

---

## 5. Teste de Carga (GTX 1650)

### 5.1. Script de Benchmark

```python
#!/usr/bin/env python
# tests/gpu_benchmark.py

import requests, time

def benchmark_model(model, prompt="Olá", max_tokens=256):
    url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.1,
            "num_ctx": 8192
        }
    }
    
    start = time.time()
    response = requests.post(url, json=payload)
    end = time.time()
    
    result = response.json()
    tokens = len(result.get("response", "").split())
    latency = end - start
    tps = tokens / latency
    
    print(f"Modelo: {model}")
    print(f"  Tokens: {tokens}")
    print(f"  Latência: {latency:.2f}s")
    print(f"  Tokens/s: {tps:.2f}")
    print()

if __name__ == "__main__":
    print("🧪 Benchmark GTX 1650 4GB\n")
    
    benchmark_model("llama3.2:3b-instruct-q4_K_M")
    benchmark_model("qwen2.5-coder:3b-instruct-q4_K_M")
    benchmark_model("qwen2.5-coder:7b-instruct-q4_K_M")
```

### 5.2. Executa

```bash
# Instala dependências
pip install requests

# Roda benchmark
python tests/gpu_benchmark.py
```

**Resultados Esperados:**
- Llama 3.2 3B: ~40-60 t/s
- Qwen2.5-Coder 3B: ~35-50 t/s
- Qwen2.5-Coder 7B: ~15-25 t/s (offloading)

---

## 6. Próximos Passos

1. ✅ PC Desktop configurado (Ollama, Docker, SQLite)
2. ⏳ Implementar NL2Code com Qwen2.5-Coder 3B
3. ⏳ Criar interface TUI (Textual) para monitoramento
4. ⏳ Adicionar wearable (LilyGO T-Watch)
5. ⏳ Adicionar mobile (Xiaomi 12 Termux)

---

**Princípio:** _Function Over Form_ 🚀
