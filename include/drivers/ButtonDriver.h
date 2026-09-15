#pragma once

#include <stdint.h>

class ButtonDriver {
public:
    void begin();
    void update();
    bool wasPressed(uint8_t slot);
private:
    bool stable_[3] = {false, false, false};
    bool lastRaw_[3] = {false, false, false};
    bool pressed_[3] = {false, false, false};
    unsigned long changedAt_[3] = {0, 0, 0};
};
