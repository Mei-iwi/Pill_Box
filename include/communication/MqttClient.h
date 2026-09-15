#pragma once

#include "domain/DomainTypes.h"
#include <stdint.h>

class WifiManager;

class MqttClient {
public:
    using CommandHandler = void (*)(void*, const char*);
    explicit MqttClient(WifiManager& wifi);
    void begin();
    void update();
    bool connected() const;
    void setCommandHandler(CommandHandler handler, void* context);
    void publishEvent(const SchedulerEvent& event, uint32_t sequence);
    void publishEnvironment(float temperatureC, float humidityPercent, bool sensorOk, uint32_t sequence);
    void publishHeartbeat(const char* state, uint32_t sequence);
    void publishStatus(const char* state, uint32_t sequence);
    void dispatchCommand(const char* payload);
private:
    WifiManager& wifi_;
    CommandHandler handler_ = nullptr;
    void* context_ = nullptr;
    unsigned long lastAttempt_ = 0;
    struct Pending { char topic[64]; char payload[320]; } queue_[16];
    uint8_t queueCount_ = 0;
    void publishOrQueue(const char* topic, const char* payload);
    void flushQueue();
};
