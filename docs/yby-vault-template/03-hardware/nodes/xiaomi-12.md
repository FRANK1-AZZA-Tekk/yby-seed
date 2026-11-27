---
type: hardware-node
node_id: xiaomi-12
node_name: Xiaomi 12
tier: edge-gateway
role: Gateway Móvel Primário e Failover PocketPal
hardware_summary: Snapdragon 8 Gen 1, Android + Termux
os_runtime: Android / Termux / Mosquitto local / PocketPal
connectivity: Wi-Fi + Tailscale + BLE
endpoints: "POST /edge/sync, http://100.64.0.2:8080/v1"
status: active
offline_ready: true
tags:
  - hardware
  - edge-gateway
  - xiaomi-12
  - termux
---

# Xiaomi 12

Gateway móvel primário da malha YBY rodando em Termux/Android. Coleta eventos offline dos wearables ([[t-watch-s3-plus]], [[yby-glass]]) e sincroniza em lotes idempotentes com o [[pc-hub]] via `/edge/sync` quando o túnel Tailscale está disponível.

- Topologia: [[TOPOLOGIA_MALHA_YBY.canvas]]
- Inventário: [[INVENTARIO_NOS_YBY.base]]
