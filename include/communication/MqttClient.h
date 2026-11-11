#pragma once

#include "domain/DomainTypes.h"
#include "domain/EventBuffer.h"
#include <stdint.h>
#include <atomic>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

class WifiManager;

class MqttClient {
public:
    using CommandHandler = void (*)(void*, const char*);
    explicit MqttClient(WifiManager& wifi);
    void begin();
    void update();
    bool connected() const;
    void setCommandHandler(CommandHandler handler, void* context);
    void publishEvent(const SchedulerEvent& event, uint32_t sequence, const char* state = nullptr, const char* refillSession = nullptr);
    void publishEnvironment(float temperatureC, float humidityPercent, bool sensorOk, uint32_t sampledEpoch, uint32_t sequence, const char* storageStatus = "PENDING");
    void publishHeartbeat(const char* state, uint32_t sequence, uint16_t minute = 1440, uint32_t epoch = 0);
    void publishStatus(const char* state, uint32_t sequence);
    void publishCommandResult(const char* commandId, const char* command, bool accepted, const Schedule* schedules, uint8_t count, const char* refillSession = nullptr);
    void dispatchCommand(const char* payload);
private:
    WifiManager& wifi_;
    CommandHandler handler_ = nullptr;
    void* context_ = nullptr;
    unsigned long lastAttempt_ = 0;
    char bootId_[24] = {};
    struct Pending { char topic[80]; char payload[1024]; };
    EventBuffer<Pending,16> queue_;
    EventBuffer<Pending,4> telemetry_;
    EventBuffer<Pending,8> control_;
    struct Command { char payload[320]; };
    EventBuffer<Command,4> commands_;
    SemaphoreHandle_t mutex_ = nullptr;
    std::atomic<bool> networkConnected_{false};
    Pending inFlight_{};
    bool hasInFlight_ = false;
    static void networkTask(void* context);
    void networkUpdate();
    void publishOrQueue(const char* topic, const char* payload, bool durable = false, bool priority = false);
    void flushQueue();
    void publishKind(const char* kind, const char* payload, bool durable = false, bool priority = false);
};
