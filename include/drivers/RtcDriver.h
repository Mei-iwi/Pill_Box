#pragma once

#include <stdint.h>

struct ClockTime { uint16_t minuteOfDay; uint16_t second; };

class RtcDriver {
public:
    bool begin();
    ClockTime now() const;
    bool isReady() const { return ready_; }
private:
    bool ready_ = false;
};
