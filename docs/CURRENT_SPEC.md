# Especificação Atual — Módulo C (`LILYGO T-Watch S3 Plus`)

Documento vivo consolidando as escolhas arquiteturais aprovadas (**D16**: `1A, 2C, 3A, 4A, 5A, 6A`) para integração do wearable de pulso à malha de 4 nós do **YBY SEED**.

## 1. Topologia e Conectividade (`1A`)

- **Modo de rádio:** Wi-Fi `WIFI_STA` com BLE desativado por padrão (preserva heap e evita conflito de antena).
- **Broker primário:** Mosquitto no PC Hub (`desktop-yby`, porta `1883`).
- **Failover automático:** caso o SSID ou broker primário falhe após as tentativas configuradas, o firmware alterna para o hotspot/broker Mosquitto do Xiaomi 12 (Termux).
- **Segredos locais:** definidos em `firmware/twatch_s3_plus/include/secrets.h` (ignorado pelo git), copiado de `firmware/twatch_s3_plus/include/secrets.example.h`.

## 2. Contrato MQTT e Fluxo de Voz (`2C`)

O microfone PDM (`SPM1423HM4H-B`) e o amplificador PCM (`MAX98357A`) ficam **desativados** no MVP; captura e resposta sonora continuam no **Baseus Bowie MC2 Air** (Módulo B). O relógio atua como controle rápido de pulso usando exatamente os schemas Pydantic de `src/yby/audio/schemas.py`:

- **Assinaturas no relógio (QoS 1):**
  - `yby/audio/state` (`AudioStateEvent`, `retain=True`): `state` em `{"listening", "thinking", "speaking", "idle"}`.
  - `yby/nodes/twatch/cmd` (`TWatchCommand`): `command` em `{"display_text", "haptic_pulse", "set_state", "ping"}`, `text` (até 160 chars), `accent_color` em `{"#00FF66", "#F5F5F2", "#0D0D0D"}`, `state`.
- **Publicações do relógio (QoS 1):**
  - `yby/nodes/twatch/telemetry` (`TWatchTelemetry`): `device_id`, `battery_pct` (`0..100`), `charging`, `wifi_rssi`, `state`, `timestamp`.
  - `yby/nodes/twatch/voice` (`TWatchVoiceEnvelope`): atalho de texto (`transcript` preenchido, `audio_b64: null`, `sensitivity: "private"`).
- **Ponte Hub-side (`src/yby/audio/twatch_bridge.py`):**
  - Recebe `TWatchVoiceEnvelope` com `transcript` (atalho `2C`), roteia pelo `CognitiveRouter` com `sensitivity="private"` (D12 / `PrivacyGate` fail-closed) e publica `TWatchCommand(command="display_text", ...)` em `yby/nodes/twatch/cmd`.
  - Converte notificações do `yby_machine` em `TWatchCommand(command="haptic_pulse", ...)` com destaque `#00FF66`.

## 3. Interface LVGL (`3A`) e Estética Nothing OS / CMF

- **Display / Touch:** `ST7789V3` 240x240 (SPI) + `FT6336U` (I2C `Wire1`, endereço `0x38`).
- **Paleta:** fundo `#0D0D0D`, texto/arco ativo `#F5F5F2`, acento/alerta `#00FF66`.
- **Carrossel horizontal (`lv_tileview`, 3 telas):**
  - **Tela 1 — Status:** hora em estética dot-matrix, arco segmentado de `yby/audio/state`, porcentagem/ícone de bateria (`AXP2101`) e indicador de nó MQTT ativo (`HUB` / `XIAOMI` / `OFFLINE`).
  - **Tela 2 — Atalhos (`2C`):** lista tátil de comandos rápidos (`Resumo do dia`, `Status da malha`, `Sincronizar notas`, `Silenciar alertas`) enviando `TWatchVoiceEnvelope` para `yby/nodes/twatch/voice`, mais cartão do último `display_text`.
  - **Tela 3 — Alertas (`5A`):** card de notificação (`yby_machine` / `yby/nodes/twatch/cmd`) com botões `OK` e `Dismiss`.

## 4. Pinout Validado (`LILYGO T-Watch S3 Plus`) e Hardware Desabilitado

- **I2C Principal (`Wire`, `0x34` AXP2101, `0x19` BMA423, `0x51` PCF8563, `0x5A` DRV2605):** `SDA=10`, `SCL=11`.
- **Touch (`Wire1`, `0x38` FT6336U):** `SDA=39`, `SCL=40`, `INT=16` (sem pino `RST` conectado).
- **Display (`ST7789V3`):** `CS=12`, `MOSI=13`, `SCK=18`, `DC=38`, `BL=45` (`MISO=-1`, `RST=-1`).
- **Interrupções:** `BMA423=14`, `FT6336U=16`, `AXP2101=21`.
- **Estágio MVP sem LoRa / sem GNSS / sem áudio no pulso:** `SX1262` (GPIOs 1/3/4/5/7/8/9 e `ALDO4`), `MIA-M10Q` (GPIOs 41/42 e `BLDO1`), `SPM1423HM4H-B` (GPIOs 44/47) e `MAX98357A` (GPIOs 15/46/48) **não** são inicializados.

## 5. Energia (`4A`) e Háptico (`5A`)

- **Carga segura AXP2101:** corrente limitada a `100–130 mA` (proteção da bateria de 1500 mAh); `ALDO4` e `BLDO1` desligados no boot.
- **Máquina de energia (3 estágios):**
  1. `ACTIVE`: tela ligada (backlight ativo).
  2. `LIGHT_SLEEP` (após `10 s` sem interação): desliga backlight (`ALDO2` / PWM GPIO45), mantém `WIFI_PS_MIN_MODEM` para preservar MQTT e acorda instantaneamente por IRQ/toque/evento MQTT.
  3. `DEEP_SLEEP` (após `300 s` ocioso): desliga Wi-Fi e periféricos de tela, configurando wake via `ext1` nos pinos de interrupção ativos (`GPIO14` BMA423, `GPIO16` FT6336U, `GPIO21` AXP2101 PWR).
- **Feedback háptico (`DRV2605`, `BLDO2` habilitado):**
  - `listening`: pulso curto (efeito `#1` sharp click) + arco `#00FF66`.
  - `thinking`: micro-tick discreto (efeito `#24` tick) + segmento pulsante.
  - `speaking`: arco sólido `#F5F5F2`.
  - `haptic_pulse` / alerta `yby_machine`: pulso duplo (efeitos `#14` + pausa curta + `#14`) + abertura da Tela 3.

## 6. Automação CLI USB (`6A`)

Scripts em `scripts/twatch/` e alvos no `Makefile`:

- `make twatch-backup` (`python -m scripts.twatch.backup`): executa `esptool.py` lendo os `16 MB` (`0x1000000`) da flash para `backups/twatch/twatch-s3-plus-<timestamp>.bin` e grava `<arquivo>.sha256`.
- `make twatch-build` (`python -m scripts.twatch.build`): executa `pio run -d firmware/twatch_s3_plus`.
- `make twatch-flash` (`python -m scripts.twatch.flash`): verifica a existência e integridade SHA-256 de um backup recente antes de rodar `pio run -d firmware/twatch_s3_plus -t upload` (aceita `--skip-backup` explícito para contornar a trava).
- `make twatch-monitor` (`python -m scripts.twatch.monitor`): abre o monitor serial em `115200` bps.
