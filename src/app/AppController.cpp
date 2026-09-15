#include "app/AppController.h"
#include "config/AppConfig.h"
#include <Arduino.h>
#include <ArduinoJson.h>

AppController::AppController() : mqtt_(wifi_) {}

void AppController::begin() {
    Serial.begin(115200);
    rtc_.begin();
    buttons_.begin();
    leds_.begin();
    buzzer_.begin();
    environment_.begin();
    settings_.begin();
    if (!settings_.load(stored_)) settings_.save(stored_);
    wifi_.begin();
    mqtt_.begin();
    mqtt_.setCommandHandler(handleCommand, this);
}

void AppController::update() {
    wifi_.update();
    mqtt_.update();
    buttons_.update();
    buzzer_.update();
    environment_.update();

    const ClockTime now = rtc_.now();
    scheduler_.update(now.minuteOfDay);
    processPendingEvent();

    for (uint8_t slot = 1; slot <= 3; ++slot) {
        if (buttons_.wasPressed(slot)) {
            scheduler_.recordSlotOpen(slot, now.minuteOfDay);
            processPendingEvent();
        }
    }

    if (scheduler_.hasActiveReminder()) {
        leds_.setSlot(scheduler_.activeSlot(), !alertSilenced_);
        if (!alertSilenced_ && !buzzer_.isActive()) buzzer_.start();
        state_ = "REMINDING";
    } else if (strcmp(state_, "REMINDING") == 0) {
        leds_.allOff();
        buzzer_.stop();
        state_ = "IDLE";
    }

    if (millis() - lastHeartbeat_ >= AppConfig::HEARTBEAT_MS) {
        lastHeartbeat_ = millis();
        mqtt_.publishHeartbeat(state_, ++sequence_);
    }
    if (millis() - lastEnvironment_ >= AppConfig::ENVIRONMENT_PUBLISH_MS) {
        lastEnvironment_ = millis();
        const auto reading = environment_.reading();
        mqtt_.publishEnvironment(reading.temperatureC, reading.humidityPercent, reading.sensorOk, ++sequence_);
        if (reading.sensorOk && (reading.temperatureC > stored_.maxTemperatureC || reading.humidityPercent > stored_.maxHumidityPercent)) {
            SchedulerEvent warning{EventType::STORAGE_WARNING, 0, "ENV", 0, now.minuteOfDay, 0};
            mqtt_.publishEvent(warning, ++sequence_);
        }
    }
}

void AppController::processPendingEvent() { SchedulerEvent event; if (scheduler_.takeEvent(event)) handleEvent(event); }

void AppController::handleEvent(const SchedulerEvent& event) {
    if (event.type == EventType::REMINDER_STARTED) { alertSilenced_ = false; state_ = "REMINDING"; buzzer_.start(); }
    if (event.type == EventType::TAKEN_ON_TIME || event.type == EventType::TAKEN_LATE || event.type == EventType::MISSED) {
        alertSilenced_ = false; leds_.setSlot(event.slotId, false); buzzer_.stop(); state_ = "IDLE";
    }
    mqtt_.publishEvent(event, ++sequence_);
}

void AppController::handleCommand(void* context, const char* payload) {
    static_cast<AppController*>(context)->handleCommandPayload(payload);
}

void AppController::handleCommandPayload(const char* payload) {
    JsonDocument doc;
    if (deserializeJson(doc, payload)) return;
    const char* command = doc["command"] | "";
    if (strcmp(command, "CLEAR_ALERT") == 0) {
        alertSilenced_ = true; buzzer_.stop(); leds_.allOff(); mqtt_.publishStatus(state_, ++sequence_); return;
    }
    if (strcmp(command, "REQUEST_STATUS") == 0) { mqtt_.publishStatus(state_, ++sequence_); return; }
    if (strcmp(command, "UPDATE_SCHEDULE") == 0) {
        if (!doc["slot_id"].is<uint8_t>() || !doc["hour"].is<uint8_t>() ||
            !doc["minute"].is<uint8_t>() || !doc["enabled"].is<bool>()) return;
        const uint8_t slot = doc["slot_id"] | 0;
        const uint8_t hour = doc["hour"] | 0;
        const uint8_t minute = doc["minute"] | 0;
        const bool enabled = doc["enabled"] | true;
        if (scheduler_.updateSchedule(slot, hour, minute, enabled)) mqtt_.publishStatus(state_, ++sequence_);
    }
}
