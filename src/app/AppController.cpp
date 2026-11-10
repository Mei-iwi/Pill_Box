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
    StoredSchedules savedSchedules;
    if (settings_.loadSchedules(savedSchedules)) {
        for (uint8_t i=0;i<Scheduler::MAX_SCHEDULES;++i) scheduler_.updateSchedule(scheduler_.schedules()[i].scheduleId,savedSchedules.hour[i],savedSchedules.minute[i],savedSchedules.enabled[i]);
    }
    SchedulerLedger ledger;
    if (settings_.loadLedger(&ledger, sizeof(ledger))) scheduler_.restoreLedger(ledger);
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

#ifdef PILLBOX_SIMULATION
    // Wokwi Serial Monitor: TIME 08:00, TIME 08:15, TIME 10:00, TIME 14:00.
    static char input[24]; static uint8_t inputLength=0;
    while (Serial.available()) {
        const char c=Serial.read();
        if (c=='\n') { input[inputLength]='\0'; unsigned hour,minute;
            if (sscanf(input,"TIME %u:%u",&hour,&minute)==2 && hour<24 && minute<60 && rtc_.setDemoTime(hour,minute)) Serial.println("DEMO clock updated");
            inputLength=0;
        } else if (c!='\r' && inputLength<sizeof(input)-1) input[inputLength++]=c;
    }
#endif

    const ClockTime now = rtc_.now();
    scheduler_.update(now.dayKey, now.minuteOfDay, now.epoch);
    while (true) { SchedulerEvent event; if (!scheduler_.takeEvent(event)) break; handleEvent(event); }

    for (uint8_t slot = 1; slot <= 3; ++slot) {
        if (buttons_.wasPressed(slot)) {
            scheduler_.recordSlotOpen(slot, now.dayKey, now.minuteOfDay, now.epoch);
            while (true) { SchedulerEvent event; if (!scheduler_.takeEvent(event)) break; handleEvent(event); }
        }
    }

    if (scheduler_.hasActiveReminder()) {
        for (uint8_t slot=1;slot<=3;++slot) leds_.setSlot(slot,scheduler_.slotReminding(slot) && !alertSilenced_);
        if (!alertSilenced_ && !buzzer_.isActive()) buzzer_.start();
        state_ = scheduler_.hasOverdueReminder() ? "ALERT" : "REMINDING";
    } else if (strcmp(state_, "REMINDING") == 0 || strcmp(state_, "ALERT") == 0) {
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
        mqtt_.publishEnvironment(reading.temperatureC, reading.humidityPercent, reading.sensorOk, now.epoch, ++sequence_);
        const auto transition=storageMonitor_.sample(reading.temperatureC,reading.humidityPercent,reading.sensorOk,
            stored_.maxTemperatureC,stored_.maxHumidityPercent,AppConfig::ENVIRONMENT_HYSTERESIS,AppConfig::ENVIRONMENT_CONFIRM_SAMPLES);
        if (transition!=StorageTransition::NONE) {
            const EventType type=transition==StorageTransition::SENSOR_ERROR ? EventType::SENSOR_ERROR :
                transition==StorageTransition::WARNING ? EventType::STORAGE_WARNING : EventType::STORAGE_NORMAL;
            SchedulerEvent event{type,0,"ENV",0,now.minuteOfDay,0,now.dayKey,now.epoch,now.epoch};
            mqtt_.publishEvent(event,++sequence_);
        }
    }
}

void AppController::handleEvent(const SchedulerEvent& event) {
    if (event.type == EventType::REMINDER_STARTED || event.type == EventType::MISSED ||
        event.type == EventType::TAKEN_ON_TIME || event.type == EventType::TAKEN_LATE) {
        const auto& ledger = scheduler_.ledger();
        if (!settings_.saveLedger(&ledger, sizeof(ledger))) Serial.println("WARN: occurrence ledger not persisted");
    }
    if (event.type == EventType::REMINDER_STARTED) { alertSilenced_ = false; state_ = "REMINDING"; buzzer_.start(); }
    if (event.type == EventType::TAKEN_ON_TIME || event.type == EventType::TAKEN_LATE) {
        alertSilenced_ = false; leds_.setSlot(event.slotId, false); buzzer_.stop(); state_ = "IDLE";
    }
    if (event.type == EventType::MISSED) state_ = "ALERT";
    mqtt_.publishEvent(event, ++sequence_);
}

void AppController::handleCommand(void* context, const char* payload) {
    static_cast<AppController*>(context)->handleCommandPayload(payload);
}

void AppController::handleCommandPayload(const char* payload) {
    JsonDocument doc;
    if (deserializeJson(doc, payload)) return;
    const char* command = doc["command"] | "";
    const char* commandId = doc["command_id"] | "";
    if (strcmp(command, "CLEAR_ALERT") == 0) {
        alertSilenced_ = true; buzzer_.stop(); leds_.allOff(); mqtt_.publishStatus(state_, ++sequence_);
        mqtt_.publishCommandResult(commandId,command,true,nullptr,0); return;
    }
    if (strcmp(command, "REQUEST_STATUS") == 0) { mqtt_.publishStatus(state_, ++sequence_); mqtt_.publishCommandResult(commandId,command,true,nullptr,0); return; }
    if (strcmp(command, "UPDATE_SCHEDULE") == 0) {
        if (!doc["schedule_id"].is<const char*>() || !doc["hour"].is<uint8_t>() ||
            !doc["minute"].is<uint8_t>() || !doc["enabled"].is<bool>()) return;
        const char* scheduleId = doc["schedule_id"] | "";
        const uint8_t hour = doc["hour"] | 0;
        const uint8_t minute = doc["minute"] | 0;
        const bool enabled = doc["enabled"] | true;
        StoredSchedules prior, next;
        for (uint8_t i=0;i<Scheduler::MAX_SCHEDULES;++i) { const auto& s=scheduler_.schedules()[i]; prior.hour[i]=s.hour; prior.minute[i]=s.minute; prior.enabled[i]=s.enabled; }
        bool accepted=scheduler_.updateSchedule(scheduleId, hour, minute, enabled);
        if (accepted) {
            for (uint8_t i=0;i<Scheduler::MAX_SCHEDULES;++i) { const auto& s=scheduler_.schedules()[i]; next.hour[i]=s.hour; next.minute[i]=s.minute; next.enabled[i]=s.enabled; }
            accepted=settings_.saveSchedules(next);
            if (!accepted) for (uint8_t i=0;i<Scheduler::MAX_SCHEDULES;++i) scheduler_.updateSchedule(scheduler_.schedules()[i].scheduleId,prior.hour[i],prior.minute[i],prior.enabled[i]);
        }
        mqtt_.publishCommandResult(commandId,command,accepted,scheduler_.schedules(),Scheduler::MAX_SCHEDULES);
    }
}
