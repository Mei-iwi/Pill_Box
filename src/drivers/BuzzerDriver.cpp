#include "drivers/BuzzerDriver.h"
#include "config/Pins.h"
#include <Arduino.h>

void BuzzerDriver::begin() { pinMode(Pins::BUZZER, OUTPUT); digitalWrite(Pins::BUZZER, LOW); }
void BuzzerDriver::start() { active_ = true; startedAt_ = millis(); digitalWrite(Pins::BUZZER, HIGH); }
void BuzzerDriver::stop() { active_ = false; digitalWrite(Pins::BUZZER, LOW); }
void BuzzerDriver::update() { if (active_ && millis() - startedAt_ >= 5000) stop(); }
