"""
Firmware Configuration — LilyGO T-Watch S3 Plus (ESP32-S3)

Responsabilidade:
- Configurações de Wi-Fi, MQTT, sensores
- IDs únicos por dispositivo
- Timeouts e intervalos

Licença: MIT
"""

#ifndef CONFIG_H
#define CONFIG_H

// === Device Identification ===
#define DEVICE_ID "yby-watch-001"  // Único por dispositivo
#define DEVICE_NAME "YBY Watch S3 Plus"
#define FIRMWARE_VERSION "1.1.0"

// === Wi-Fi ===
#define WIFI_SSID "your_wifi_ssid"
#define WIFI_PASSWORD "your_wifi_password"
#define WIFI_CONNECT_TIMEOUT 10000  // 10 segundos

// === MQTT ===
#define MQTT_BROKER_HOST "broker.yby.local"
#define MQTT_BROKER_PORT 1883
#define MQTT_CLIENT_ID DEVICE_ID
#define MQTT_USER ""  // Opcional
#define MQTT_PASSWORD ""  // Opcional

// Tópicos MQTT
#define MQTT_TOPIC_TELEMETRY "yby/telemetry"
#define MQTT_TOPIC_STATUS "yby/status"
#define MQTT_TOPIC_COMMANDS "yby/commands"

// MQTT+TLS (habilitar em produção)
// #define MQTT_SECURE
// #define MQTT_CA_CERT "-----BEGIN CERTIFICATE-----\n..."

// === Publish Interval ===
#define PUBLISH_INTERVAL 30000  // 30 segundos

// === Deep Sleep ===
#define DEEP_SLEEP_TIMEOUT 300000  // 5 minutos
#define WAKEUP_SOURCE_TIMER  // Wake-up por timer

// === Sensors ===
#define SENSOR_HEART_RATE_PIN 4  // GPIO para MAX30102
#define SENSOR_SPO2_PIN 5  // GPIO para MAX30102
#define SENSOR_ACCEL_PIN 6  // GPIO para BMM150

// === Display (LVGL) ===
#define DISPLAY_WIDTH 240
#define DISPLAY_HEIGHT 240
#define DISPLAY_BACKLIGHT_PIN 10
#define DISPLAY_BACKLIGHT_PWM_CHANNEL 0
#define DISPLAY_BACKLIGHT_FREQ 5000
#define DISPLAY_BACKLIGHT_DUTY 128  // 50% brilho

// === Power ===
#define BATTERY_ADC_PIN 1
#define BATTERY_ADC_ATTEN ADC_ATTEN_DB_11
#define BATTERY_LOW_THRESHOLD 20  // 20%
#define BATTERY_CRITICAL_THRESHOLD 5  // 5%

// === NVS (Non-Volatile Storage) ===
#define NVS_NAMESPACE "yby"
#define NVS_KEY_TELEMETRY_BUFFER "tele_buf"
#define NVS_KEY_CONFIG "config"

// === Debug ===
#define DEBUG_SERIAL_SPEED 115200
#define DEBUG_HEAP_TRACING 1
#define DEBUG_COREDUMP_ENABLE 1

// === Logging ===
#define LOG_LEVEL_DEBUG 0
#define LOG_LEVEL_INFO 1
#define LOG_LEVEL_WARN 2
#define LOG_LEVEL_ERROR 3
#define LOG_LEVEL LOG_LEVEL_INFO

// Macros de log
#if LOG_LEVEL <= LOG_LEVEL_DEBUG
  #define LOG_DEBUG(...) Serial.printf(__VA_ARGS__)
#else
  #define LOG_DEBUG(...)
#endif

#if LOG_LEVEL <= LOG_LEVEL_INFO
  #define LOG_INFO(...) Serial.printf(__VA_ARGS__)
#else
  #define LOG_INFO(...)
#endif

#if LOG_LEVEL <= LOG_LEVEL_WARN
  #define LOG_WARN(...) Serial.printf(__VA_ARGS__)
#else
  #define LOG_WARN(...)
#endif

#if LOG_LEVEL <= LOG_LEVEL_ERROR
  #define LOG_ERROR(...) Serial.printf(__VA_ARGS__)
#else
  #define LOG_ERROR(...)
#endif

#endif // CONFIG_H
