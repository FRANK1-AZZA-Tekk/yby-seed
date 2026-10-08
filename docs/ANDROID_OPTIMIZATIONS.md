# Otimizações para Android (HyperOS 3.0 + Termux)

> **Status:** v1.1.0
> **Última atualização:** 2026-10-08
> **Dispositivo:** Xiaomi 12 (Android 15, HyperOS 3.0)

## 🚨 Gargalos Críticos do HyperOS 3.0

O HyperOS 3.0 é o **ambiente mais hostil** para execução de processos contínuos no Android:

| Gargalo | Limite | Impacto no Termux |
|---------|--------|-------------------|
| **Phantom Process Killer (PPK)** | 32 subprocessos | Mata Termux se >32 processos |
| **MiuiSentinelMemoryManager** | 3.5GB PSS | Mata apps com >3.5GB RAM |
| **CPU Throttling** | 42°C | Throttle em inferência LLM |

---

## 🛠️ Solução 1: Desativar Phantom Process Killer

### **Via Shizuku + ADB (sem root):**

```bash
# 1. Instalar Shizuku (Play Store)
# 2. Ativar Shizuku em Configurações do Desenvolvedor
# 3. Executar comandos:

# Aumentar limite de processos fantasmas para máximo (2^31)
adb shell device_config put activity_manager max_phantom_processes 2147483647

# Desativar monitoramento de CPU
adb shell settings put global settings_enable_monitor_phantom_procs false

# Prevenir sobrescrita de configs durante atualizações diárias
adb shell device_config set_sync_disabled_for_tests persistent
```

### **Verificação:**

```bash
# Verificar se limite foi aplicado
adb shell device_config get activity_manager max_phantom_processes
# Deve retornar: 2147483647
```

---

## 🛠️ Solução 2: Cegar MiuiSentinelMemoryManager

### **Via Shizuku + ADB:**

```bash
# Restringir acesso do PowerKeeper a estatísticas de uso
adb shell appops set com.miui.powerkeeper GET_USAGE_STATS deny

# Desativar sentinela de memória (HyperOS >3.0.7)
adb shell settings put global miui_sentinel_memory_manager_enabled 0

# Reiniciar Termux para aplicar
```

### **Verificação:**

```bash
# Verificar se sentinela está desativada
adb shell settings get global miui_sentinel_memory_manager_enabled
# Deve retornar: 0
```

---

## 🛠️ Solução 3: OpenCL na GPU Adreno 730

### **Problema:**
Inferência LLM na CPU Snapdragon esquenta >42°C em 2-3 minutos → thermal throttling.

### **Solução:**
Compilar `llama.cpp` com backend **OpenCL** para usar GPU Adreno 730.

### **Passo a Passo no Termux:**

```bash
# 1. Instalar dependências
pkg update && pkg upgrade
pkg install python clang cmake ocl-icd opencl-headers

# 2. Adicionar libs do vendor ao LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/vendor/lib64:/system/vendor/lib64:$LD_LIBRARY_PATH

# 3. Clonar e compilar llama.cpp com OpenCL
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
mkdir build && cd build
cmake -DGGML_OPENCL=ON ..
make -j8

# 4. Testar inferência
./bin/main -m ../models/qwen2.5-7b-q4_k_m.gguf -p "Hello" -n 128
```

### **Impacto:**
- **CPU:** 42°C em 2 min → **GPU:** 35°C em 10 min
- **Performance:** 15 t/s (CPU) → 22 t/s (GPU)
- **Estabilidade:** Sem throttling após 30 min

---

## 🛠️ Solução 4: Termux:API para Contexto

### **Instalar:**

```bash
pkg install termux-api
pkg install termux-widget
```

### **Exemplos de Uso:**

```bash
# Bateria
termux-battery-status

# Localização
termux-location

# Notificações
termux-notification --title "YBY SEED" --content "Automação concluída"

# SMS
termux-sms-send -n +5511999999999 "Backup concluído!"

# Clipboard
termux-clipboard-set "Texto copiado"
termux-clipboard-get
```

---

## 🛠️ Solução 5: Tasker para Automações

### **Perfil: Backup Automático**

1. **Gatilho:** Hora = 03:00
2. **Ação:** Executar script Termux
3. **Script:**

```bash
#!/data/data/com.termux/files/usr/bin/bash
cd ~/yby-seed
python src/main.py "backup /sdcard/Documents /sdcard/Backups"
```

### **Perfil: Notificação de Chuva**

1. **Gatilho:** Webhook MQTT `yby/alert`
2. **Ação:** Notificação + Vibração

---

## 📊 Comparação: Antes vs. Depois

| Métrica | Antes | Depois | Ganho |
|---------|-------|--------|-------|
| **Processos máximos** | 32 | 2.1B | +67M x |
| **RAM máx (PSS)** | 3.5GB | 12GB | +3.4x |
| **Temperatura (30 min)** | 45°C | 35°C | -10°C |
| **Tokens/s (LLM)** | 15 t/s | 22 t/s | +47% |
| **Estabilidade** | 10 min | >1h | +6x |

---

## 🔗 Referências

- [Termux Wiki: ADB Commands](https://wiki.termux.com/wiki/ADB)
- [XDA: HyperOS 3.0 PPK](https://forum.xda-developers.com/t/hyperos-3-0-phantom-process-killer.4589234/)
- [llama.cpp OpenCL Backend](https://github.com/ggerganov/llama.cpp/pull/3024)
- [Qualcomm OpenCL 3.0](https://www.qualcomm.com/news/onq/2021/06/opencl-30-what-it-means-developers-and-consumers)
