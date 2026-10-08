# Futuro: Mobile + ESP32

> **Status:** Em planejamento (Fase 2 + Fase 3)  
> **Última atualização:** 2026-10-08

## 📱 Fase 2: Mobile (Android + Termux)

### Hardware Alvo:
- Xiaomi 12 (Snapdragon 8 Gen 1, Adreno 730 GPU)
- Android 15 + HyperOS 3.0
- 12GB RAM

### Componentes:
- Gateway MQTT no Termux
- OpenCL na GPU Adreno 730
- Injeção ADB (desativar PPK + MiuiSentinel)
- Termux:API (sensores, notificações, SMS)

### Documentação (movida de `src/mobile/`):
- `MOBILE_FUTURE.md` — Guia completo de setup
- `ANDROID_OPTIMIZATIONS.md` — Otimizações HyperOS 3.0

### Cronograma:
- **Início:** Fase 2 (após estabilização do PC Hub)
- **Duração:** 2-3 meses
- **Dependências:** PC Hub estável + testes automatizados

---

## ⌚ Fase 3: Wearable (ESP32-S3)

### Hardware Alvo:
- LilyGO T-Watch S3 Plus (ESP32-S3, 8MB PSRAM)
- Sensores: MAX30102 (batimentos, SpO2), BMM150 (acelerômetro)

### Componentes:
- Firmware PlatformIO (MQTT+TLS, Deep Sleep)
- Sensores biométricos (batimentos, SpO2, passos)
- Display LVGL (interface vestível)

### Documentação (movida de `firmware/`):
- `ESP32_FUTURE.md` — Firmware e esquemáticos

### Cronograma:
- **Início:** Fase 3 (após Mobile estável)
- **Duração:** 3-4 meses
- **Dependências:** Mobile estável + gateway MQTT funcionando

---

## 🔗 Referências

- [Roadmap YBY SEED](../README.md#roadmap)
- [Arquitetura PC Hub](ARCHITECTURE.md)
