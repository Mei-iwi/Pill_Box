#pragma once

// Pin map for the Adafruit Feather ESP32-S2 prototype. Verify the wiring
// against the exact board revision before connecting hardware.
namespace Pins {
constexpr int RTC_SDA = 3;
constexpr int RTC_SCL = 4;
constexpr int SLOT_BUTTONS[3] = {5, 6, 7};
constexpr int SLOT_LEDS[3] = {8, 9, 10};
constexpr int BUZZER = 11;
constexpr int DHT = 12;
}
