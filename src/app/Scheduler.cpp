#include "app/Scheduler.h"

Scheduler::Scheduler() { loadDefaults(); }

void Scheduler::loadDefaults() {
#ifdef PILLBOX_SIMULATION
    schedules_[0] = {"S1", 1, 8, 0, true, 0, 1};
    schedules_[1] = {"S2", 2, 8, 2, true, 0, 1};
    schedules_[2] = {"S3", 3, 8, 4, true, 0, 1};
#else
    schedules_[0] = {"S1", 1, 8, 0, true, 5, 120};
    schedules_[1] = {"S2", 2, 14, 0, true, 5, 120};
    schedules_[2] = {"S3", 3, 20, 0, true, 5, 120};
#endif
    active_ = false;
    eventReady_ = false;
    lastMinute_ = 1440;
    lastReminderMinute_ = 1440;
}

void Scheduler::queue(EventType type, uint8_t slot, const char* id, uint16_t scheduled, uint16_t occurred, int16_t delay) {
    if (eventReady_) return;
    pending_ = {type, slot, id, scheduled, occurred, delay};
    eventReady_ = true;
}

void Scheduler::update(uint16_t currentMinute) {
    if (currentMinute > 1439) return;
    if (lastMinute_ > currentMinute + 1) lastReminderMinute_ = 1440; // midnight rollover
    lastMinute_ = currentMinute;

    if (active_) {
        const uint16_t elapsed = currentMinute >= activeSchedule_.hour * 60 + activeSchedule_.minute
            ? currentMinute - (activeSchedule_.hour * 60 + activeSchedule_.minute) : 0;
        if (elapsed > activeSchedule_.onTimeWindowMinutes + activeSchedule_.lateTrackingWindowMinutes) {
            queue(EventType::MISSED, activeSchedule_.slotId, activeSchedule_.scheduleId,
                  activeSchedule_.hour * 60 + activeSchedule_.minute, currentMinute, 0);
            active_ = false;
        }
    }

    for (const auto& schedule : schedules_) {
        const uint16_t scheduledMinute = schedule.hour * 60 + schedule.minute;
        if (schedule.enabled && currentMinute == scheduledMinute && lastReminderMinute_ != currentMinute && !active_) {
            activeSchedule_ = schedule;
            active_ = true;
            lastReminderMinute_ = currentMinute;
            queue(EventType::REMINDER_STARTED, schedule.slotId, schedule.scheduleId, scheduledMinute, currentMinute, 0);
            break;
        }
    }
}

bool Scheduler::takeEvent(SchedulerEvent& event) {
    if (!eventReady_) return false;
    event = pending_;
    eventReady_ = false;
    return true;
}

bool Scheduler::recordSlotOpen(uint8_t slotId, uint16_t currentMinute) {
    if (!active_) {
        queue(EventType::WRONG_SLOT, slotId, "NONE", currentMinute, currentMinute, 0);
        return false;
    }
    const uint16_t scheduled = activeSchedule_.hour * 60 + activeSchedule_.minute;
    if (slotId != activeSchedule_.slotId) {
        queue(EventType::WRONG_SLOT, slotId, activeSchedule_.scheduleId, scheduled, currentMinute, 0);
        return false;
    }
    const uint16_t elapsed = currentMinute >= scheduled ? currentMinute - scheduled : 0;
    if (elapsed <= activeSchedule_.onTimeWindowMinutes) {
        queue(EventType::TAKEN_ON_TIME, slotId, activeSchedule_.scheduleId, scheduled, currentMinute, elapsed);
        active_ = false;
        return true;
    }
    if (elapsed <= activeSchedule_.onTimeWindowMinutes + activeSchedule_.lateTrackingWindowMinutes) {
        queue(EventType::TAKEN_LATE, slotId, activeSchedule_.scheduleId, scheduled, currentMinute, elapsed);
        active_ = false;
        return true;
    }
    queue(EventType::MISSED, slotId, activeSchedule_.scheduleId, scheduled, currentMinute, 0);
    active_ = false;
    return false;
}

bool Scheduler::updateSchedule(uint8_t slotId, uint8_t hour, uint8_t minute, bool enabled) {
    if (slotId < 1 || slotId > MAX_SCHEDULES || hour > 23 || minute > 59) return false;
    schedules_[slotId - 1].hour = hour;
    schedules_[slotId - 1].minute = minute;
    schedules_[slotId - 1].enabled = enabled;
    return true;
}
