#include <Arduino.h>
#include <SensorPCF8563.hpp>
#include <Wire.h>
#include <stdio.h>
#include <string.h>

#include "haptics.h"
#include "mqtt_mesh.h"
#include "power_pmu.h"
#include "ui_lvgl.h"
#include "yby_config.h"

static PowerPmuManager g_pmu;
static HapticFeedback g_haptics;
static MqttMeshClient g_mqtt;
static UiLvglManager g_ui;
static SensorPCF8563 g_rtc;

static bool g_rtc_ready = false;
static char g_audio_state[24] = "idle";
static uint32_t g_last_telemetry_ms = 0;
static uint32_t g_last_ui_refresh_ms = 0;

static void formatClockText(char* out, size_t out_len) {
    if (g_rtc_ready) {
        RTC_DateTime dt = g_rtc.getDateTime();
        snprintf(out, out_len, "%02u:%02u", dt.getHour(), dt.getMinute());
        return;
    }
    uint32_t secs = millis() / 1000UL;
    uint32_t mins = (secs / 60UL) % 60UL;
    uint32_t hrs = (secs / 3600UL) % 24UL;
    snprintf(out, out_len, "%02lu:%02lu", static_cast<unsigned long>(hrs), static_cast<unsigned long>(mins));
}

void setup() {
    Serial.begin(115200);
    delay(150);

    g_pmu.begin();
    g_haptics.begin();
    g_rtc_ready = g_rtc.begin(Wire, PCF8563_SLAVE_ADDRESS);

    g_ui.begin(
        [](const char* transcript) {
            g_pmu.notifyInteraction(millis());
            g_haptics.playShortClick();
            g_mqtt.publishVoiceShortcut(transcript);
        },
        []() {
            g_pmu.notifyInteraction(millis());
        }
    );

    g_mqtt.begin(
        [](const char* state) {
            if (state != nullptr) {
                strncpy(g_audio_state, state, sizeof(g_audio_state) - 1);
                g_audio_state[sizeof(g_audio_state) - 1] = '\0';
            }
            if (strcmp(g_audio_state, "idle") != 0) {
                g_pmu.notifyInteraction(millis());
            }
            g_haptics.playAudioState(g_audio_state);
        },
        [](const char* cmd, const char* text, const char* accent_hex) {
            g_pmu.notifyInteraction(millis());
            if (strcmp(cmd, "haptic_pulse") == 0) {
                g_haptics.playAlertDoublePulse();
                g_ui.showAlert(text, accent_hex);
            } else if (strcmp(cmd, "display_text") == 0) {
                g_haptics.playShortClick();
                g_ui.setLastReply(text);
                g_ui.showAlert(text, accent_hex);
            } else if (strcmp(cmd, "set_state") == 0 && text != nullptr && strlen(text) > 0) {
                strncpy(g_audio_state, text, sizeof(g_audio_state) - 1);
                g_audio_state[sizeof(g_audio_state) - 1] = '\0';
            }
        }
    );
}

void loop() {
    uint32_t now = millis();
    g_mqtt.loop(now);

    bool busy = (strcmp(g_audio_state, "idle") != 0);
    g_pmu.update(now, busy);

    if (now - g_last_ui_refresh_ms >= 250) {
        g_last_ui_refresh_ms = now;
        char clock_buf[8];
        formatClockText(clock_buf, sizeof(clock_buf));
        g_ui.updateStatus(
            clock_buf,
            g_audio_state,
            g_pmu.batteryPercent(),
            g_pmu.isCharging(),
            g_mqtt.linkLabel()
        );
    }

    if (now - g_last_telemetry_ms >= YBY_TELEMETRY_INTERVAL_MS) {
        g_last_telemetry_ms = now;
        g_mqtt.publishTelemetry(g_pmu.batteryPercent(), g_pmu.isCharging(), g_audio_state);
    }

    if (g_pmu.isScreenOn()) {
        g_ui.tick();
        delay(5);
    } else {
        delay(50);
    }
}
