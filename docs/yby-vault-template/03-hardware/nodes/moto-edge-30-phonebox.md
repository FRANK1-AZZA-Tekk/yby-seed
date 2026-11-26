---
type: hardware-node
node_id: moto-edge-30-phonebox
node_name: Moto Edge 30 + PhoneBox
tier: surface
role: Painel Tátil de Telemetria, Status e Webhooks Locais
hardware_summary: Motorola Edge 30 (AMOLED 144Hz) + PhoneBox
os_runtime: Android / PhoneBox (YBY ZERO Dark UI)
connectivity: LAN + Tailscale HTTP
endpoints: "GET /api/v1/cockpit/status, POST /api/v1/cockpit/webhook"
status: active
offline_ready: true
ui_palette:
  obsidian: "#0D0D0D"
  off_white: "#F5F5F2"
  silicon_green: "#00FF66"
  titanium_gray: "#8E8E93"
tags:
  - hardware
  - surface
  - phonebox
  - moto-edge-30
---

# Moto Edge 30 + PhoneBox

Superfície tátil dedicada de telemetria e controle do ecossistema YBY. Consome `GET /api/v1/cockpit/status` do [[pc-hub]] em baixa latência e dispara comandos táteis via `POST /api/v1/cockpit/webhook` (`capture_inbox`, `trigger_reindex`, `publish_mqtt`).

- Topologia: [[TOPOLOGIA_MALHA_YBY.canvas]]
- Inventário: [[INVENTARIO_NOS_YBY.base]]
- Nós acionados via MQTT: [[t-watch-s3-plus]], [[yby-glass]]
