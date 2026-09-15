#pragma once

#include <stdint.h>

struct StoredSettings { uint8_t version; float maxTemperatureC; float maxHumidityPercent; };

class SettingsStore {
public:
    bool begin();
    bool load(StoredSettings& settings);
    bool save(const StoredSettings& settings);
    void resetToDefaults(StoredSettings& settings);
};
