#include "drivers/BuzzerDriver.h"
#include "config/Pins.h"
#include <Arduino.h>

void BuzzerDriver::begin() { pinMode(Pins::BUZZER, OUTPUT); digitalWrite(Pins::BUZZER, LOW); }
void BuzzerDriver::start() {
    active_ = true; startedAt_ = millis();
#ifdef PILLBOX_SIMULATION
    tone(Pins::BUZZER,2000); // Wokwi models a passive piezo.
#else
    digitalWrite(Pins::BUZZER,HIGH); // Active buzzer via a suitable driver.
#endif
}
void BuzzerDriver::stop() {
    active_ = false;
#ifdef PILLBOX_SIMULATION
    noTone(Pins::BUZZER);
#endif
    digitalWrite(Pins::BUZZER,LOW);
}
void BuzzerDriver::update() { if (active_ && millis() - startedAt_ >= 5000) stop(); }
