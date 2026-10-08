"""
Mobile Setup — Guia completo de setup (Android + HyperOS 3.0)

# YBY SEED — Mobile Setup (Xiaomi 12, HyperOS 3.0)

> **Status:** v1.1.0  
> **Última atualização:** 2026-10-08  
> **Dispositivo:** Xiaomi 12 (Android 15, HyperOS 3.0)

## 📱 Pré-requisitos

- Xiaomi 12 (ou similar com Snapdragon 8 Gen 1)
- Android 15 + HyperOS 3.0
- 12GB RAM (mínimo 8GB)
- 128GB storage (mínimo 64GB)

## 📦 Instalação

### 1. Termux (F-Droid, NÃO Play Store)

```bash
# Baixar F-Droid: https://f-droid.org/
# Instalar Termux do F-Droid: https://f-droid.org/packages/com.termux/
```

**Importante:** Versão da Play Store está desatualizada e não recebe mais updates.

### 2. Termux:API

```bash
pkg update && pkg upgrade
pkg install termux-api
```

### 3. Shizuku (Play Store)

- Instalar Shizuku: https://play.google.com/store/apps/details?id=moe.shizuku.privileged.api
- Ativar em **Configurações do Desenvolvedor**
- Conectar via wireless (ADB)

### 4. ADB Wireless

```bash
# Ativar depuração USB em Configurações do Desenvolvedor
# Ativar "Depuração wireless"
# Anotar IP e porta (ex: 192.168.1.100:5555)
```

## 🔧 Configuração

### 1. Injeção ADB (Desativar PPK + MiuiSentinel)

```bash
# Conectar ADB wireless
adb connect 192.168.1.100:5555

# Desativar Phantom Process Killer
adb shell device_config put activity_manager max_phantom_processes 2147483647
adb shell settings put global settings_enable_monitor_phantom_procs false
adb shell device_config set_sync_disabled_for_tests persistent

# Desativar MiuiSentinelMemoryManager
adb shell appops set com.miui.powerkeeper GET_USAGE_STATS deny
adb shell settings put global miui_sentinel_memory_manager_enabled 0

# Verificar
adb shell device_config get activity_manager max_phantom_processes
# Deve retornar: 2147483647
```

### 2. OpenCL na GPU Adreno 730

```bash
# No Termux:
pkg install ocl-icd opencl-headers

# Compilar llama.cpp com OpenCL:
cd ~/llama.cpp
mkdir build && cd build
cmake -DGGML_OPENCL=ON -DGGML_OPENCL_SDK_VERSION=3.0 ..
make -j8

# Adicionar libs do vendor ao LD_LIBRARY_PATH:
export LD_LIBRARY_PATH=/vendor/lib64:/system/vendor/lib64:$LD_LIBRARY_PATH

# Adicionar ao ~/.bashrc (persistente):
echo 'export LD_LIBRARY_PATH="/vendor/lib64:/system/vendor/lib64:$LD_LIBRARY_PATH"' >> ~/.bashrc
```

### 3. Foreground Service (Evitar kill em background)

```bash
# Criar script de boot:
cat > ~/.termux/boot.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash

# Foreground service (notificação persistente)
termux-notification --title "YBY SEED Gateway" --content "Executando em background" --ongoing true

# Manter CPU ativa
while true; do
    sleep 300
done
EOF

# Tornar executável:
chmod +x ~/.termux/boot.sh
```

### 4. Battery Optimization Whitelist

```bash
# Via ADB:
adb shell appops set com.termux IGNORE_BACKGROUND_RESTRICTIONS allow

# Manual (sem ADB):
# Configurações > Apps > Termux > Bateria > Sem restrições
```

## 🚀 Execução

### 1. Iniciar Termux

```bash
# Abrir Termux
# Executar boot script:
~/.termux/boot.sh
```

### 2. Iniciar Gateway MQTT

```bash
cd ~/yby-seed
python src/mobile/gateway.py
```

### 3. Verificar Status

```bash
# Bateria
termux-battery-status

# GPS
termux-location

# Notificação de teste
termux-notification --title "YBY SEED" --content "Gateway ativo"
```

## 📊 Benchmarks

### Antes (sem otimizações):

- **Estabilidade:** 10 min (Termux é killado)
- **Temperatura:** 45°C (CPU throttling)
- **Tokens/s:** 15 t/s (LLM na CPU)

### Depois (com otimizações):

- **Estabilidade:** >1h (foreground service)
- **Temperatura:** 35°C (GPU OpenCL)
- **Tokens/s:** 22 t/s (GPU Adreno 730)

## 🛠️ Troubleshooting

### Termux é killado em background

```bash
# Verificar se foreground service está ativo
ps aux | grep boot.sh

# Se não estiver rodando, reiniciar:
~/.termux/boot.sh
```

### OpenCL não detecta GPU

```bash
# Verificar se libs do vendor estão acessíveis
ls -la /vendor/lib64/libOpenCL.so

# Se não existir, adicionar ao LD_LIBRARY_PATH:
export LD_LIBRARY_PATH=/vendor/lib64:/system/vendor/lib64:$LD_LIBRARY_PATH
```

### ADB não conecta

```bash
# Verificar se depuração wireless está ativa
# Configurações > Opções do Desenvolvedor > Depuração wireless

# Reconectar:
adb disconnect
adb connect 192.168.1.100:5555
```

## 🔗 Referências

- [Termux Wiki](https://wiki.termux.com/)
- [Shizuku](https://shizuku.rikka.app/)
- [llama.cpp OpenCL Backend](https://github.com/ggerganov/llama.cpp/pull/3024)
- [HyperOS 3.0 PPK](https://forum.xda-developers.com/t/hyperos-3-0-phantom-process-killer.4589234/)
