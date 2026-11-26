#pragma once

#include <stdint.h>

class HapticFeedback {
public:
    bool begin();
    void playAudioState(const char* state);
    void playAlertDoublePulse();
    void playShortClick();

private:
    void playWaveform(uint8_t effect_a, uint8_t effect_b = 0);

    bool initialized_ = false;
};
