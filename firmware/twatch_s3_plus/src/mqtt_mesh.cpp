#include "mqtt_mesh.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <esp_bt.h>

#include "yby_config.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

static WiFiClient s_wifi_client;
static PubSubClient s_mqtt_client(s_wifi_client);

void MqttMeshClient::begin(AudioStateCallback on_audio_state, CommandCallback on_command) {
    on_audio_state_ = on_audio_state;
    on_command_ = on_command;

#if YBY_ENABLE_BLE == 0
    // 1A: BLE desligado por padrao para preservar heap e estabilidade Wi-Fi
    btStop();
#endif

    WiFi.mode(WIFI_STA);
    WiFi.setSleep(WIFI_PS_MIN_MODEM);
    s_mqtt_client.setBufferSize(1024);
    s_mqtt_client.setCallback([this](char* topic, uint8_t* payload, unsigned int length) {
        this->handleIncoming(topic, payload, length);
    });

    using_failover_ = false;
    wifi_attempt_started_ms_ = millis();
    WiFi.begin(YBY_WIFI_PRIMARY_SSID, YBY_WIFI_PRIMARY_PASS);
}

bool MqttMeshClient::ensureWifi(uint32_t now_ms) {
    if (WiFi.status() == WL_CONNECTED) {
        link_mode_ = using_failover_ ? LinkMode::XIAOMI_FAILOVER : LinkMode::HUB_PRIMARY;
        return true;
    }

    link_mode_ = LinkMode::OFFLINE;
    if (now_ms - wifi_attempt_started_ms_ >= YBY_WIFI_CONNECT_TIMEOUT_MS) {
        // 1A: failover automatico entre PC Hub e Xiaomi 12
        using_failover_ = !using_failover_;
        wifi_attempt_started_ms_ = now_ms;
        WiFi.disconnect(false);
        if (using_failover_) {
            WiFi.begin(YBY_WIFI_FAILOVER_SSID, YBY_WIFI_FAILOVER_PASS);
        } else {
            WiFi.begin(YBY_WIFI_PRIMARY_SSID, YBY_WIFI_PRIMARY_PASS);
        }
    }
    return false;
}

bool MqttMeshClient::ensureMqtt(uint32_t now_ms) {
    if (s_mqtt_client.connected()) {
        return true;
    }
    if (now_ms - last_mqtt_attempt_ms_ < YBY_MQTT_RETRY_INTERVAL_MS) {
        return false;
    }
    last_mqtt_attempt_ms_ = now_ms;

    const char* broker_host = using_failover_ ? YBY_MQTT_FAILOVER_HOST : YBY_MQTT_PRIMARY_HOST;
    const uint16_t broker_port = using_failover_ ? YBY_MQTT_FAILOVER_PORT : YBY_MQTT_PRIMARY_PORT;
    s_mqtt_client.setServer(broker_host, broker_port);

    bool ok = false;
    if (strlen(YBY_MQTT_USER) > 0) {
        ok = s_mqtt_client.connect(YBY_DEVICE_ID, YBY_MQTT_USER, YBY_MQTT_PASS);
    } else {
        ok = s_mqtt_client.connect(YBY_DEVICE_ID);
    }

    if (ok) {
        s_mqtt_client.subscribe(YBY_TOPIC_AUDIO_STATE, 1);
        s_mqtt_client.subscribe(YBY_TOPIC_CMD, 1);
    }
    return ok;
}

void MqttMeshClient::loop(uint32_t now_ms) {
    if (!ensureWifi(now_ms)) {
        return;
    }
    if (ensureMqtt(now_ms)) {
        s_mqtt_client.loop();
    }
}

void MqttMeshClient::handleIncoming(char* topic, uint8_t* payload, unsigned int length) {
    if (topic == nullptr || payload == nullptr || length == 0) {
        return;
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload, length);
    if (err) {
        return;
    }

    if (strcmp(topic, YBY_TOPIC_AUDIO_STATE) == 0) {
        const char* state = doc["state"] | "idle";
        if (on_audio_state_) {
            on_audio_state_(state);
        }
        return;
    }

    if (strcmp(topic, YBY_TOPIC_CMD) == 0) {
        const char* cmd = doc["command"] | "display_text";
        const char* text = doc["text"] | "";
        const char* accent = doc["accent_color"] | "#00FF66";
        const char* state = doc["state"] | "";
        if (on_command_) {
            on_command_(cmd, text, accent, state);
        }
    }
}

bool MqttMeshClient::publishTelemetry(int battery_pct, bool charging, const char* audio_state) {
    if (!s_mqtt_client.connected()) {
        return false;
    }
    JsonDocument doc;
    doc["device_id"] = YBY_DEVICE_ID;
    doc["battery_pct"] = battery_pct;
    doc["charging"] = charging;
    doc["wifi_rssi"] = WiFi.RSSI();
    doc["state"] = audio_state != nullptr ? audio_state : "idle";

    char buf[256];
    size_t len = serializeJson(doc, buf, sizeof(buf));
    return s_mqtt_client.publish(YBY_TOPIC_TELEMETRY, reinterpret_cast<const uint8_t*>(buf), len, false);
}

bool MqttMeshClient::publishVoiceShortcut(const char* transcript) {
    if (!s_mqtt_client.connected() || transcript == nullptr) {
        return false;
    }
    // 2C: TWatchVoiceEnvelope sem audio bruto (audio_b64 = null, sensitivity = private)
    JsonDocument doc;
    doc["device_id"] = YBY_DEVICE_ID;
    doc["transcript"] = transcript;
    doc["audio_b64"] = nullptr;
    doc["sample_rate"] = 16000;
    doc["sensitivity"] = "private";

    char buf[320];
    size_t len = serializeJson(doc, buf, sizeof(buf));
    return s_mqtt_client.publish(YBY_TOPIC_VOICE, reinterpret_cast<const uint8_t*>(buf), len, false);
}

bool MqttMeshClient::isConnected() {
    return WiFi.status() == WL_CONNECTED && s_mqtt_client.connected();
}

const char* MqttMeshClient::linkLabel() const {
    switch (link_mode_) {
        case LinkMode::HUB_PRIMARY:
            return "HUB";
        case LinkMode::XIAOMI_FAILOVER:
            return "XIAOMI";
        default:
            return "OFFLINE";
    }
}
