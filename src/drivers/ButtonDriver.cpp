#include "drivers/ButtonDriver.h"
#include "config/Pins.h"
#include <Arduino.h>

void ButtonDriver::begin() {
    for (int pin : Pins::SLOT_BUTTONS) pinMode(pin, INPUT_PULLUP);
}

void ButtonDriver::update() {
    const unsigned long now = millis();
    for (uint8_t i = 0; i < 3; ++i) {
        const bool rawPressed = digitalRead(Pins::SLOT_BUTTONS[i]) == LOW;
        if (rawPressed != lastRaw_[i]) { lastRaw_[i] = rawPressed; changedAt_[i] = now; }
        if (now - changedAt_[i] >= 35 && stable_[i] != rawPressed) {
            stable_[i] = rawPressed;
            if (stable_[i]) pressed_[i] = true;
        }
    }
}

bool ButtonDriver::wasPressed(uint8_t slot) {
    if (slot < 1 || slot > 3) return false;
    const bool result = pressed_[slot - 1];
    pressed_[slot - 1] = false;
    return result;
}
