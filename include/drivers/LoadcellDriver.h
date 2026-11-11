#pragma once

// Optional HX711 integration contract. No concrete implementation or hardware validation yet.
// A weight change observes removal only; it cannot identify medication or prove ingestion.
class LoadcellDriver {
public:
    virtual ~LoadcellDriver() = default;
    virtual bool begin() = 0;
    virtual void update() = 0;  // Must not block scheduler/network processing.
    virtual bool ready() const = 0;
    virtual float grams() const = 0;
    virtual void tare() = 0;
    virtual bool calibrate(float referenceGrams) = 0;
};
