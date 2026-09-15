#include "drivers/EnvironmentDriver.h"
#include "config/Pins.h"
#include "config/AppConfig.h"
#include <Arduino.h>
#include <DHT.h>

static DHT dht(Pins::DHT, DHT22);
void EnvironmentDriver::begin() { dht.begin(); }
void EnvironmentDriver::update() {
    if (millis() - lastRead_ < AppConfig::DHT_READ_MS) return;
    lastRead_ = millis();
    const float humidity = dht.readHumidity();
    const float temperature = dht.readTemperature();
    reading_ = {temperature, humidity, !isnan(temperature) && !isnan(humidity)};
}
