#include "drivers/RtcDriver.h"
#include "config/Pins.h"
#include <Arduino.h>
#include <Wire.h>
#include <RTClib.h>
#include <time.h>

#ifdef PILLBOX_SIMULATION
static RTC_DS1307 rtc;
#else
static RTC_DS3231 rtc;
#endif

static uint32_t demoEpoch = 0;
static uint32_t demoStarted = 0;

bool RtcDriver::setDemoTime(uint8_t hour, uint8_t minute) {
#ifdef PILLBOX_SIMULATION
    if (hour > 23 || minute > 59 || !ready_) return false;
    const DateTime date = rtc.now();
    demoEpoch = DateTime(date.year(),date.month(),date.day(),hour,minute,0).unixtime();
    demoStarted = millis(); cached_=false; return true;
#else
    return false;
#endif
}

bool RtcDriver::begin() {
    Wire.begin(Pins::RTC_SDA, Pins::RTC_SCL);
    present_ = rtc.begin();
    ready_ = present_;
#ifdef PILLBOX_SIMULATION
    if (ready_) ready_=rtc.isrunning();
#else
    if (ready_) ready_=!rtc.lostPower();
#endif
    return ready_;
}

bool RtcDriver::synchronizeUtc(uint32_t utc) {
#ifdef PILLBOX_SIMULATION
    return false; // Keep the controlled Wokwi RTC and TIME commands independent of NTP.
#else
    if (utc<1704067200UL || utc>4102444799UL) return false;
    if (present_) { rtc.adjust(DateTime(utc+7UL*3600UL)); ready_=true; }
    cached_=false;
    return true;
#endif
}

ClockTime RtcDriver::now() const {
    if (cached_ && millis()-lastRead_ < 200) return cachedTime_;
    lastRead_=millis(); cached_=true;
    if (ready_) {
        const DateTime t = demoEpoch ? DateTime(demoEpoch + (millis()-demoStarted)/1000UL) : rtc.now();
        if (t.isValid() && t.year()>=2020 && t.year()<=2099) {
        const uint32_t dayKey = static_cast<uint32_t>(t.year()) * 10000UL + t.month() * 100UL + t.day();
        cachedTime_={static_cast<uint16_t>(t.hour() * 60 + t.minute()), t.second(), dayKey, t.unixtime()};
        return cachedTime_;
        }
    }
#ifndef PILLBOX_SIMULATION
    const time_t utc=time(nullptr);
    if (utc>=1704067200 && utc<=4102444799LL) {
        const DateTime t(static_cast<uint32_t>(utc)+7UL*3600UL);
        cachedTime_={static_cast<uint16_t>(t.hour()*60+t.minute()),t.second(),
            static_cast<uint32_t>(t.year())*10000UL+t.month()*100UL+t.day(),t.unixtime()};
        return cachedTime_;
    }
#endif
    const unsigned long seconds = millis() / 1000UL;
    cachedTime_={static_cast<uint16_t>((seconds / 60UL) % 1440UL), static_cast<uint16_t>(seconds % 60UL),
            1UL + seconds / 86400UL, 0};
    return cachedTime_;
}
