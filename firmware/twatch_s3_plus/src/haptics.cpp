#include "haptics.h"

#include <Wire.h>
#include <SensorDRV2605.hpp>
#include <string.h>

static SensorDRV2605 s_drv;

bool HapticFeedback::begin() {
    if (!s_drv.begin(Wire)) {
        return false;
    }
    s_drv.selectLibrary(1);
    s_drv.setMode(SensorDRV2605::MODE_INTTRIG);
    s_drv.useERM();
    initialized_ = true;
    return true;
}

void HapticFeedback::playWaveform(uint8_t effect_a, uint8_t effect_b) {
    if (!initialized_) {
        return;
    }
    s_drv.setWaveform(0, effect_a);
    if (effect_b > 0) {
        s_drv.setWaveform(1, 134);  // pausa curta (wait ~60ms)
        s_drv.setWaveform(2, effect_b);
        s_drv.setWaveform(3, 0);
    } else {
        s_drv.setWaveform(1, 0);
    }
    s_drv.run();
}

void HapticFeedback::playShortClick() {
    playWaveform(1);  // Strong Click 100%
}

void HapticFeedback::playAlertDoublePulse() {
    playWaveform(14, 14);  // Pulso duplo para haptic_pulse / yby_machine
}

void HapticFeedback::playAudioState(const char* state) {
    if (state == nullptr) {
        return;
    }
    if (strcmp(state, "listening") == 0) {
        playShortClick();
    } else if (strcmp(state, "thinking") == 0) {
        playWaveform(24);  // Micro-tick discreto
    } else if (strcmp(state, "speaking") == 0) {
        playWaveform(47);  // Buzz suave de inicio de fala
    }
}
