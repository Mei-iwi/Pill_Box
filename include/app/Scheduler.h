#pragma once

#include "domain/DomainTypes.h"

struct SchedulerLedger {
    uint32_t version = 1;
    uint32_t started[4]{};
    uint32_t completed[4]{};
    uint32_t missed[4]{};
};

class Scheduler {
public:
    static constexpr uint8_t MAX_SCHEDULES = 4;

    Scheduler();
    void loadDefaults();
    void update(uint32_t dayKey, uint16_t currentMinute, uint32_t currentEpoch = 0);
    bool takeEvent(SchedulerEvent& event);
    bool recordSlotOpen(uint8_t slotId, uint32_t dayKey, uint16_t currentMinute, uint32_t currentEpoch = 0);
    bool hasActiveReminder() const;
    bool hasOverdueReminder() const;
    uint8_t activeSlot() const;
    bool slotReminding(uint8_t slot) const;
    const Schedule* schedules() const { return schedules_; }
    bool updateSchedule(const char* scheduleId, uint8_t hour, uint8_t minute, bool enabled);
    const SchedulerLedger& ledger() const { return ledger_; }
    void restoreLedger(const SchedulerLedger& ledger) { if (ledger.version == 1) ledger_ = ledger; }

private:
    Schedule schedules_[MAX_SCHEDULES];
    struct Occurrence {
        bool active;
        bool missedEmitted;
        Schedule schedule;
        uint32_t dayKey;
        uint16_t scheduledMinute;
        uint32_t scheduledEpoch;
    } occurrences_[MAX_SCHEDULES]{};
    SchedulerLedger ledger_{};
    static constexpr uint8_t EVENT_QUEUE_SIZE = 8;
    SchedulerEvent events_[EVENT_QUEUE_SIZE]{};
    uint8_t eventHead_ = 0;
    uint8_t eventCount_ = 0;
    uint32_t currentDay_ = 0;
    void resetForDay(uint32_t dayKey);
    int8_t firstActiveIndex() const;
    void queue(EventType type, uint8_t slot, const char* id, uint16_t scheduled,
               uint16_t occurred, int16_t delay, uint32_t dayKey,
               uint32_t scheduledEpoch, uint32_t occurredEpoch);
};
