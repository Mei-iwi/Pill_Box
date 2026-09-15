#include <cassert>
#include <iostream>
#include "app/Scheduler.h"

static SchedulerEvent take(Scheduler& scheduler) {
    SchedulerEvent event{};
    assert(scheduler.takeEvent(event));
    return event;
}

int main() {
    Scheduler scheduler;
    SchedulerEvent event{};

    scheduler.update(7 * 60 + 59);
    assert(!scheduler.takeEvent(event));

    scheduler.update(8 * 60);
    assert(take(scheduler).type == EventType::REMINDER_STARTED);
    scheduler.update(8 * 60);
    assert(!scheduler.takeEvent(event)); // duplicate reminder protection
    assert(!scheduler.recordSlotOpen(2, 8 * 60 + 1));
    assert(take(scheduler).type == EventType::WRONG_SLOT);
    assert(scheduler.hasActiveReminder() && scheduler.activeSlot() == 1);
    assert(scheduler.recordSlotOpen(1, 8 * 60 + 3));
    assert(take(scheduler).type == EventType::TAKEN_ON_TIME);

    scheduler.update(14 * 60);
    assert(take(scheduler).type == EventType::REMINDER_STARTED);
    assert(scheduler.recordSlotOpen(2, 14 * 60 + 30));
    event = take(scheduler);
    assert(event.type == EventType::TAKEN_LATE && event.delayMinutes == 30);

    scheduler.update(20 * 60);
    assert(take(scheduler).type == EventType::REMINDER_STARTED);
    scheduler.update(22 * 60 + 6);
    assert(take(scheduler).type == EventType::MISSED);

    assert(!scheduler.updateSchedule(4, 8, 0, true));
    std::cout << "HOST_SCHEDULER_TESTS_PASS\n";
    return 0;
}
