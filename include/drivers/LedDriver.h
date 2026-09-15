#pragma once

#include <stdint.h>

class LedDriver {
public:
    void begin();
    void setSlot(uint8_t slot, bool on);
    void allOff();
};
