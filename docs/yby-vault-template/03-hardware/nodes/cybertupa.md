---
type: hardware-node
node_id: cybertupa
node_name: CyberTupã
tier: station
role: Estação Off-Grid de Campo e Alimentação 18V
hardware_summary: Estação portátil com banco de bateria 18V e telemetria local
os_runtime: Linux Embarcado / Telemetria MQTT
connectivity: Wi-Fi Local + Tailscale + Off-Grid Power
endpoints: "mqtt://yby/nodes/cybertupa/telemetry"
status: planned
offline_ready: true
tags:
  - hardware
  - station
  - cybertupa
  - off-grid
---

# CyberTupã

Estação móvel off-grid do ecossistema YBY alimentada por bateria 18V para autonomia energética em campo, acoplada à malha local junto ao [[pc-hub]] e ao [[xiaomi-12]].

- Topologia: [[TOPOLOGIA_MALHA_YBY.canvas]]
- Inventário: [[INVENTARIO_NOS_YBY.base]]
