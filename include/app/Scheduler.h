#pragma once

#include "domain/DomainTypes.h"

class Scheduler {
public:
    static constexpr uint8_t MAX_SCHEDULES = 3;

    Scheduler();
    void loadDefaults();
    void update(uint16_t currentMinute);
    bool takeEvent(SchedulerEvent& event);
    bool recordSlotOpen(uint8_t slotId, uint16_t currentMinute);
    bool hasActiveReminder() const { return active_; }
    uint8_t activeSlot() const { return active_ ? activeSchedule_.slotId : 0; }
    const Schedule* schedules() const { return schedules_; }
    bool updateSchedule(uint8_t slotId, uint8_t hour, uint8_t minute, bool enabled);

private:
    Schedule schedules_[MAX_SCHEDULES];
    Schedule activeSchedule_{};
    bool active_ = false;
    bool eventReady_ = false;
    SchedulerEvent pending_{};
    uint16_t lastMinute_ = 1440;
    uint16_t lastReminderMinute_ = 1440;
    void queue(EventType type, uint8_t slot, const char* id, uint16_t scheduled, uint16_t occurred, int16_t delay);
};
