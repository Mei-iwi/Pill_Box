#pragma once

#include <stdint.h>
#include <stddef.h>

struct StoredSettings { uint8_t version; float maxTemperatureC; float maxHumidityPercent; };
struct StoredSchedules { uint32_t version = 1; uint8_t hour[4]{}, minute[4]{}, enabled[4]{}; };

class SettingsStore {
public:
    bool begin();
    bool load(StoredSettings& settings);
    bool save(const StoredSettings& settings);
    void resetToDefaults(StoredSettings& settings);
    bool loadLedger(void* ledger, size_t size);
    bool saveLedger(const void* ledger, size_t size);
    bool loadSchedules(StoredSchedules& value);
    bool saveSchedules(const StoredSchedules& value);
};
