# Scan técnico — LilyGO T-Watch S3 Plus × YBY

> **Escopo:** documentação pós-v1. **Não** implementar firmware neste repositório (D1, D7).  
> **Princípio:** FUNCTION OVER FORM; local-first; IA só no PC Hub; relógio sem cloud; IA externa não comanda GPIO.  
> **Data do scan:** 2026-11-19.

Irmãos: [PLANO_ECOSISTEMA_WEARABLE.md](PLANO_ECOSISTEMA_WEARABLE.md), [FICHA_INVESTIGACAO.md](FICHA_INVESTIGACAO.md), [METRICAS_OBSERVABILIDADE.md](METRICAS_OBSERVABILIDADE.md).

Legenda: **Fato** = doc oficial / issue / medição citada. **Hipótese** = a validar na Plus real.

---

## 1. Arquitetura recomendada

```text
[T-Watch S3 Plus]                    [PC Hub yby-seed]
  sensores / LVGL mínimo               Ollama 3B (D4)
  mic PDM → PCM curto                  Whisper + Piper
  fila offline + IDs                   safety / actions
  MQTT/TLS cliente                     Mosquitto LAN (TLS)
        │                                      │
        └──────── eventos JSON ────────────────┘
                 hub → intent allowlist → firmware
```

| Camada | Papel | Onde |
|---|---|---|
| **T-Watch S3 Plus** | Sensores, UI fina, mic, fila offline, MQTT/TLS | FRANK_ZER0 / YBY |
| **Broker** | Mosquitto LAN + ACL por device | PC Hub |
| **PC Hub** | Autoridade: telemetria, STT/TTS, LLM, confirmação humana | `yby-seed` |
| **Android** | BLE provision / notificação | Fora do v1 |

Regras duras:

- Sem Tailscale/WireGuard no ESP32; sem OpenRouter no relógio.
- Intent versionado hub→firmware allowlist; nunca cloud→GPIO.
- Menu ≤5 ações; microgestos = eventos `confirm` / `back` / `voice`.

### Hardware Plus (fato — LilyGoLib)

