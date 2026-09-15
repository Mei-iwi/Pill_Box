#include "drivers/RtcDriver.h"
#include "config/Pins.h"
#include <Arduino.h>
#include <Wire.h>
#include <RTClib.h>

#ifdef PILLBOX_SIMULATION
static RTC_DS1307 rtc;
#else
static RTC_DS3231 rtc;
#endif

bool RtcDriver::begin() {
    Wire.begin(Pins::RTC_SDA, Pins::RTC_SCL);
    ready_ = rtc.begin();
    return ready_;
}

ClockTime RtcDriver::now() const {
    if (ready_) {
        const DateTime t = rtc.now();
        return {static_cast<uint16_t>(t.hour() * 60 + t.minute()), t.second()};
    }
    const unsigned long seconds = millis() / 1000UL;
    return {static_cast<uint16_t>((seconds / 60UL) % 1440UL), static_cast<uint16_t>(seconds % 60UL)};
}
