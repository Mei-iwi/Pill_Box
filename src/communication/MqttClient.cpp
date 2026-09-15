#include "communication/MqttClient.h"
#include "communication/WifiManager.h"
#include "config/AppConfig.h"
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#if __has_include("config/Secrets.h")
#include "config/Secrets.h"
#else
#define PILLBOX_MQTT_USER ""
#define PILLBOX_MQTT_PASSWORD ""
#endif

static WiFiClient netClient;
static PubSubClient mqtt(netClient);
static MqttClient* currentClient = nullptr;

static void mqttCallback(char* topic, byte* payload, unsigned int length) {
    if (!currentClient || String(topic) != "pillbox/PB01/command") return;
    char message[320] = {0};
    const unsigned int copyLength = length < sizeof(message) - 1 ? length : sizeof(message) - 1;
    memcpy(message, payload, copyLength);
    currentClient->dispatchCommand(message);
}

MqttClient::MqttClient(WifiManager& wifi) : wifi_(wifi) {}

void MqttClient::begin() {
    mqtt.setServer(AppConfig::MQTT_HOST, AppConfig::MQTT_PORT);
    mqtt.setCallback(mqttCallback);
    currentClient = this;
}

void MqttClient::update() {
    if (!wifi_.connected()) return;
    if (!mqtt.connected()) {
        if (millis() - lastAttempt_ < AppConfig::MQTT_RETRY_MS) return;
        lastAttempt_ = millis();
        const bool connected = strlen(PILLBOX_MQTT_USER) > 0
            ? mqtt.connect(AppConfig::DEVICE_ID, PILLBOX_MQTT_USER, PILLBOX_MQTT_PASSWORD)
            : mqtt.connect(AppConfig::DEVICE_ID);
        if (connected) {
            mqtt.subscribe("pillbox/PB01/command");
            mqtt.publish("pillbox/PB01/status", "{\"device_id\":\"PB01\",\"status\":\"online\"}");
            flushQueue();
        }
        return;
    }
    mqtt.loop();
}

bool MqttClient::connected() const { return mqtt.connected(); }
void MqttClient::setCommandHandler(CommandHandler handler, void* context) { handler_ = handler; context_ = context; }
void MqttClient::dispatchCommand(const char* payload) { if (handler_) handler_(context_, payload); }

void MqttClient::publishOrQueue(const char* topic, const char* payload) {
    if (mqtt.connected()) { mqtt.publish(topic, payload); return; }
    if (queueCount_ >= AppConfig::OFFLINE_QUEUE_CAPACITY) return;
    strncpy(queue_[queueCount_].topic, topic, sizeof(queue_[queueCount_].topic) - 1);
    queue_[queueCount_].topic[sizeof(queue_[queueCount_].topic) - 1] = '\0';
    strncpy(queue_[queueCount_].payload, payload, sizeof(queue_[queueCount_].payload) - 1);
    queue_[queueCount_].payload[sizeof(queue_[queueCount_].payload) - 1] = '\0';
    ++queueCount_;
}

void MqttClient::flushQueue() {
    while (queueCount_ > 0 && mqtt.connected()) {
        if (!mqtt.publish(queue_[0].topic, queue_[0].payload)) break;
        for (uint8_t i = 1; i < queueCount_; ++i) queue_[i - 1] = queue_[i];
        --queueCount_;
    }
}

void MqttClient::publishEvent(const SchedulerEvent& event, uint32_t sequence) {
    JsonDocument doc;
    doc["device_id"] = AppConfig::DEVICE_ID;
    doc["event"] = eventTypeName(event.type);
    doc["slot_id"] = event.slotId;
    doc["schedule_id"] = event.scheduleId;
    doc["scheduled_minute"] = event.scheduledMinute;
    doc["occurred_minute"] = event.occurredMinute;
    doc["delay_minutes"] = event.delayMinutes;
    doc["seq"] = sequence;
    char payload[320]; serializeJson(doc, payload, sizeof(payload));
    publishOrQueue("pillbox/PB01/event", payload);
}

void MqttClient::publishEnvironment(float temperatureC, float humidityPercent, bool sensorOk, uint32_t sequence) {
    JsonDocument doc;
    doc["device_id"] = AppConfig::DEVICE_ID;
    doc["temperature_c"] = temperatureC;
    doc["humidity_percent"] = humidityPercent;
    doc["sensor_ok"] = sensorOk;
    doc["seq"] = sequence;
    char payload[240]; serializeJson(doc, payload, sizeof(payload));
    publishOrQueue("pillbox/PB01/environment", payload);
}

void MqttClient::publishHeartbeat(const char* state, uint32_t sequence) {
    JsonDocument doc;
    doc["device_id"] = AppConfig::DEVICE_ID; doc["status"] = wifi_.connected() ? "online" : "offline";
    doc["state"] = state; doc["seq"] = sequence;
    char payload[220]; serializeJson(doc, payload, sizeof(payload));
    publishOrQueue("pillbox/PB01/heartbeat", payload);
}

void MqttClient::publishStatus(const char* state, uint32_t sequence) {
    JsonDocument doc; doc["device_id"] = AppConfig::DEVICE_ID; doc["state"] = state; doc["seq"] = sequence;
    char payload[180]; serializeJson(doc, payload, sizeof(payload));
    publishOrQueue("pillbox/PB01/status", payload);
}
