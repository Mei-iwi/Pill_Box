#pragma once
#include <stdint.h>
#include <math.h>

// Sample every 2 s, publish on change or at least once every 30 s.
class TelemetryGate {
public:
    bool shouldPublish(float temperature, float humidity, bool valid, uint32_t now, bool force=false) {
        const bool changed=!initialized_ || valid!=valid_ ||
            (valid && (fabsf(temperature-temperature_)>=0.3f || fabsf(humidity-humidity_)>=2.0f));
        if (!force && !changed && static_cast<uint32_t>(now-last_)<30000UL) return false;
        initialized_=true; valid_=valid; temperature_=temperature; humidity_=humidity; last_=now;
        return true;
    }
private:
    bool initialized_=false, valid_=false;
    float temperature_=0, humidity_=0;
    uint32_t last_=0;
};
