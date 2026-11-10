#include "app/Scheduler.h"
#include <string.h>

Scheduler::Scheduler() { loadDefaults(); }

void Scheduler::loadDefaults() {
    schedules_[0] = {"S1", "MED001", 1, 8, 0, true, 15, 240};
    schedules_[1] = {"S2", "MED001", 1, 14, 0, true, 15, 240};
    schedules_[2] = {"S3", "MED002", 2, 9, 0, true, 15, 240};
    schedules_[3] = {"S4", "MED003", 3, 20, 0, true, 15, 240};
    for (uint8_t i = 0; i < MAX_SCHEDULES; ++i) {
        occurrences_[i] = {};
    }
    eventHead_ = 0;
    eventCount_ = 0;
    currentDay_ = 0;
    ledger_ = {};
}

void Scheduler::resetForDay(uint32_t dayKey) {
    if (currentDay_ == dayKey) return;
    currentDay_ = dayKey;
    for (auto& occurrence : occurrences_) occurrence = {};
}

void Scheduler::queue(EventType type, uint8_t slot, const char* id, uint16_t scheduled,
                      uint16_t occurred, int16_t delay, uint32_t dayKey,
                      uint32_t scheduledEpoch, uint32_t occurredEpoch) {
    if (eventCount_ >= EVENT_QUEUE_SIZE) return;
    const uint8_t tail = (eventHead_ + eventCount_) % EVENT_QUEUE_SIZE;
    events_[tail] = {type, slot, id, scheduled, occurred, delay, dayKey, scheduledEpoch, occurredEpoch};
    ++eventCount_;
}

void Scheduler::update(uint32_t dayKey, uint16_t currentMinute, uint32_t currentEpoch) {
    if (currentMinute > 1439 || dayKey == 0) return;
    resetForDay(dayKey);

    for (uint8_t i = 0; i < MAX_SCHEDULES; ++i) {
        const Schedule& schedule = schedules_[i];
        const uint16_t scheduledMinute = schedule.hour * 60 + schedule.minute;
        if (schedule.enabled && currentMinute >= scheduledMinute &&
            currentMinute - scheduledMinute <= schedule.lateTrackingWindowMinutes &&
            ledger_.completed[i] != dayKey && !occurrences_[i].active) {
            const uint32_t scheduledEpoch = currentEpoch > 0 ? currentEpoch - (currentEpoch % 60U) - (currentMinute - scheduledMinute) * 60UL : 0;
            occurrences_[i] = {true, ledger_.missed[i] == dayKey, schedule, dayKey, scheduledMinute, scheduledEpoch};
            if (ledger_.started[i] != dayKey) {
                ledger_.started[i] = dayKey;
                queue(EventType::REMINDER_STARTED, schedule.slotId, schedule.scheduleId,
                      scheduledMinute, currentMinute, 0, dayKey, scheduledEpoch, currentEpoch);
            }
        }
    }

    for (uint8_t i = 0; i < MAX_SCHEDULES; ++i) {
        auto& occurrence = occurrences_[i];
        if (!occurrence.active || occurrence.dayKey != dayKey || currentMinute < occurrence.scheduledMinute) continue;
        const uint16_t elapsed = currentMinute - occurrence.scheduledMinute;
        if (!occurrence.missedEmitted && elapsed >= occurrence.schedule.onTimeWindowMinutes) {
            occurrence.missedEmitted = true;
            ledger_.missed[i] = dayKey;
            queue(EventType::MISSED, occurrence.schedule.slotId, occurrence.schedule.scheduleId,
                  occurrence.scheduledMinute, currentMinute, elapsed, dayKey,
                  occurrence.scheduledEpoch, currentEpoch);
        }
        if (elapsed > occurrence.schedule.lateTrackingWindowMinutes) {
            occurrence.active = false;
        }
    }
}

bool Scheduler::takeEvent(SchedulerEvent& event) {
    if (eventCount_ == 0) return false;
    event = events_[eventHead_];
    eventHead_ = (eventHead_ + 1) % EVENT_QUEUE_SIZE;
    --eventCount_;
    return true;
}

