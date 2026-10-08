# Futuro: Mobile (Android + Termux)

> **Status:** Em planejamento (Fase 2)  
> **Última atualização:** 2026-10-08  
> **Dispositivo:** Xiaomi 12 (Android 15, HyperOS 3.0)

## 📱 Visão Geral

O YBY SEED Mobile permitirá que o sistema rode em **Xiaomi 12** com Termux, usando a GPU Adreno 730 para inferência local via OpenCL.

## 📦 Pré-requisitos

- Xiaomi 12 (Snapdragon 8 Gen 1, Adreno 730)
- Android 15 + HyperOS 3.0
- 12GB RAM
- Termux (F-Droid) + Termux:API

## 🔧 Otimizações (movidas de `src/mobile/`)

### 1. Injeção ADB (Desativar PPK + MiuiSentinel)

```bash
# Desativar Phantom Process Killer
adb shell device_config put activity_manager max_phantom_processes 2147483647
adb shell settings put global settings_enable_monitor_phantom_procs false

# Desativar MiuiSentinel
adb shell appops set com.miui.powerkeeper GET_USAGE_STATS deny
adb shell settings put global miui_sentinel_memory_manager_enabled 0
```

### 2. OpenCL na GPU Adreno 730

```bash
# No Termux:
pkg install ocl-icd opencl-headers

# Compilar llama.cpp com OpenCL:
cd llama.cpp
mkdir build && cd build
cmake -DGGML_OPENCL=ON -DGGML_OPENCL_SDK_VERSION=3.0 ..
make -j8
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

chmod +x ~/.termux/boot.sh
```

## 📊 Benchmarks (Esperados)

| Métrica | Sem Otimizações | Com Otimizações |
|---------|-----------------|-----------------|
| Estabilidade | 10 min | >1h |
| Temperatura | 45°C | 35°C |
| Tokens/s | 15 t/s | 22 t/s |

## 🔗 Referências

- [Mobile Setup (movido de `docs/MOBILE_SETUP.md`)](MOBILE_SETUP.md)
- [Android Optimizations (movido de `docs/ANDROID_OPTIMIZATIONS.md`)](ANDROID_OPTIMIZATIONS.md)
- [Roadmap YBY SEED](../README.md#roadmap)
