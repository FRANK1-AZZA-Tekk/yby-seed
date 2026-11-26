---
type: hardware-node
node_id: pc-hub
node_name: PC Hub
tier: core
role: Núcleo de Inferência, FastAPI, RAG pgvector e Broker MQTT
hardware_summary: AMD Ryzen 5 4600G, 16GB DDR4, GTX 1650 4GB VRAM, 1TB NVMe
os_runtime: Ubuntu / FastAPI / LiteLLM / Ollama / llama.cpp / Postgres+pgvector / Redis / Mosquitto
connectivity: LAN + Tailscale
endpoints: "http://127.0.0.1:8000/api/v1/cockpit/status, mqtt://127.0.0.1:1883"
status: active
offline_ready: true
tags:
  - hardware
  - core
  - pc-hub
  - local-first
---

# PC Hub

Núcleo cognitivo local-first da malha YBY. Hospeda a API FastAPI ([[moto-edge-30-phonebox]] e [[xiaomi-12]]), inferência local via Ollama/`llama.cpp` (`qwen2.5-coder:3b`), cache Redis, memória vetorial PostgreSQL + `pgvector` e broker Mosquitto MQTT.

- Topologia: [[TOPOLOGIA_MALHA_YBY.canvas]]
- Inventário: [[INVENTARIO_NOS_YBY.base]]
- Template de Spec: [[TEMPLATE_YBY_SPEC]]
