#pragma once

#include <stdint.h>

struct ClockTime {
    uint16_t minuteOfDay;
    uint16_t second;
    uint32_t dayKey;
    uint32_t epoch;
};

class RtcDriver {
public:
    bool begin();
    ClockTime now() const;
    bool setDemoTime(uint8_t hour, uint8_t minute);
    bool isReady() const { return ready_; }
private:
    bool ready_ = false;
};
