#include "drivers/LedDriver.h"
#include "config/Pins.h"
#include <Arduino.h>

void LedDriver::begin() { for (int pin : Pins::SLOT_LEDS) { pinMode(pin, OUTPUT); digitalWrite(pin, LOW); } }
void LedDriver::setSlot(uint8_t slot, bool on) { if (slot >= 1 && slot <= 3) digitalWrite(Pins::SLOT_LEDS[slot - 1], on ? HIGH : LOW); }
void LedDriver::allOff() { for (uint8_t i = 1; i <= 3; ++i) setSlot(i, false); }
