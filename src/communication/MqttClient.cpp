#include "communication/MqttClient.h"
#include "communication/WifiManager.h"
#include "config/AppConfig.h"
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include <RTClib.h>
#include <time.h>

#if PILLBOX_MQTT_TLS
#include <WiFiClientSecure.h>
static WiFiClientSecure netClient;
#else
static WiFiClient netClient;
#endif
static PubSubClient mqtt(netClient);
static MqttClient* currentClient = nullptr;
static char statusTopic[80];
static char commandTopic[80];

static void mqttCallback(char* topic, byte* payload, unsigned int length) {
    if (!currentClient || strcmp(topic,commandTopic)) return;
    if (length>=320) return; // Reject, rather than execute a truncated command.
    char message[320] = {0};
    const unsigned int copyLength = length < sizeof(message) - 1 ? length : sizeof(message) - 1;
    memcpy(message, payload, copyLength);
    currentClient->dispatchCommand(message);
}

MqttClient::MqttClient(WifiManager& wifi) : wifi_(wifi) {}

void MqttClient::begin() {
    snprintf(statusTopic,sizeof(statusTopic),"pillbox/%s/status",AppConfig::DEVICE_ID);
    snprintf(commandTopic,sizeof(commandTopic),"pillbox/%s/command",AppConfig::DEVICE_ID);
#if PILLBOX_MQTT_TLS
    netClient.setCACert(PILLBOX_MQTT_CA_CERT);
    netClient.setHandshakeTimeout(8);
#endif
    configTime(0,0,AppConfig::NTP_SERVER);
    snprintf(bootId_, sizeof(bootId_), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
    mqtt.setBufferSize(1536);
    mqtt.setSocketTimeout(1);
    mqtt.setKeepAlive(AppConfig::MQTT_KEEPALIVE_SECONDS);
    mqtt.setServer(AppConfig::MQTT_HOST, AppConfig::MQTT_PORT);
    mqtt.setCallback(mqttCallback);
    currentClient = this;
    mutex_ = xSemaphoreCreateMutex();
    if (!mutex_ || xTaskCreate(networkTask,"pillbox-mqtt",8192,this,1,nullptr)!=pdPASS) Serial.println("ERROR: MQTT worker unavailable");
}

void MqttClient::update() {
    if (!mutex_) return;
    // Commands execute on the application task, keeping scheduler/NVS ownership local.
    Command command{}; bool available=false;
    xSemaphoreTake(mutex_,portMAX_DELAY);
    if (commands_.size()) { command=commands_.front(); commands_.pop(); available=true; }
    xSemaphoreGive(mutex_);
    if (available && handler_) handler_(context_,command.payload);
}

void MqttClient::networkTask(void* context) {
    auto* client=static_cast<MqttClient*>(context);
    for (;;) { client->networkUpdate(); vTaskDelay(pdMS_TO_TICKS(10)); }
}

void MqttClient::networkUpdate() {
    if (!wifi_.connected()) { networkConnected_=false; return; }
#if PILLBOX_MQTT_TLS
    // Certificate validity needs real UTC; RTC demo time must not bypass TLS checks.
    if (time(nullptr)<1704067200) { networkConnected_=false; return; }
#endif
    if (!mqtt.connected()) {
        networkConnected_=false;
        if (millis() - lastAttempt_ < AppConfig::MQTT_RETRY_MS) return;
        lastAttempt_ = millis();
        char will[140]; snprintf(will,sizeof(will),"{\"device_id\":\"%s\",\"status\":\"offline\"}",AppConfig::DEVICE_ID);
        const bool connected = strlen(PILLBOX_MQTT_USER) > 0
            ? mqtt.connect(AppConfig::DEVICE_ID, PILLBOX_MQTT_USER, PILLBOX_MQTT_PASSWORD, statusTopic, 1, true, will)
            : mqtt.connect(AppConfig::DEVICE_ID, statusTopic, 1, true, will);
        networkConnected_=connected;
        if (connected) {
            mqtt.subscribe(commandTopic);
            JsonDocument hello; hello["device_id"]=AppConfig::DEVICE_ID; hello["status"]="online";
            hello["boot_id"]=bootId_; hello["uptime_ms"]=millis();
            char payload[220]; serializeJson(hello,payload,sizeof(payload));
            mqtt.publish(statusTopic,payload,true);
            flushQueue();
        }
        return;
    }
    mqtt.loop();
    networkConnected_=mqtt.connected();
    flushQueue();
}

bool MqttClient::connected() const { return networkConnected_.load(); }
void MqttClient::setCommandHandler(CommandHandler handler, void* context) { handler_ = handler; context_ = context; }
void MqttClient::dispatchCommand(const char* payload) {
    if (!mutex_) return;
    Command command{}; strncpy(command.payload,payload,sizeof(command.payload)-1);
    xSemaphoreTake(mutex_,portMAX_DELAY); commands_.push(command); xSemaphoreGive(mutex_);
}

void MqttClient::publishOrQueue(const char* topic, const char* payload, bool durable, bool priority) {
    if (!mutex_ || (!durable && !connected())) return;
    Pending pending{};
    strncpy(pending.topic, topic, sizeof(pending.topic)-1);
    strncpy(pending.payload, payload, sizeof(pending.payload)-1);
    xSemaphoreTake(mutex_,portMAX_DELAY);
    if (priority) control_.push(pending); else if (durable) queue_.push(pending); else telemetry_.push(pending);
    xSemaphoreGive(mutex_);
}

void MqttClient::publishKind(const char* kind, const char* payload, bool durable, bool priority) {
    char topic[80]; snprintf(topic,sizeof(topic),"pillbox/%s/%s",AppConfig::DEVICE_ID,kind);
    publishOrQueue(topic,payload,durable,priority);
}

void MqttClient::flushQueue() {
    if (!mqtt.connected()) return;
    xSemaphoreTake(mutex_,portMAX_DELAY);
    if (!hasInFlight_) {
        if (control_.size()) { inFlight_=control_.front(); control_.pop(); hasInFlight_=true; }
        else if (queue_.size()) { inFlight_=queue_.front(); queue_.pop(); hasInFlight_=true; }
        else if (telemetry_.size()) { inFlight_=telemetry_.front(); telemetry_.pop(); hasInFlight_=true; }
    }
    xSemaphoreGive(mutex_);
    // Keep one in-flight message across failed writes. Network I/O never holds the app mutex.
    if (hasInFlight_ && mqtt.publish(inFlight_.topic,inFlight_.payload)) hasInFlight_=false;
}

void MqttClient::publishEvent(const SchedulerEvent& event, uint32_t sequence, const char* state, const char* refillSession) {
    JsonDocument doc;
    doc["device_id"] = AppConfig::DEVICE_ID;
    doc["event"] = eventTypeName(event.type);
    doc["slot_id"] = event.slotId;
    doc["schedule_id"] = event.scheduleId;
    doc["scheduled_minute"] = event.scheduledMinute;
    doc["occurred_minute"] = event.occurredMinute;
    doc["delay_minutes"] = event.delayMinutes;
    doc["seq"] = sequence;
    doc["schema_version"] = 2;
    doc["boot_id"] = bootId_;
    doc["uptime_ms"] = millis();
    if (refillSession) doc["refill_session_id"]=refillSession;
    if (state) { doc["device_state"]=state; doc["device_local_minute"]=event.occurredMinute; doc["device_epoch_local"]=event.occurredEpoch; }
    char eventId[80]; snprintf(eventId, sizeof(eventId), "%s:%s:%lu", AppConfig::DEVICE_ID, bootId_, (unsigned long)sequence);
    doc["event_id"] = eventId;
    char occurrenceId[80]; snprintf(occurrenceId, sizeof(occurrenceId), "%s:%s:%lu", AppConfig::DEVICE_ID, event.scheduleId, (unsigned long)event.occurrenceDay);
    if (event.slotId > 0 && strcmp(event.scheduleId, "NONE") && strcmp(event.scheduleId, "AMBIGUOUS") && strcmp(event.scheduleId,"REFILL")) doc["occurrence_id"] = occurrenceId;
    else doc["occurrence_id"] = nullptr;
    // RTC stores local civil time; represent it explicitly with the demo +07:00 offset.
    char scheduledAt[32], occurredAt[32];
    if (event.scheduledEpoch && event.occurredEpoch) {
        DateTime scheduled(event.scheduledEpoch), occurred(event.occurredEpoch);
        snprintf(scheduledAt, sizeof(scheduledAt), "%04u-%02u-%02uT%02u:%02u:%02u+07:00", scheduled.year(), scheduled.month(), scheduled.day(), scheduled.hour(), scheduled.minute(), scheduled.second());
        snprintf(occurredAt, sizeof(occurredAt), "%04u-%02u-%02uT%02u:%02u:%02u+07:00", occurred.year(), occurred.month(), occurred.day(), occurred.hour(), occurred.minute(), occurred.second());
        doc["scheduled_at"] = scheduledAt; doc["occurred_at"] = occurredAt;
        doc["device_time_quality"] = "rtc";
    } else { doc["scheduled_at"] = nullptr; doc["occurred_at"] = nullptr; doc["device_time_quality"] = "unsynchronized"; }
    char payload[1024]; serializeJson(doc, payload, sizeof(payload));
    publishKind("event", payload, true);
}

void MqttClient::publishEnvironment(float temperatureC, float humidityPercent, bool sensorOk, uint32_t sampledEpoch, uint32_t sequence, const char* storageStatus) {
    JsonDocument doc;
    doc["device_id"] = AppConfig::DEVICE_ID;
    doc["temperature_c"] = temperatureC;
    doc["humidity_percent"] = humidityPercent;
    doc["sensor_ok"] = sensorOk;
    doc["seq"] = sequence;
    doc["sampled_epoch_local"] = sampledEpoch;
    doc["boot_id"]=bootId_; doc["uptime_ms"]=millis(); doc["storage_status"]=storageStatus;
    char payload[384]; serializeJson(doc, payload, sizeof(payload));
    publishKind("environment", payload);
}

void MqttClient::publishHeartbeat(const char* state, uint32_t sequence, uint16_t minute, uint32_t epoch) {
    JsonDocument doc;
    doc["device_id"] = AppConfig::DEVICE_ID; doc["status"] = wifi_.connected() ? "online" : "offline";
    doc["state"] = state; doc["seq"] = sequence;
    doc["boot_id"] = bootId_;
    doc["uptime_ms"]=millis();
    doc["utc_synced"]=time(nullptr)>=1704067200;
    if (minute<1440) { doc["device_local_minute"]=minute; doc["device_epoch_local"]=epoch; }
    if (mutex_) {
        xSemaphoreTake(mutex_,portMAX_DELAY);
        doc["queue_depth"] = queue_.size(); doc["queue_dropped"] = queue_.dropped();
        xSemaphoreGive(mutex_);
    }
    char payload[384]; serializeJson(doc, payload, sizeof(payload));
    publishKind("heartbeat", payload,false,true);
}

void MqttClient::publishStatus(const char* state, uint32_t sequence) {
    JsonDocument doc; doc["device_id"] = AppConfig::DEVICE_ID; doc["state"] = state; doc["seq"] = sequence;
    doc["boot_id"]=bootId_; doc["uptime_ms"]=millis();
    char payload[180]; serializeJson(doc, payload, sizeof(payload));
    publishKind("status", payload,false,true);
}

void MqttClient::publishCommandResult(const char* commandId, const char* command, bool accepted, const Schedule* schedules, uint8_t count, const char* refillSession) {
    JsonDocument doc;
    doc["device_id"] = AppConfig::DEVICE_ID; doc["command_id"] = commandId;
    doc["command"] = command; doc["command_result"] = accepted ? "APPLIED" : "REJECTED";
    doc["boot_id"]=bootId_; doc["uptime_ms"]=millis();
    if (refillSession) doc["refill_session_id"]=refillSession;
    if (accepted && strcmp(command, "UPDATE_SCHEDULE") == 0) {
        auto values = doc["schedules"].to<JsonArray>();
        for (uint8_t i=0; i<count; ++i) {
            auto value = values.add<JsonObject>();
            value["schedule_id"]=schedules[i].scheduleId; value["hour"]=schedules[i].hour;
            value["minute"]=schedules[i].minute; value["enabled"]=schedules[i].enabled;
        }
    }
    char payload[768]; serializeJson(doc,payload,sizeof(payload));
    publishKind("status",payload,false,true);
}