bool Scheduler::recordSlotOpen(uint8_t slotId, uint32_t dayKey, uint16_t currentMinute, uint32_t currentEpoch) {
    if (slotId < 1 || slotId > 3 || dayKey != currentDay_ || currentMinute > 1439) return false;
    uint8_t candidates = 0;
    int8_t candidateIndex = -1;
    for (uint8_t i = 0; i < MAX_SCHEDULES; ++i) {
        const auto& occurrence = occurrences_[i];
        if (!occurrence.active || occurrence.dayKey != dayKey || occurrence.schedule.slotId != slotId ||
            currentMinute < occurrence.scheduledMinute) continue;
        const uint16_t elapsed = currentMinute - occurrence.scheduledMinute;
        if (elapsed <= occurrence.schedule.lateTrackingWindowMinutes) {
            ++candidates;
            candidateIndex = static_cast<int8_t>(i);
        }
    }

    if (candidates > 1) {
        queue(EventType::AMBIGUOUS_OPEN, slotId, "AMBIGUOUS", currentMinute, currentMinute, 0,
              dayKey, currentEpoch, currentEpoch);
        return false;
    }

    if (candidateIndex < 0) {
        const int8_t activeIndex = firstActiveIndex();
        if (activeIndex >= 0) {
            const auto& expected = occurrences_[activeIndex];
            queue(EventType::WRONG_SLOT, slotId, expected.schedule.scheduleId,
                  expected.scheduledMinute, currentMinute, 0, dayKey,
                  expected.scheduledEpoch, currentEpoch);
        } else {
            queue(EventType::UNSCHEDULED_OPEN, slotId, "NONE", currentMinute, currentMinute, 0,
                  dayKey, currentEpoch, currentEpoch);
        }
        return false;
    }

    auto& occurrence = occurrences_[candidateIndex];
    const uint16_t elapsed = currentMinute - occurrence.scheduledMinute;
    const EventType result = elapsed < occurrence.schedule.onTimeWindowMinutes
        ? EventType::TAKEN_ON_TIME : EventType::TAKEN_LATE;
    queue(result, slotId, occurrence.schedule.scheduleId, occurrence.scheduledMinute,
          currentMinute, elapsed, dayKey, occurrence.scheduledEpoch, currentEpoch);
    occurrence.active = false;
    ledger_.completed[candidateIndex] = dayKey;
    return true;
}

int8_t Scheduler::firstActiveIndex() const {
    int8_t result = -1;
    for (uint8_t i = 0; i < MAX_SCHEDULES; ++i) {
        if (!occurrences_[i].active) continue;
        if (result < 0 || occurrences_[i].scheduledMinute < occurrences_[result].scheduledMinute) result = i;
    }
    return result;
}

bool Scheduler::hasActiveReminder() const { return firstActiveIndex() >= 0; }

bool Scheduler::hasOverdueReminder() const {
    for (const auto& occurrence : occurrences_) {
        if (occurrence.active && occurrence.missedEmitted) return true;
    }
    return false;
}

uint8_t Scheduler::activeSlot() const {
    const int8_t index = firstActiveIndex();
    return index >= 0 ? occurrences_[index].schedule.slotId : 0;
}

bool Scheduler::slotReminding(uint8_t slot) const {
    for (const auto& occurrence : occurrences_) if (occurrence.active && occurrence.schedule.slotId==slot) return true;
    return false;
}

bool Scheduler::updateSchedule(const char* scheduleId, uint8_t hour, uint8_t minute, bool enabled) {
    if (!scheduleId || hour > 23 || minute > 59) return false;
    for (auto& schedule : schedules_) {
        if (strcmp(schedule.scheduleId, scheduleId) == 0) {
            schedule.hour = hour;
            schedule.minute = minute;
            schedule.enabled = enabled;
            return true;
        }
    }
    return false;
}
