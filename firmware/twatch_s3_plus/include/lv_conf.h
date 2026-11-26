#pragma once

#if 1

#include <stdint.h>

#define LV_COLOR_DEPTH 16
#define LV_COLOR_16_SWAP 1

#define LV_MEM_CUSTOM 0
#define LV_MEM_SIZE (64U * 1024U)

#define LV_TICK_CUSTOM 1
#if LV_TICK_CUSTOM
#define LV_TICK_CUSTOM_INCLUDE "Arduino.h"
#define LV_TICK_CUSTOM_SYS_TIME_EXPR (millis())
#endif

#define LV_DPI_DEF 260

#define LV_FONT_MONTSERRAT_12 1
#define LV_FONT_MONTSERRAT_14 1
#define LV_FONT_MONTSERRAT_16 1
#define LV_FONT_MONTSERRAT_28 1
#define LV_FONT_MONTSERRAT_40 1
#define LV_FONT_DEFAULT &lv_font_montserrat_14

#define LV_USE_ARC 1
#define LV_USE_BTN 1
#define LV_USE_LABEL 1
#define LV_USE_LIST 1
#define LV_USE_TILEVIEW 1

#define LV_USE_LOG 0

#endif
