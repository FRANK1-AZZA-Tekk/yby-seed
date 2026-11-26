#include "ui_lvgl.h"

#include <Arduino.h>
#include <TFT_eSPI.h>
#include <TouchDrvFT6X36.hpp>
#include <Wire.h>
#include <lvgl.h>
#include <string.h>

#include "yby_config.h"

static TFT_eSPI s_tft = TFT_eSPI();
static TouchDrvFT6X36 s_touch;

static lv_disp_draw_buf_t s_draw_buf;
static lv_color_t s_buf1[YBY_DISP_WIDTH * 24];

static lv_obj_t* s_tileview = nullptr;
static lv_obj_t* s_tile_status = nullptr;
static lv_obj_t* s_tile_shortcuts = nullptr;
static lv_obj_t* s_tile_alerts = nullptr;

static lv_obj_t* s_arc_state = nullptr;
static lv_obj_t* s_lbl_clock = nullptr;
static lv_obj_t* s_lbl_state = nullptr;
static lv_obj_t* s_lbl_batt = nullptr;
static lv_obj_t* s_lbl_link = nullptr;
static lv_obj_t* s_lbl_reply = nullptr;
static lv_obj_t* s_lbl_alert = nullptr;

static ShortcutCallback s_shortcut_cb;
static InteractionCallback s_interaction_cb;

static void dispFlushCb(lv_disp_drv_t* disp, const lv_area_t* area, lv_color_t* color_p) {
    uint32_t w = static_cast<uint32_t>(area->x2 - area->x1 + 1);
    uint32_t h = static_cast<uint32_t>(area->y2 - area->y1 + 1);

    s_tft.startWrite();
    s_tft.setAddrWindow(area->x1, area->y1, w, h);
    s_tft.pushColors(reinterpret_cast<uint16_t*>(&color_p->full), w * h, true);
    s_tft.endWrite();

    lv_disp_flush_ready(disp);
}

static void touchReadCb(lv_indev_drv_t* indev_drv, lv_indev_data_t* data) {
    (void)indev_drv;
    int16_t x = 0;
    int16_t y = 0;
    if (s_touch.getPoint(&x, &y, 1) > 0) {
        data->state = LV_INDEV_STATE_PR;
        data->point.x = x;
        data->point.y = y;
        if (s_interaction_cb) {
            s_interaction_cb();
        }
    } else {
        data->state = LV_INDEV_STATE_REL;
    }
}

static void onShortcutBtnEvent(lv_event_t* e) {
    const char* text = static_cast<const char*>(lv_event_get_user_data(e));
    if (s_interaction_cb) {
        s_interaction_cb();
    }
    if (text != nullptr && s_shortcut_cb) {
        s_shortcut_cb(text);
    }
}

static void onAlertDismissEvent(lv_event_t* e) {
    (void)e;
    if (s_interaction_cb) {
        s_interaction_cb();
    }
    if (s_lbl_alert != nullptr) {
        lv_label_set_text(s_lbl_alert, "Sem alertas pendentes");
    }
    if (s_tileview != nullptr && s_tile_status != nullptr) {
        lv_obj_set_tile(s_tileview, s_tile_status, LV_ANIM_ON);
    }
}

static lv_color_t parseHexOrDefault(const char* hex_str, uint32_t fallback) {
    if (hex_str != nullptr && hex_str[0] == '#') {
        uint32_t val = static_cast<uint32_t>(strtoul(hex_str + 1, nullptr, 16));
        return lv_color_hex(val);
    }
    return lv_color_hex(fallback);
}

