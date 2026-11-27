---
type: hardware-node
node_id: t-watch-s3-plus
node_name: LILYGO T-Watch S3 Plus
tier: wearable
role: Wearable de Pulso, Alertas Hápticos e Comandos Rápidos
hardware_summary: ESP32-S3, Display Touch, Motor Háptico, LoRa/Wi-Fi/BLE
os_runtime: Firmware ESP-IDF / Arduino + Cliente MQTT
connectivity: Wi-Fi Local + BLE + MQTT
endpoints: "mqtt://yby/cockpit/action, mqtt://yby/audio/state, mqtt://yby/nodes/twatch/telemetry"
status: active
offline_ready: true
tags:
  - hardware
  - wearable
  - t-watch-s3-plus
  - mqtt
---

# LILYGO T-Watch S3 Plus

Wearable de pulso da malha YBY. Recebe comandos publicados pelo [[moto-edge-30-phonebox]] através do [[pc-hub]] no tópico `yby/cockpit/action` e sincroniza telemetria local via [[xiaomi-12]] ou Mosquitto direto.

- Topologia: [[TOPOLOGIA_MALHA_YBY.canvas]]
- Inventário: [[INVENTARIO_NOS_YBY.base]]