| Item | Valor |
|---|---|
| SoC | ESP32-S3 |
| Flash / PSRAM | 16 MB QSPI / 8 MB OPI |
| GNSS | u-blox MIA-M10Q (Plus) |
| LoRa | SX1262 (board revision) |
| Accel | BMA423 |
| RTC | PCF8563 |
| PMIC | AXP2101 |
| Haptic | DRV2605 |
| Mic / amp | SPM1423HM4H-B / MAX98357A |
| Touch | FT6336U (**RESET não conectado**) |
| Display | 240×240 ST7789V3, BL GPIO 45 |
| Esquemático | `schematic/T-Watch-S3-Plus-GPS V1.0 2025-04-29.pdf` em [LilyGoLib](https://github.com/Xinyuan-LilyGO/LilyGoLib) |

Fontes: [docs/hardware/lilygo-t-watch-s3-plus.md](https://github.com/Xinyuan-LilyGO/LilyGoLib/blob/master/docs/hardware/lilygo-t-watch-s3-plus.md), [wiki Quick Start Plus](https://wiki.lilygo.cc/products/t-watch-series/t-watch-s3-plus/quick-start.html).

---

## 2. Classificação

### Usar agora (hub / docs — wearable ainda pós-v1)

| Item | O que é | Por que útil | Problema que resolve | Onde no YBY | Risco | Adaptação | Pri |
|---|---|---|---|---|---|---|---|
| PC Hub + voz + safety | `ask`, Whisper/Piper, D10 | Autoridade local | LLM/ação no relógio | `yby-seed` | — | Manter | P0 |
| Ficha + métricas | FICHA / METRICAS | Fato vs hipótese | Otimizar no escuro | docs/future | Só papel | Preencher por experimento | P0 |
| LilyGoLib pinout/esquemático | MIT | Pinout/GPS/PMIC corretos | Variante S3 vs Plus | Ficha hardware | Lib/branch errada | Fixar revisão PCB + rádio | P0 doc |

### Usar depois (Fase P hub estável)

| Item | O que é | Por que útil | Problema | Onde | Risco | Adaptação | Pri |
|---|---|---|---|---|---|---|---|
| LilyGoLib + PlatformIO | BSP Plus; Arduino-ESP32 ≥3.3.11 | Bring-up oficial | BSP lagado | FRANK_ZER0 | ThirdParty pinado | Env Plus; não atualizar deps cegas | P1 |
| ESP-IDF + esp-mqtt | Apache-2.0 MQTT TLS | Reconnect, stack TLS | PubSubClient frágil | Firmware | Stack 6 KB curto | Stack MQTT ≥8 KB; `client_id` único | P1 |
| Mosquitto LAN TLS | Broker EDL | Telemetria→hub | Broker na WAN | Hub | ACL fraca | Só LAN / Tailscale no PC | P1 |
| XPowersLib / AXP2101 | PMIC | BL / rails / carga | Sleep mal medido | Firmware | Rail errado | Medir mA por modo | P1 |
| BMA423 + RTC | Accel / wake | Microgesto | Falso positivo | Eventos | Ruído | Calibrar thresholds | P1 |
| Mic PDM → hub STT | SPM1423 → hub | Voz sem LLM no chip | Bandwidth | Pipeline voz | Wi-Fi sempre on | Buffer curto; STT só no hub | P1 |

### Adaptar

| Item | O que é | Por que útil | Problema | Onde | Risco | Adaptação | Pri |
|---|---|---|---|---|---|---|---|
| LVGL | UI 240×240 | Status / confirm | Stack overflow recursão; docs v7 vs v8 | UI fina | FPS vs bateria | Wiki Plus = v8; FB em PSRAM; stack UI IRAM; ≤3 telas | P1 |
| esp-mqtt + mbedTLS | MQTTS | Transporte seguro | Heap leak `loadCACert` stream; WDT | Firmware | OOM pós-sleep | Bundle/`setCACert`; dynamic mbedtls; watermark heap | P1 |
| Sleep IDF | Light / deep | Autonomia | Touch sem reset: sleep touch exige reboot (**fato** doc S3/Plus pinout) | Energia | UX brick | Light sleep + BL off; deep só timer/botão | P1 |
| Fila offline + IDs | Event store | Rede intermitente | Duplicatas | Gateway | Flash wear | Idempotência + batch | P1 |
| CBOR telemetria | Compacto | Bytes/rádio | Debug | Após JSON P0 | Schema drift | JSON P0 → CBOR P1 | P2 |
| ESP Insights (Apache-2.0) | Heap/crash metrics | Diagnóstico | Cloud Espressif por default | Observabilidade | Viola local-first | Só padrão de métricas → MQTT **hub**; sem Insights cloud | P2 |

### Evitar

| Item | Por quê | Alternativa YBY |
|---|---|---|
| ESP Insights cloud / RainMaker | Telemetria fora do hub | Métricas locais → hub |
| ESPHome no relógio (GPL runtime) | Licença + HA | LilyGoLib + IDF |
| Tailscale / WireGuard no ESP32 | CPU/RAM/bateria | MQTT/TLS ao hub |
| LLM / Whisper no relógio | VRAM no PC; S3 sem margem | Hub Ollama 3B + voz |
| IA cloud → GPIO | Segurança | Intent hub + allowlist |
| UI dashboard rico LVGL | Forma > função | ≤5 ações / ≤3 telas |
| TTGO_TWatch_Library trunk antigo / esp core ≤2.0 | Plus exige Arduino-ESP32 3.3.11+ | LilyGoLib + wiki |
| Flash Meshtastic sem BOOT+RST | Upload falha (wiki) | Procedimento documentado |
| ULP I2C deep-sleep “mágico” | I2C S3 fora dos GPIOs ULP 0–4 (issue TTGO #257, **fato** S3); Plus: validar no PDF | Não planejar ULP I2C sem pinout |
| omi backend cloud | Áudio contínuo SaaS | Só padrões; D7 |

---

## 3. Tecnologias aprovadas vs descartadas

**Aprovadas (stack alvo pós-v1):** LilyGoLib (MIT) + PlatformIO; Arduino-ESP32 / IDF pinado pela LilyGO; esp-mqtt + TLS; Mosquitto no hub; JSON schema de eventos; LVGL mínimo; AXP2101/XPowers; BMA + mic → hub; Ollama 3B + Whisper/Piper no hub; Tailscale **só** PC/phone.

**Descartadas no relógio:** Insights cloud, ESPHome merge, LLM on-device, VPN on-device, FAISS-GPU, multi-agente no firmware, UI complexa.

---

## 4. Gargalos detectados

| Gargalo | Tipo | Evidência |
|---|---|---|
| S3 vs S3 Plus / LVGL v7 vs v8 | Doc | Wiki Plus: LVGL v8; README TTGO antigo: v7.7.2 |
| I2C fora do ULP; XTAL32K pins reusados | Hardware | TTGO #257 — **fato** S3; **hipótese** até confirmar Plus no esquemático |
| Touch sleep irreversível | Hardware | RESET touch NC (fato pinout Plus) |
| MQTT TLS heap / stack | Firmware | arduino-esp32 #9636; esp-mqtt stack default 6144 |
| LVGL recursão `on_value` | UI | Padrão geral (ex. ESPHome #6524) |
| Wi-Fi+BLE+LoRa+GPS+display | Energia/RF | **Hipótese** — medir na Plus |
| Latência voz mic→hub | Sistema | Sem cloud; depende Wi-Fi |

---

## 5. Mitigação

1. Preencher [FICHA_INVESTIGACAO.md](FICHA_INVESTIGACAO.md) com revisão PCB + board revision rádio **antes** de código.
2. Benchmark energia (active / BL on-off / light / deep / GPS on) com amperímetro → [METRICAS_OBSERVABILIDADE.md](METRICAS_OBSERVABILIDADE.md).
3. MQTT: stack ≥8 KB; cert estático; `client_id=yby-<mac>`; QoS0 telemetria, QoS1 comandos.
4. LVGL: partial buffer PSRAM; watermark de stack UI; sem callbacks recursivos.
5. Firmware só executa allowlist; hub confirma ações destrutivas.
6. Publicar periodicamente `{heap_free, heap_min, largest, wifi_rssi, bat_mv}` no hub (padrão Insights **sem** nuvem Espressif).

---

## 6. Sprints (após Fase P do hub)

| Sprint | Objetivo | Aceite |
|---|---|---|
| **W0** | Este SCAN + ficha Plus + ref. esquemático | Ficha com campos PCB |
| **W1** | Helloworld LilyGoLib, BL, bat %, heap UART | Log serial |
| **W2** | Medir 5 modos energia; BL off + light sleep | Tabela mA **Plus** |
| **W3** | MQTT/TLS → Mosquitto; JSON; fila offline | RTT &lt;2 s LAN |
| **W4** | UI 3 telas + 2 microgestos → eventos | Soak 1 h sem stack overflow |
| **W5** | Mic clip → hub STT → resposta curta | Latência p50/p95 |
| **W6** | Intent hub→watch allowlist | Sem path cloud→GPIO |

Wearable **não** conta no % do v1 PC Hub.

---

## 7. Próximos experimentos e benchmarks

1. Corrente deep/light **Plus** vs números publicados do S3 (LilyGO hardware doc S3: light ~2.38 mA; deep ~0.46–0.53 mA — **fato S3**, gerar fato Plus).
2. Heap após 100 ciclos Wi-Fi + MQTT TLS connect/sleep.
3. Latência toque → MQTT → hub → ack.
4. FPS LVGL 1 label vs 3 telas (partial buf).
5. GPS cold start / AssistNow — **só se** o produto precisar GPS; senão desligar rail GPS/LoRa.

---

## Fontes (não popularidade)

- [LilyGoLib](https://github.com/Xinyuan-LilyGO/LilyGoLib) (MIT)
- [Wiki T-Watch S3 Plus Quick Start](https://wiki.lilygo.cc/products/t-watch-series/t-watch-s3-plus/quick-start.html)
- [ESP-IDF / esp-mqtt](https://docs.espressif.com/projects/esp-mqtt/en/latest/esp32/) (Apache-2.0)
- [ESP Insights](https://documentation.espressif.com/esp-insights/main/README.md) — padrão de métricas; cloud **evitar**
- [arduino-esp32 #9636](https://github.com/espressif/arduino-esp32/issues/9636) (leak `loadCACert`)
- [TTGO_TWatch_Library #257](https://github.com/Xinyuan-LilyGO/TTGO_TWatch_Library/issues/257) (ULP / energia S3)
