#pragma once

#include <stdint.h>
#include <functional>

enum class LinkMode : uint8_t {
    OFFLINE = 0,
    HUB_PRIMARY = 1,
    XIAOMI_FAILOVER = 2,
};

using AudioStateCallback = std::function<void(const char* state)>;
using CommandCallback = std::function<void(const char* cmd, const char* text, const char* accent_hex)>;

class MqttMeshClient {
public:
    void begin(AudioStateCallback on_audio_state, CommandCallback on_command);
    void loop(uint32_t now_ms);

    bool publishTelemetry(int battery_pct, bool charging, const char* audio_state);
    bool publishVoiceShortcut(const char* transcript);

    bool isConnected();
    LinkMode linkMode() const { return link_mode_; }
    const char* linkLabel() const;

private:
    bool ensureWifi(uint32_t now_ms);
    bool ensureMqtt(uint32_t now_ms);
    void handleIncoming(char* topic, uint8_t* payload, unsigned int length);

    LinkMode link_mode_ = LinkMode::OFFLINE;
    bool using_failover_ = false;
    uint32_t wifi_attempt_started_ms_ = 0;
    uint32_t last_mqtt_attempt_ms_ = 0;
    AudioStateCallback on_audio_state_;
    CommandCallback on_command_;
};
