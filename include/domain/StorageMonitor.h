#pragma once
#include <math.h>
#include <stdint.h>

enum class StorageTransition { NONE, WARNING, NORMAL, SENSOR_ERROR };
class StorageMonitor {
public:
    StorageTransition sample(float temperature, float humidity, bool sensorOk,
                             float maxTemperature, float maxHumidity, float hysteresis, uint8_t required) {
        if (!sensorOk || !isfinite(temperature) || !isfinite(humidity)) {
            bad_=good_=0;
            if (!error_) { error_=true; return StorageTransition::SENSOR_ERROR; }
            return StorageTransition::NONE;
        }
        error_=false;
        const bool outside=temperature>maxTemperature || humidity>maxHumidity;
        const bool recovered=temperature<maxTemperature-hysteresis && humidity<maxHumidity-hysteresis;
        bad_=outside ? (bad_<250 ? bad_+1 : 250) : 0;
        good_=recovered ? (good_<250 ? good_+1 : 250) : 0;
        if (!warning_ && bad_>=required) { warning_=true; return StorageTransition::WARNING; }
        if (warning_ && good_>=required) { warning_=false; return StorageTransition::NORMAL; }
        return StorageTransition::NONE;
    }
private:
    bool warning_=false,error_=false;
    uint8_t bad_=0,good_=0;
};
