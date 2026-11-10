#pragma once

struct EnvironmentReading { float temperatureC; float humidityPercent; bool sensorOk; };

class EnvironmentDriver {
public:
    void begin();
    bool update(); // True only for a new measurement (including a failed read).
    EnvironmentReading reading() const { return reading_; }
private:
    EnvironmentReading reading_{0, 0, false};
    unsigned long lastRead_ = 0;
};