void UiLvglManager::begin(ShortcutCallback on_shortcut, InteractionCallback on_interaction) {
    on_shortcut_ = on_shortcut;
    on_interaction_ = on_interaction;
    s_shortcut_cb = on_shortcut;
    s_interaction_cb = on_interaction;

    s_tft.init();
    s_tft.setRotation(0);
    s_tft.fillScreen(TFT_BLACK);

    Wire1.begin(YBY_TOUCH_SDA, YBY_TOUCH_SCL);
    s_touch.begin(Wire1, FT6X36_SLAVE_ADDRESS, YBY_TOUCH_SDA, YBY_TOUCH_SCL);

    lv_init();
    lv_disp_draw_buf_init(&s_draw_buf, s_buf1, nullptr, YBY_DISP_WIDTH * 24);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = YBY_DISP_WIDTH;
    disp_drv.ver_res = YBY_DISP_HEIGHT;
    disp_drv.flush_cb = dispFlushCb;
    disp_drv.draw_buf = &s_draw_buf;
    lv_disp_drv_register(&disp_drv);

    static lv_indev_drv_t indev_drv;
    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = touchReadCb;
    lv_indev_drv_register(&indev_drv);

    // 3A: Carrossel horizontal minimalista Nothing OS / CMF (#0D0D0D / #F5F5F2 / #00FF66)
    lv_obj_t* scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_hex(YBY_COLOR_BG), 0);
    lv_obj_set_style_text_color(scr, lv_color_hex(YBY_COLOR_FG), 0);

    s_tileview = lv_tileview_create(scr);
    lv_obj_set_style_bg_color(s_tileview, lv_color_hex(YBY_COLOR_BG), 0);
    lv_obj_set_scrollbar_mode(s_tileview, LV_SCROLLBAR_MODE_OFF);

    // Tela 1: Status (Relogio dot-matrix + arco segmentado + bateria + link)
    s_tile_status = lv_tileview_add_tile(s_tileview, 0, 0, LV_DIR_RIGHT);
    s_arc_state = lv_arc_create(s_tile_status);
    lv_obj_set_size(s_arc_state, 224, 224);
    lv_obj_center(s_arc_state);
    lv_arc_set_rotation(s_arc_state, 135);
    lv_arc_set_bg_angles(s_arc_state, 0, 270);
    lv_arc_set_value(s_arc_state, 100);
    lv_obj_remove_style(s_arc_state, nullptr, LV_PART_KNOB);
    lv_obj_clear_flag(s_arc_state, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(s_arc_state, 8, LV_PART_MAIN);
    lv_obj_set_style_arc_width(s_arc_state, 8, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(s_arc_state, lv_color_hex(YBY_COLOR_SURFACE), LV_PART_MAIN);
    lv_obj_set_style_arc_color(s_arc_state, lv_color_hex(YBY_COLOR_FG), LV_PART_INDICATOR);

    s_lbl_clock = lv_label_create(s_tile_status);
    lv_obj_set_style_text_font(s_lbl_clock, &lv_font_montserrat_40, 0);
    lv_obj_set_style_text_color(s_lbl_clock, lv_color_hex(YBY_COLOR_FG), 0);
    lv_label_set_text(s_lbl_clock, "--:--");
    lv_obj_align(s_lbl_clock, LV_ALIGN_CENTER, 0, -14);

    s_lbl_state = lv_label_create(s_tile_status);
    lv_obj_set_style_text_font(s_lbl_state, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(s_lbl_state, lv_color_hex(YBY_COLOR_ACCENT), 0);
    lv_label_set_text(s_lbl_state, "IDLE");
    lv_obj_align(s_lbl_state, LV_ALIGN_CENTER, 0, 24);

    s_lbl_batt = lv_label_create(s_tile_status);
    lv_obj_set_style_text_font(s_lbl_batt, &lv_font_montserrat_12, 0);
    lv_label_set_text(s_lbl_batt, "BAT 100%");
    lv_obj_align(s_lbl_batt, LV_ALIGN_BOTTOM_MID, -38, -22);

    s_lbl_link = lv_label_create(s_tile_status);
    lv_obj_set_style_text_font(s_lbl_link, &lv_font_montserrat_12, 0);
    lv_label_set_text(s_lbl_link, "OFFLINE");
    lv_obj_align(s_lbl_link, LV_ALIGN_BOTTOM_MID, 40, -22);

    // Tela 2: Atalhos 2C + ultimo display_text
    s_tile_shortcuts = lv_tileview_add_tile(s_tileview, 1, 0, LV_DIR_HOR);
    lv_obj_t* lbl_sc_title = lv_label_create(s_tile_shortcuts);
    lv_obj_set_style_text_color(lbl_sc_title, lv_color_hex(YBY_COLOR_ACCENT), 0);
    lv_label_set_text(lbl_sc_title, "YBY ATALHOS");
    lv_obj_align(lbl_sc_title, LV_ALIGN_TOP_MID, 0, 12);

    lv_obj_t* list = lv_list_create(s_tile_shortcuts);
    lv_obj_set_size(list, 212, 132);
    lv_obj_align(list, LV_ALIGN_TOP_MID, 0, 36);
    lv_obj_set_style_bg_color(list, lv_color_hex(YBY_COLOR_SURFACE), 0);
    lv_obj_set_style_border_width(list, 0, 0);

    for (int i = 0; i < YBY_SHORTCUT_COUNT; ++i) {
        lv_obj_t* btn = lv_list_add_btn(list, nullptr, YBY_VOICE_SHORTCUTS[i]);
        lv_obj_set_style_bg_color(btn, lv_color_hex(YBY_COLOR_BG), 0);
        lv_obj_set_style_text_color(btn, lv_color_hex(YBY_COLOR_FG), 0);
        lv_obj_add_event_cb(
            btn,
            onShortcutBtnEvent,
            LV_EVENT_CLICKED,
            const_cast<char*>(YBY_VOICE_SHORTCUTS[i])
        );
    }

    s_lbl_reply = lv_label_create(s_tile_shortcuts);
    lv_obj_set_width(s_lbl_reply, 208);
    lv_label_set_long_mode(s_lbl_reply, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_font(s_lbl_reply, &lv_font_montserrat_12, 0);
    lv_label_set_text(s_lbl_reply, "Aguardando resposta do hub...");
    lv_obj_align(s_lbl_reply, LV_ALIGN_BOTTOM_MID, 0, -14);

    // Tela 3: Alertas (yby_machine / yby/nodes/twatch/cmd) com OK / Dismiss
    s_tile_alerts = lv_tileview_add_tile(s_tileview, 2, 0, LV_DIR_LEFT);
    lv_obj_t* lbl_al_title = lv_label_create(s_tile_alerts);
    lv_obj_set_style_text_color(lbl_al_title, lv_color_hex(YBY_COLOR_ACCENT), 0);
    lv_label_set_text(lbl_al_title, "ALERTAS");
    lv_obj_align(lbl_al_title, LV_ALIGN_TOP_MID, 0, 14);

    s_lbl_alert = lv_label_create(s_tile_alerts);
    lv_obj_set_width(s_lbl_alert, 200);
    lv_label_set_long_mode(s_lbl_alert, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_font(s_lbl_alert, &lv_font_montserrat_14, 0);
    lv_label_set_text(s_lbl_alert, "Sem alertas pendentes");
    lv_obj_align(s_lbl_alert, LV_ALIGN_CENTER, 0, -12);

    lv_obj_t* btn_ok = lv_btn_create(s_tile_alerts);
    lv_obj_set_size(btn_ok, 88, 36);
    lv_obj_align(btn_ok, LV_ALIGN_BOTTOM_LEFT, 22, -20);
    lv_obj_set_style_bg_color(btn_ok, lv_color_hex(YBY_COLOR_ACCENT), 0);
    lv_obj_add_event_cb(btn_ok, onAlertDismissEvent, LV_EVENT_CLICKED, nullptr);
    lv_obj_t* lbl_ok = lv_label_create(btn_ok);
    lv_obj_set_style_text_color(lbl_ok, lv_color_hex(YBY_COLOR_BG), 0);
    lv_label_set_text(lbl_ok, "OK");
    lv_obj_center(lbl_ok);

    lv_obj_t* btn_dismiss = lv_btn_create(s_tile_alerts);
    lv_obj_set_size(btn_dismiss, 88, 36);
    lv_obj_align(btn_dismiss, LV_ALIGN_BOTTOM_RIGHT, -22, -20);
    lv_obj_set_style_bg_color(btn_dismiss, lv_color_hex(YBY_COLOR_SURFACE), 0);
    lv_obj_add_event_cb(btn_dismiss, onAlertDismissEvent, LV_EVENT_CLICKED, nullptr);
    lv_obj_t* lbl_dis = lv_label_create(btn_dismiss);
    lv_obj_set_style_text_color(lbl_dis, lv_color_hex(YBY_COLOR_FG), 0);
    lv_label_set_text(lbl_dis, "DISMISS");
    lv_obj_center(lbl_dis);
}

void UiLvglManager::tick() {
    lv_timer_handler();
}

void UiLvglManager::updateStatus(
    const char* time_str,
    const char* audio_state,
    int battery_pct,
    bool charging,
    const char* link_label
) {
    if (s_lbl_clock != nullptr && time_str != nullptr) {
        lv_label_set_text(s_lbl_clock, time_str);
    }
    if (s_lbl_state != nullptr && audio_state != nullptr) {
        lv_label_set_text(s_lbl_state, audio_state);
    }
    if (s_arc_state != nullptr && audio_state != nullptr) {
        if (strcmp(audio_state, "listening") == 0) {
            lv_obj_set_style_arc_color(s_arc_state, lv_color_hex(YBY_COLOR_ACCENT), LV_PART_INDICATOR);
            lv_arc_set_value(s_arc_state, 65);
        } else if (strcmp(audio_state, "thinking") == 0) {
            lv_obj_set_style_arc_color(s_arc_state, lv_color_hex(YBY_COLOR_FG), LV_PART_INDICATOR);
            lv_arc_set_value(s_arc_state, 40);
        } else if (strcmp(audio_state, "speaking") == 0) {
            lv_obj_set_style_arc_color(s_arc_state, lv_color_hex(YBY_COLOR_FG), LV_PART_INDICATOR);
            lv_arc_set_value(s_arc_state, 100);
        } else {
            lv_obj_set_style_arc_color(s_arc_state, lv_color_hex(YBY_COLOR_SURFACE), LV_PART_INDICATOR);
            lv_arc_set_value(s_arc_state, battery_pct);
        }
    }
    if (s_lbl_batt != nullptr) {
        lv_label_set_text_fmt(s_lbl_batt, charging ? "CHG %d%%" : "BAT %d%%", battery_pct);
    }
    if (s_lbl_link != nullptr && link_label != nullptr) {
        lv_label_set_text(s_lbl_link, link_label);
    }
}

void UiLvglManager::setLastReply(const char* text) {
    if (s_lbl_reply != nullptr && text != nullptr) {
        lv_label_set_text(s_lbl_reply, text);
    }
}

void UiLvglManager::showAlert(const char* text, const char* accent_hex) {
    if (s_lbl_alert != nullptr && text != nullptr) {
        lv_obj_set_style_text_color(s_lbl_alert, parseHexOrDefault(accent_hex, YBY_COLOR_FG), 0);
        lv_label_set_text(s_lbl_alert, text);
    }
    if (s_tileview != nullptr && s_tile_alerts != nullptr) {
        lv_obj_set_tile(s_tileview, s_tile_alerts, LV_ANIM_ON);
    }
}

void UiLvglManager::clearAlert() {
    if (s_lbl_alert != nullptr) {
        lv_label_set_text(s_lbl_alert, "Sem alertas pendentes");
    }
}
