# Métricas e observabilidade (ecossistema YBY)

> Catálogo de **o que medir** antes de otimizar. Valores de datasheet **não** são metas — só medições em hardware real contam. **v1 ativo:** PC Hub ([ROADMAP.md](../../ROADMAP.md) métricas de agente). Wearable/mobile: fases futuras.

## PC Hub (v1 — instrumentar primeiro)

| Domínio | Métrica | Onde hoje / alvo |
|---|---|---|
| IA | Latência `ask` (local/nuvem) | `src/engine`, [MODEL_CARD.md](../../MODEL_CARD.md) |
| IA | Tokens / custo por execução | `test_cloud_usage_log`, D12 |
| IA | Taxa de erro / timeout provedor | `HybridEngine`, logs |
| IA | % offline (sem nuvem) | Config sem chave = 100% local |
| Plataforma | Hub keepalive OK | `src/platform`, journal |
| Segurança | Bloqueios `safety` / AST | `src/safety`, `ast_guard` |

## Hardware (wearable — medição futura)

| Métrica | Notas |
|---|---|
| Corrente, tensão, temperatura | PMIC da placa; não extrapolar de módulo SoC sozinho |
| Boot, resets, periféricos | Contador NVS + panic reason |

## Firmware (ESP32-S3 Plus — futuro)

| Métrica | Ferramenta típica |
|---|---|
| Heap livre / mínimo / maior bloco | `heap_caps_get_*`, logs periódicos |
| PSRAM vs interna | `MALLOC_CAP_SPIRAM` |
| Stack high-water | `uxTaskGetStackHighWaterMark` |
| Watchdog, coredump | IDF panic, `esp_core_dump` |
| Tempo de boot | GPIO + log timestamp cold/warm |

## UI (LVGL — futuro)

| Métrica | Meta de engenharia |
|---|---|
| FPS, tempo render/flush | `lv_timer`, evitar full-screen invalidation |
| Latência touch | IRQ → evento |
| RAM display | Buffers parciais vs full; PSRAM |

**Avatar YBY:** oito estados oficiais **ainda não estão definidos neste repositório** — registrar no PRD fase D ([ROADMAP.md](../../ROADMAP.md)); não adicionar estados visuais extras sem ganho funcional.

## Rede

| Métrica | Aplicação |
|---|---|
| Latência, perda, jitter, reconexão | MQTT/WSS até PC Hub |
| Throughput | Telemetria em burst |
| Consumo RF | Por modo Wi-Fi/BLE (medido, não datasheet) |

## IA (no hub, não no relógio)

| Métrica | Regra |
|---|---|
| Tempo de resposta, timeout, taxa de erro | Ollama no PC |
| Confiança / citação | Agente fase B |
| Tamanho de mensagem | Truncar antes da nuvem (`YBY_CLOUD_CONTEXT_MAX_CHARS`) |

**Regra:** IA externa **não** comanda GPIO/atuadores; só o gateway normaliza intent → fila → firmware com contrato versionado.

## Android (gateway móvel — futuro)

| Métrica | Contexto |
|---|---|
| Tempo ativo, reconexão, kill em background | HyperOS / Doze — ver [MOBILE_FUTURE.md](MOBILE_FUTURE.md) |
| Consumo | Tailscale + MQTT opcional |

Ligar métricas de agente do [ROADMAP.md](../../ROADMAP.md) às métricas de produto acima quando o agente P0 existir.