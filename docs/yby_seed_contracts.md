# YBY SEED — contratos técnicos canônicos (ingestão pgvector)

Documento de referência para RAG (`memory/ingest.py`), agentes e geração de dataset (`forge/dataset_synth.py`).  
**Function Over Form:** regras verificáveis pelo `hardware_linter` e pelo sandbox Docker.

---

## 1. Placas e módulos suportados

| ID | Uso |
|---|---|
| `seeed_xiao_esp32s3` | XIAO ESP32-S3, footprint mínimo |
| `esp32_s3_devkitc1` | DevKitC-1 ESP32-S3 (referência) |
| `esp32_p4_c6` | ESP32-P4 + C6 (Wi-Fi 6 / coexistência) |
| `waveshare_modbus_rtu` | Gateway/industrial Modbus RTU (ESP32 + RS-485) |

### 1.1 Pinagem — regras comuns

- Declarar a placa no código ou comentário (`board: seeed_xiao_esp32s3`).
- **Nunca** usar GPIO em `reserved_flash_psram`, `strapping_critical` ou pinos de `usb_uart` / `rs485` conforme `BOARD_CONSTRAINTS` em `sandbox/hardware_linter.py`.
- Um pino físico → uma função (sem conflito de `GPIO_NUM_*`, `#define` e `pinMode` divergentes).
- UART/console: respeitar pinos USB-UART da placa; RS-485 só nos pinos `rs485` do módulo Waveshare.

### 1.2 Modbus RTU (`waveshare_modbus_rtu` / domínio `modbus_rtu`)

- Baud: `1200`–`115200` (conjunto permitido no linter).
- Funções: `1, 2, 3, 4, 5, 6, 15, 16, 23`.
- Tramas com **CRC-16 Modbus** correta (polinômio 0xA001).
- Slave ID `1–247`; sem broadcast `0` em escrita sem salvaguarda documentada.

---

## 2. Firmware — ESP-IDF v5.3

**Stack:** FreeRTOS, driver GPIO, ADC, I2C, SPI, MQTT (esp_mqtt).

Obrigatório em exemplos `esp_idf`:

- `app_main` ou task init explícita; prioridades FreeRTOS plausíveis (sem busy-loop na CPU 0).
- GPIO via `gpio_config` / `GPIO_NUM_*` (não números mágicos sem macro).
- ADC com atenuação documentada; I2C/SPI com pins compatíveis com a placa escolhida.
- MQTT: broker em `mqtt://` ou `mqtts://`, client id estável, reconnect com backoff.
- Versão alvo: **ESP-IDF v5.3** citada em comentário ou `idf_component.yml`.

Domínio RAG: `esp_idf` · Linguagem sandbox: `cpp_embedded` · Arquivo típico: `main.c` ou `app_main.c`.

---

## 3. Interface tátil — LVGL v9

Domínio `lvgl_v9` · Linguagem: `cpp_embedded` / C.

- API **LVGL v9** (`lv_obj_*`, `lv_screen_load`, sem APIs removidas da v8).
- Um display flush callback registrado; buffer em DMA-capable quando aplicável.
- Touch: eixo alinhado ao `hardware_linter` da placa display.
- Sem alocação ilimitada em loop de render (tick `lv_timer_handler` em task dedicada).

---

## 4. Contrato determinístico de saída (YBY SEED)

Toda resposta **aprovada** para dataset ou missão Vibe Coding deve conter, nesta ordem:

### 4.1 Bloco `hardware_check` (YAML)

```yaml
hardware_check:
  board: esp32_s3_devkitc1
  domain: esp_idf
  idf_version: "5.3"
  gpio_claims:
    - gpio: 4
      role: led_status
  modbus:
    enabled: false
  linter_expected: true
```

### 4.2 Bloco de código validado

Fenced code com linguagem correta (`c`, `cpp`, ou `python`). Exemplo mínimo ESP-IDF:

```c
// board: esp32_s3_devkitc1
#include "freertos/FreeRTOS.h"
void app_main(void) { }
```

### 4.3 Mensagem ChatML (dataset)

| role | conteúdo |
|---|---|
| `system` | Referência a este contrato + domínio |
| `user` | `user_intent` em português |
| `assistant` | YAML `hardware_check` + bloco de código (texto integral) |

Somente amostras que passam **sandbox + hardware_linter** entram em `data/datasets/validated_pairs.jsonl` (dedupe SHA-256).

---

## 5. Domínios Python / industrial

| Domínio | Linguagem | Foco |
|---|---|---|
| `python_fastapi` | `python` | API local, testes pytest |
| `modbus_rtu` | `python` | pymodbus/serial ou framing manual com CRC |

---

## 6. Ingestão pgvector

- Ingerir este arquivo e variantes por placa:  
  `uv run python -m src.yby_seed.memory.ingest --dir ./docs --domain yby_arch`
- Chunks referenciam `source_file: yby_seed_contracts.md` para o Architect.
