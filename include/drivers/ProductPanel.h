#pragma once
#include <stdint.h>
#include "domain/DomainTypes.h"

// OLED + scanner input. Keypad emulates a scanner in Wokwi; UART accepts a real reader.
class ProductPanel {
public:
    void begin();
    void update(uint16_t minute, uint16_t second, const char* state, bool connected, const Schedule* schedules);
    void select(uint8_t slot) { selected_ = slot; }
    bool takeScan(char* destination, unsigned capacity);
private:
    uint8_t selected_ = 1;
    char input_[49] = {};
    char ready_[49] = {};
    char captured_[49] = {};
    unsigned length_ = 0;
    unsigned long lastDraw_ = 0;
    bool displayReady_ = false;
    bool invalidInput_ = false;
    void character(char c);
};
