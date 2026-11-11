#pragma once

#include "app/Scheduler.h"
#include "drivers/RtcDriver.h"
#include "drivers/ButtonDriver.h"
#include "drivers/LedDriver.h"
#include "drivers/BuzzerDriver.h"
#include "drivers/EnvironmentDriver.h"
#include "storage/SettingsStore.h"
#include "communication/WifiManager.h"
#include "communication/MqttClient.h"
#include "domain/StorageMonitor.h"
#include "domain/RefillWindow.h"

class AppController {
public:
    AppController();
    void begin();
    void update();
private:
    Scheduler scheduler_;
    RtcDriver rtc_;
    ButtonDriver buttons_;
    LedDriver leds_;
    BuzzerDriver buzzer_;
    EnvironmentDriver environment_;
    SettingsStore settings_;
    StoredSettings stored_{};
    WifiManager wifi_;
    MqttClient mqtt_;
    uint32_t sequence_ = 0;
    unsigned long lastHeartbeat_ = 0;
    unsigned long lastEnvironment_ = 0;
    const char* state_ = "IDLE";
    const char* lastPublishedState_ = "";
    bool statusDirty_ = true;
    bool wasConnected_ = false;
    bool alertSilenced_ = false;
    StorageMonitor storageMonitor_;
    RefillWindow refillWindow_;
    bool incidentActive_ = false;
    uint8_t incidentSlot_ = 0;
    unsigned long incidentStarted_ = 0;
    static void handleCommand(void* context, const char* payload);
    void handleCommandPayload(const char* payload);
    void handleEvent(const SchedulerEvent& event);
};
