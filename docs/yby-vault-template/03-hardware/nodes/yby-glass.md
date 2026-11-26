---
type: hardware-node
node_id: yby-glass
node_name: YBY Glass (XIAO ESP32-S3 Sense)
tier: wearable
role: Captura Visual e Áudio Leve na Borda
hardware_summary: Seeed Studio XIAO ESP32-S3 Sense (Câmera OV2640 + Microfone PDM)
os_runtime: Firmware ESP32-S3 + MQTT / HTTP Local
connectivity: Wi-Fi Local + BLE + MQTT
endpoints: "mqtt://yby/cockpit/action, mqtt://yby/nodes/glass/telemetry"
status: active
offline_ready: true
tags:
  - hardware
  - wearable
  - yby-glass
  - esp32-s3
---

# YBY Glass (XIAO ESP32-S3 Sense)

Óculos sensoriais leves baseados no XIAO ESP32-S3 Sense. Capturam frames sob demanda para visão local no [[pc-hub]] e respondem a comandos operacionais recebidos via `yby/cockpit/action` disparados pelo [[moto-edge-30-phonebox]].

- Topologia: [[TOPOLOGIA_MALHA_YBY.canvas]]
- Inventário: [[INVENTARIO_NOS_YBY.base]]
