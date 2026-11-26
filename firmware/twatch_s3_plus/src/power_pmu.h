#pragma once

#include <stdint.h>

enum class PowerStage : uint8_t {
    ACTIVE = 0,
    LIGHT_SLEEP = 1,
    DEEP_SLEEP = 2,
};

class PowerPmuManager {
public:
    bool begin();
    void update(uint32_t now_ms, bool mqtt_busy);
    void notifyInteraction(uint32_t now_ms);
    void wakeScreen();
    void enterDeepSleep();

    int batteryPercent() const;
    bool isCharging() const;
    PowerStage stage() const { return stage_; }
    bool isScreenOn() const { return screen_on_; }

private:
    void setBacklight(bool enabled);

    bool initialized_ = false;
    bool screen_on_ = true;
    PowerStage stage_ = PowerStage::ACTIVE;
    uint32_t last_interaction_ms_ = 0;
};
