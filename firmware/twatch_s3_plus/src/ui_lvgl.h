#pragma once

#include <stdint.h>
#include <functional>

using ShortcutCallback = std::function<void(const char* transcript)>;
using InteractionCallback = std::function<void()>;

class UiLvglManager {
public:
    void begin(ShortcutCallback on_shortcut, InteractionCallback on_interaction);
    void tick();

    void updateStatus(
        const char* time_str,
        const char* audio_state,
        int battery_pct,
        bool charging,
        const char* link_label
    );
    void setLastReply(const char* text);
    void showAlert(const char* text, const char* accent_hex);
    void clearAlert();

private:
    ShortcutCallback on_shortcut_;
    InteractionCallback on_interaction_;
};
