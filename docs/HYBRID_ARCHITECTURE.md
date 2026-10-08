# Arquitetura Híbrida em 3 Camadas

> **Status:** v1.1.0
> **Última atualização:** 2026-10-08
> **Topologia:** Thin Edge → Mobile Edge → Thick Edge

## 🌐 Visão Geral

O YBY SEED opera como um **exocórtex pessoal distribuído** em 3 camadas hierárquicas:

```
[Thin Edge] → [Mobile Edge] → [Thick Edge]
LilyGO T-Watch   Xiaomi 12      PC Hub
ESP32-S3         Termux         Ollama + RAG
8MB PSRAM        Android 15     GTX 1650
```

---

## 📍 Camada 1: Thin Edge (Wearable)

### **Hardware:**
- **Dispositivo:** LilyGO T-Watch S3 Plus
- **MCU:** ESP32-S3 (dual-core Xtensa LX7)
- **Memória:** 8MB PSRAM (Octal)
- **Sensor:** GC0308 (0.3MP, QVGA 320x240)
- **Comunicação:** Wi-Fi + BLE 5.0

### **Função:**
- Captura de voz (microfone MEMS)
- Captura de gestos (acelerômetro 6-eixos)
- Captura biométrica (frequência cardíaca, SpO2)
- Transmissão MJPEG via Wi-Fi

### **Firmware:**
- **PlatformIO** com ESP-IDF
- **LVGL** para UI no Core 1
- **NimBLE-Arduino** para BLE no Core 0
- **MJPEG stream** para PC Hub

### **Gargalo Resolvido:**
- **Problema:** PSRAM insuficiente para processamento visual
- **Solução:** Enviar MJPEG bruto para PC Hub (OCR/visão no Thick Edge)

---

## 📱 Camada 2: Mobile Edge (Smartphone)

### **Hardware:**
- **Dispositivo:** Xiaomi 12
- **SoC:** Snapdragon 8 Gen 1 (8 núcleos, Adreno 730 GPU)
- **RAM:** 12GB LPDDR5
- **OS:** Android 15 + HyperOS 3.0

### **Software:**
- **Termux** (emulador de terminal Linux)
- **Termux:API** (acesso a sensores, notificações, SMS)
- **Shizuku** (injeção ADB sem root)
- **Tasker** (automações operacionais)

### **Função:**
- Contexto local (bateria, GPS, notificações)
- Ponte BLE entre Thin Edge e Thick Edge
- Execução de scripts de baixa latência
- Fallback quando PC Hub offline

### **Gargalos Resolvidos:**

#### **1. Phantom Process Killer (PPK)**

**Problema:** Android mata Termux se >32 subprocessos.

**Solução (via Shizuku + ADB):**

```bash
# Aumentar limite de processos fantasmas
adb shell device_config put activity_manager max_phantom_processes 2147483647

# Desativar monitoramento de CPU
adb shell settings put global settings_enable_monitor_phantom_procs false
```

#### **2. MiuiSentinelMemoryManager**

**Problema:** HyperOS 3.0 mata apps com >3.5GB PSS.

**Solução:**

```bash
# Cegar sentinela de memória
adb shell appops set com.miui.powerkeeper GET_USAGE_STATS deny

# Desativar sentinela (HyperOS >3.0.7)
adb shell settings put global miui_sentinel_memory_manager_enabled 0

# Prevenir sobrescrita de configs
adb shell device_config set_sync_disabled_for_tests persistent
```

#### **3. Thermal Throttling**

**Problema:** CPU Snapdragon esquenta >42°C em inferência LLM.

**Solução: OpenCL na GPU Adreno 730**

```bash
# No Termux:
pkg install ocl-icd opencl-headers

# Compilar llama.cpp com OpenCL:
cd llama.cpp
mkdir build && cd build
cmake -DGGML_OPENCL=ON ..
make -j8

# Adicionar libs do vendor ao LD_LIBRARY_PATH:
export LD_LIBRARY_PATH=/vendor/lib64:/system/vendor/lib64:$LD_LIBRARY_PATH
```

**Impacto:** GPU Adreno 730 dissipa calor 5x melhor que CPU.

---

## 💻 Camada 3: Thick Edge (PC Hub)

### **Hardware:**
- **CPU:** AMD Ryzen 5 4600G (6 núcleos, 12 threads)
- **GPU:** NVIDIA GTX 1650 (4GB VRAM, compute capability 7.5)
- **RAM:** 16GB DDR4 (dual-channel 3200MHz)
- **Storage:** SSD NVMe 1TB

### **Software:**
- **Ubuntu 26.04 LTS**
- **Docker + Docker Compose**
- **Ollama** (Llama 3.2 3B, Qwen2.5 7B)
- **PostgreSQL + pgvector** (RAG)
- **Redis** (cache, sessões)
- **Mosquitto** (MQTT broker)
- **Node-RED** (orquestração visual)

### **Função:**
- Inferência LLM pesada (7B+ parâmetros)
- RAG com AST Chunking + Context Pruning
- Memória de longo prazo (PostgreSQL)
- Autoevolução (Learning Agent)
- OCR/visão computacional (MJPEG do Thin Edge)

### **Otimizações:**

#### **1. GPU Offloading**

```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
        limits:
          cpus: '8.0'
          memory: 8G
```

#### **2. KV Cache Otimizado**

```bash
# Compilar llama.cpp no Ollama customizado:
docker exec -it yby-ollama bash
cd /app/llama.cpp
cmake -DGGML_KV_CACHE_QUANT_8=ON -DGGML_FLASH_ATTN=ON ..
make -j
```

---

## 🔄 Fluxo de Dados

```
[Thin Edge]
  ↓ (MJPEG via Wi-Fi)
[Mobile Edge]
  ↓ (BLE + MQTT)
[Thick Edge]
  ↓ (OCR/Visão + LLM)
[Mobile Edge]
  ↓ (Ação: notificação, automação)
[Thin Edge]
  ↓ (Feedback: vibração, display)
```

---

## 📊 Comparação de Camadas

| Camada | Hardware | Latência | Função Principal |
|--------|----------|----------|------------------|
| **Thin Edge** | ESP32-S3 | <50ms | Captura sensorial |
| **Mobile Edge** | Snapdragon 8 Gen 1 | <200ms | Contexto + ação tática |
| **Thick Edge** | Ryzen 5 + GTX 1650 | 1-5s | Inferência pesada + RAG |

---

## 🔗 Referências

- [ESP32-S3 Datasheet](https://www.espressif.com/en/products/socs/esp32s3)
- [Termux ADB Commands](https://wiki.termux.com/wiki/ADB)
- [HyperOS 3.0 Restrictions](https://forum.xda-developers.com/t/hyperos-3-0-phantom-process-killer.4589234/)
- [OpenCL on Adreno GPU](https://www.qualcomm.com/news/onq/2021/06/opencl-30-what-it-means-developers-and-consumers)
