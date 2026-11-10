#include "drivers/BuzzerDriver.h"
#include "config/Pins.h"
#include <Arduino.h>

void BuzzerDriver::begin() {
    pinMode(Pins::BUZZER, OUTPUT); digitalWrite(Pins::BUZZER, LOW);
#ifdef PILLBOX_SIMULATION
    // Initialize the timer before attaching: Arduino 2.x tone() attaches first,
    // which reads duty from an uninitialized LEDC peripheral on ESP32-S2.
    pwmReady_ = ledcSetup(0, 2000, 8) != 0;
    if (pwmReady_) { ledcAttachPin(Pins::BUZZER, 0); ledcWrite(0, 0); }
    else Serial.println("ERROR: buzzer PWM initialization failed");
#endif
}
void BuzzerDriver::start() {
#ifdef PILLBOX_SIMULATION
    if (!pwmReady_) return;
#endif
    active_ = true; startedAt_ = millis();
#ifdef PILLBOX_SIMULATION
    ledcWrite(0, 128); // 2 kHz, 50% duty for Wokwi's passive piezo.
#else
    digitalWrite(Pins::BUZZER,HIGH); // Active buzzer via a suitable driver.
#endif
}
void BuzzerDriver::stop() {
    active_ = false;
#ifdef PILLBOX_SIMULATION
    if (pwmReady_) ledcWrite(0, 0);
#else
    digitalWrite(Pins::BUZZER,LOW);
#endif
}
void BuzzerDriver::update() { if (active_ && millis() - startedAt_ >= 5000) stop(); }
