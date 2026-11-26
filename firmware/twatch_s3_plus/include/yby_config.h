#pragma once

#define YBY_FW_VERSION "0.1.0-module-c"
#define YBY_DEVICE_ID "twatch-s3-plus-01"

// Escolhas arquiteturais consolidadas (D16)
#define YBY_ENABLE_LORA 0
#define YBY_ENABLE_GNSS 0
#define YBY_ENABLE_BLE 0
#define YBY_ENABLE_MIC 0

// Display ST7789V3 (240x240)
#define YBY_DISP_WIDTH 240
#define YBY_DISP_HEIGHT 240
#define YBY_DISP_CS 12
#define YBY_DISP_MOSI 13
#define YBY_DISP_SCK 18
#define YBY_DISP_DC 38
#define YBY_DISP_BL 45

// Barramento I2C Principal (AXP2101 0x34, BMA423 0x19, PCF8563 0x51, DRV2605 0x5A)
#define YBY_I2C_SDA 10
#define YBY_I2C_SCL 11

// Barramento I2C Touch FT6336U (0x38, Wire1)
#define YBY_TOUCH_SDA 39
#define YBY_TOUCH_SCL 40
#define YBY_TOUCH_INT 16

// Interrupcoes de wake-up (4A)
#define YBY_BMA_INT 14
#define YBY_PMU_INT 21

// Politica de energia em 3 estagios (4A)
#define YBY_LIGHT_SLEEP_MS 10000
#define YBY_DEEP_SLEEP_MS 300000
#define YBY_TELEMETRY_INTERVAL_MS 30000

// Paleta Nothing OS / CMF (3A / 5A)
#define YBY_COLOR_BG 0x0D0D0D
#define YBY_COLOR_FG 0xF5F5F2
#define YBY_COLOR_ACCENT 0x00FF66
#define YBY_COLOR_SURFACE 0x1A1A1A

// Topicos MQTT (src/yby/audio/schemas.py)
#define YBY_TOPIC_AUDIO_STATE "yby/audio/state"
#define YBY_TOPIC_TELEMETRY "yby/nodes/twatch/telemetry"
#define YBY_TOPIC_CMD "yby/nodes/twatch/cmd"
#define YBY_TOPIC_VOICE "yby/nodes/twatch/voice"

// Failover Wi-Fi -> Xiaomi 12 (1A)
#define YBY_WIFI_CONNECT_TIMEOUT_MS 8000
#define YBY_MQTT_RETRY_INTERVAL_MS 5000

// Atalhos de texto pre-definidos (2C)
#define YBY_SHORTCUT_COUNT 4
static const char* const YBY_VOICE_SHORTCUTS[YBY_SHORTCUT_COUNT] = {
    "Resumo do dia",
    "Status da malha",
    "Sincronizar notas",
    "Silenciar alertas",
};
