#include "power_pmu.h"

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <XPowersLib.h>
#include <esp_sleep.h>

#include "yby_config.h"

static XPowersAXP2101 s_pmu;

bool PowerPmuManager::begin() {
    Wire.begin(YBY_I2C_SDA, YBY_I2C_SCL);
    if (!s_pmu.begin(Wire, AXP2101_SLAVE_ADDRESS, YBY_I2C_SDA, YBY_I2C_SCL)) {
        return false;
    }

    // Trilhas essenciais: display, touch e DRV2605
    s_pmu.setALDO2Voltage(3300);
    s_pmu.setALDO3Voltage(3300);
    s_pmu.setBLDO2Voltage(3300);
    s_pmu.enableALDO2();
    s_pmu.enableALDO3();
    s_pmu.enableBLDO2();

    // MVP estritamente SEM LoRa (ALDO4) e SEM GNSS (BLDO1 / DC3)
    s_pmu.disableALDO4();
    s_pmu.disableBLDO1();
    s_pmu.disableDC3();
    s_pmu.disableDC2();
    s_pmu.disableDC4();
    s_pmu.disableDC5();
    s_pmu.disableALDO1();
    s_pmu.disableDLDO1();
    s_pmu.disableDLDO2();

    // Carga segura recomendada para bateria 1500mAh (<= 130 mA)
    s_pmu.setPrechargeCurr(XPOWERS_AXP2101_PRECHARGE_50MA);
    s_pmu.setChargerConstantCurr(XPOWERS_AXP2101_CHG_CUR_125MA);
    s_pmu.setChargerTerminationCurr(XPOWERS_AXP2101_CHG_ITERM_25MA);
    s_pmu.setChargeTargetVoltage(XPOWERS_AXP2101_CHG_VOL_4V2);

    s_pmu.enableBattDetection();
    s_pmu.enableVbusVoltageMeasure();
    s_pmu.enableBattVoltageMeasure();
    s_pmu.enableSystemVoltageMeasure();

    s_pmu.disableIRQ(XPOWERS_AXP2101_ALL_IRQ);
    s_pmu.enableIRQ(XPOWERS_AXP2101_PKEY_SHORT_IRQ | XPOWERS_AXP2101_PKEY_LONG_IRQ);
    s_pmu.clearIrqStatus();

    pinMode(YBY_PMU_INT, INPUT_PULLUP);
    pinMode(YBY_TOUCH_INT, INPUT_PULLUP);
    pinMode(YBY_BMA_INT, INPUT_PULLUP);
    pinMode(YBY_DISP_BL, OUTPUT);
    setBacklight(true);

    initialized_ = true;
    last_interaction_ms_ = millis();
    stage_ = PowerStage::ACTIVE;
    return true;
}

void PowerPmuManager::setBacklight(bool enabled) {
    screen_on_ = enabled;
    digitalWrite(YBY_DISP_BL, enabled ? HIGH : LOW);
    if (initialized_) {
        if (enabled) {
            s_pmu.enableALDO2();
        } else {
            s_pmu.disableALDO2();
        }
    }
}

void PowerPmuManager::notifyInteraction(uint32_t now_ms) {
    last_interaction_ms_ = now_ms;
    if (!screen_on_ || stage_ != PowerStage::ACTIVE) {
        wakeScreen();
    }
}

void PowerPmuManager::wakeScreen() {
    setBacklight(true);
    stage_ = PowerStage::ACTIVE;
}

void PowerPmuManager::update(uint32_t now_ms, bool mqtt_busy) {
    if (initialized_ && digitalRead(YBY_PMU_INT) == LOW) {
        s_pmu.getIrqStatus();
        if (s_pmu.isPekeyShortPressIrq()) {
            notifyInteraction(now_ms);
        }
        s_pmu.clearIrqStatus();
    }

    uint32_t idle_ms = now_ms - last_interaction_ms_;
    if (stage_ == PowerStage::ACTIVE && idle_ms >= YBY_LIGHT_SLEEP_MS) {
        // Estagio 2 (4A): apaga tela mantendo Wi-Fi em modem-sleep + MQTT vivo
        setBacklight(false);
        WiFi.setSleep(WIFI_PS_MIN_MODEM);
        stage_ = PowerStage::LIGHT_SLEEP;
    } else if (stage_ == PowerStage::LIGHT_SLEEP && !mqtt_busy && idle_ms >= YBY_DEEP_SLEEP_MS) {
        enterDeepSleep();
    }
}

void PowerPmuManager::enterDeepSleep() {
    stage_ = PowerStage::DEEP_SLEEP;
    setBacklight(false);

    if (initialized_) {
        s_pmu.disableALDO3();
        s_pmu.disableBLDO2();
        s_pmu.disableALDO4();
        s_pmu.disableBLDO1();
        s_pmu.clearIrqStatus();
    }

    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);

    // Wake por botao PWR (GPIO21), toque FT6336U (GPIO16) ou movimento BMA423 (GPIO14)
    const uint64_t wake_mask = (1ULL << YBY_BMA_INT) | (1ULL << YBY_TOUCH_INT) | (1ULL << YBY_PMU_INT);
    esp_sleep_enable_ext1_wakeup(wake_mask, ESP_EXT1_WAKEUP_ALL_LOW);
    esp_deep_sleep_start();
}

int PowerPmuManager::batteryPercent() const {
    if (!initialized_ || !s_pmu.isBatteryConnect()) {
        return 100;
    }
    int pct = s_pmu.getBatteryPercent();
    if (pct < 0) return 0;
    if (pct > 100) return 100;
    return pct;
}

bool PowerPmuManager::isCharging() const {
    if (!initialized_) {
        return false;
    }
    return s_pmu.isCharging();
}
