#include "storage/SettingsStore.h"
#include <Preferences.h>

static Preferences preferences;
bool SettingsStore::begin() { return preferences.begin("pillbox", false); }
void SettingsStore::resetToDefaults(StoredSettings& settings) { settings = {1, 30.0f, 70.0f}; }
bool SettingsStore::load(StoredSettings& settings) {
    resetToDefaults(settings);
    if (!preferences.isKey("version")) return false;
    settings.version = preferences.getUChar("version", 1);
    settings.maxTemperatureC = preferences.getFloat("max_temp", 30.0f);
    settings.maxHumidityPercent = preferences.getFloat("max_hum", 70.0f);
    return true;
}
bool SettingsStore::save(const StoredSettings& settings) {
    return preferences.putUChar("version", settings.version) > 0 &&
           preferences.putFloat("max_temp", settings.maxTemperatureC) > 0 &&
           preferences.putFloat("max_hum", settings.maxHumidityPercent) > 0;
}
