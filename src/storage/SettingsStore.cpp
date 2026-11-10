#include "storage/SettingsStore.h"
#include <Preferences.h>
#include <math.h>
#include "config/AppConfig.h"

static Preferences preferences;
bool SettingsStore::loadSchedules(StoredSchedules& value) {
    if (preferences.getBytesLength("schedules_v1") != sizeof(value) || preferences.getBytes("schedules_v1", &value, sizeof(value)) != sizeof(value) || value.version != 1) return false;
    for (uint8_t i=0;i<4;++i) if (value.hour[i]>23 || value.minute[i]>59 || value.enabled[i]>1) return false;
    return true;
}
bool SettingsStore::saveSchedules(const StoredSchedules& value) { return preferences.putBytes("schedules_v1", &value, sizeof(value)) == sizeof(value); }
bool SettingsStore::loadLedger(void* ledger, size_t size) { return preferences.getBytesLength("ledger_v1") == size && preferences.getBytes("ledger_v1", ledger, size) == size; }
bool SettingsStore::saveLedger(const void* ledger, size_t size) { return preferences.putBytes("ledger_v1", ledger, size) == size; }
bool SettingsStore::begin() { return preferences.begin("pillbox", false); }
void SettingsStore::resetToDefaults(StoredSettings& settings) { settings = {1, AppConfig::DEMO_MAX_TEMPERATURE_C, AppConfig::DEMO_MAX_HUMIDITY_PERCENT}; }
bool SettingsStore::load(StoredSettings& settings) {
    resetToDefaults(settings);
    if (!preferences.isKey("version")) return false;
    settings.version = preferences.getUChar("version", 1);
    settings.maxTemperatureC = preferences.getFloat("max_temp", 30.0f);
    settings.maxHumidityPercent = preferences.getFloat("max_hum", 70.0f);
    if (settings.version != 1 || !isfinite(settings.maxTemperatureC) || !isfinite(settings.maxHumidityPercent) || settings.maxHumidityPercent < 0 || settings.maxHumidityPercent > 100) { resetToDefaults(settings); return false; }
    return true;
}
bool SettingsStore::save(const StoredSettings& settings) {
    return preferences.putUChar("version", settings.version) > 0 &&
           preferences.putFloat("max_temp", settings.maxTemperatureC) > 0 &&
           preferences.putFloat("max_hum", settings.maxHumidityPercent) > 0;
}
