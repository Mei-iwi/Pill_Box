#pragma once

#include <stdint.h>

enum class EventType : uint8_t {
    REMINDER_STARTED,
    TAKEN_ON_TIME,
    TAKEN_LATE,
    MISSED,
    WRONG_SLOT,
    STORAGE_WARNING,
    DEVICE_ONLINE,
    DEVICE_OFFLINE
};

struct Schedule {
    const char* scheduleId;
    uint8_t slotId;
    uint8_t hour;
    uint8_t minute;
    bool enabled;
    uint16_t onTimeWindowMinutes;
    uint16_t lateTrackingWindowMinutes;
};

struct SchedulerEvent {
    EventType type;
    uint8_t slotId;
    const char* scheduleId;
    uint16_t scheduledMinute;
    uint16_t occurredMinute;
    int16_t delayMinutes;
};

inline const char* eventTypeName(EventType type) {
    switch (type) {
        case EventType::REMINDER_STARTED: return "REMINDER_STARTED";
        case EventType::TAKEN_ON_TIME: return "TAKEN_ON_TIME";
        case EventType::TAKEN_LATE: return "TAKEN_LATE";
        case EventType::MISSED: return "MISSED";
        case EventType::WRONG_SLOT: return "WRONG_SLOT";
        case EventType::STORAGE_WARNING: return "STORAGE_WARNING";
        case EventType::DEVICE_ONLINE: return "DEVICE_ONLINE";
        case EventType::DEVICE_OFFLINE: return "DEVICE_OFFLINE";
    }
    return "UNKNOWN";
}
