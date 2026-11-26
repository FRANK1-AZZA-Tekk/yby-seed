#pragma once

// Copie este arquivo para `secrets.h` (ignorado pelo git) e preencha suas credenciais locais.

// 1A — Rede primaria: PC Hub (desktop-yby)
#define YBY_WIFI_PRIMARY_SSID "SEU_WIFI_CASA"
#define YBY_WIFI_PRIMARY_PASS "SUA_SENHA_CASA"
#define YBY_MQTT_PRIMARY_HOST "192.168.1.100"
#define YBY_MQTT_PRIMARY_PORT 1883

// 1A — Failover automatico: Xiaomi 12 (Termux Mosquitto / hotspot)
#define YBY_WIFI_FAILOVER_SSID "Xiaomi12_Hotspot"
#define YBY_WIFI_FAILOVER_PASS "SUA_SENHA_HOTSPOT"
#define YBY_MQTT_FAILOVER_HOST "192.168.43.1"
#define YBY_MQTT_FAILOVER_PORT 1883

// Credenciais opcionais do broker Mosquitto
#define YBY_MQTT_USER ""
#define YBY_MQTT_PASS ""
