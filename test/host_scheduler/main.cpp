#include <cassert>
#include <iostream>
#include "app/Scheduler.h"
#include "domain/EventBuffer.h"
#include "domain/StorageMonitor.h"

static SchedulerEvent take(Scheduler& scheduler) {
    SchedulerEvent event{};
    assert(scheduler.takeEvent(event));
    return event;
}

int main() {
    StorageMonitor restartedMonitor;
    assert(restartedMonitor.sample(25,50,true,30,70,2,3)==StorageTransition::NONE);
    assert(restartedMonitor.sample(25,50,true,30,70,2,3)==StorageTransition::NONE);
    assert(restartedMonitor.sample(25,50,true,30,70,2,3)==StorageTransition::NORMAL);
    assert(std::string(restartedMonitor.status())=="NORMAL");
    assert(restartedMonitor.sample(NAN,50,false,30,70,2,3)==StorageTransition::SENSOR_ERROR);
    assert(std::string(restartedMonitor.status())=="SENSOR_ERROR");
    assert(restartedMonitor.sample(25,50,true,30,70,2,3)==StorageTransition::NONE);
    assert(restartedMonitor.sample(25,50,true,30,70,2,3)==StorageTransition::NONE);
    assert(restartedMonitor.sample(25,50,true,30,70,2,3)==StorageTransition::NORMAL);
    StorageMonitor monitor;
    auto sample=[&](float t,float h,bool ok=true){return monitor.sample(t,h,ok,30,70,2,3);};
    assert(sample(25,50)==StorageTransition::NONE);
    assert(sample(31,72)==StorageTransition::NONE);
    assert(sample(31,72)==StorageTransition::NONE);
    assert(sample(31,72)==StorageTransition::WARNING);
    for(int i=0;i<4;++i) assert(sample(29,69)==StorageTransition::NONE);
    assert(sample(25,50)==StorageTransition::NONE);
    assert(sample(25,50)==StorageTransition::NONE);
    assert(sample(25,50)==StorageTransition::NORMAL);
    assert(sample(NAN,50)==StorageTransition::SENSOR_ERROR);
    assert(sample(NAN,50)==StorageTransition::NONE);
    EventBuffer<int,16> fifo;
    for (int i=0;i<18;++i) fifo.push(i);
    assert(fifo.size()==16 && fifo.dropped()==2);
    for (int i=2;i<18;++i) { assert(fifo.front()==i); fifo.pop(); }
    assert(fifo.size()==0);
    Scheduler scheduler;
    scheduler.updateSchedule("S3",9,0,false); // Isolate S1/S2 while skipping test-clock hours.
    SchedulerEvent event{};

    const uint32_t day = 20261110;
    scheduler.update(day, 7 * 60 + 59);
    assert(!scheduler.takeEvent(event));

    scheduler.update(day, 8 * 60);
    assert(take(scheduler).type == EventType::REMINDER_STARTED);
    scheduler.update(day, 8 * 60);
    assert(!scheduler.takeEvent(event)); // duplicate reminder protection
    assert(!scheduler.recordSlotOpen(2, day, 8 * 60 + 1));
    assert(take(scheduler).type == EventType::WRONG_SLOT);
    assert(scheduler.hasActiveReminder() && scheduler.activeSlot() == 1);
    scheduler.update(day, 8 * 60 + 15);
    assert(take(scheduler).type == EventType::MISSED);
    assert(scheduler.hasOverdueReminder());
    scheduler.update(day, 10 * 60);
    assert(scheduler.recordSlotOpen(1, day, 10 * 60));
    event = take(scheduler);
    assert(event.type == EventType::TAKEN_LATE && event.delayMinutes == 120);
    assert(event.occurrenceDay == day);
    assert(!scheduler.recordSlotOpen(1, day, 601));
    assert(take(scheduler).type == EventType::UNSCHEDULED_OPEN);

    scheduler.update(day, 14 * 60);
    assert(take(scheduler).type == EventType::REMINDER_STARTED);
    assert(scheduler.recordSlotOpen(1, day, 14 * 60 + 30));
    event = take(scheduler);
    assert(event.type == EventType::TAKEN_LATE && event.delayMinutes == 30);

    scheduler.update(day, 20 * 60);
    assert(take(scheduler).type == EventType::REMINDER_STARTED);
    scheduler.update(day, 22 * 60 + 6);
    assert(take(scheduler).type == EventType::MISSED);

    Scheduler rebooted;
    rebooted.restoreLedger(scheduler.ledger());
    rebooted.update(day, 14 * 60 + 31);
    assert(!rebooted.takeEvent(event));
    assert(!rebooted.hasActiveReminder());
    rebooted.update(day+1, 480);
    assert(take(rebooted).type == EventType::REMINDER_STARTED);
    rebooted.update(day+2, 0);
    assert(!rebooted.hasActiveReminder());
    Scheduler overlap;
    assert(overlap.updateSchedule("S2",8,1,true));
    overlap.update(day,480); take(overlap);
    overlap.update(day,481); take(overlap);
    assert(!overlap.recordSlotOpen(1,day,482));
    assert(take(overlap).type == EventType::AMBIGUOUS_OPEN);
    assert(overlap.hasActiveReminder());
    Scheduler expired;
    expired.updateSchedule("S3",9,0,false);
    expired.update(day,480); take(expired);
    expired.update(day,721); assert(take(expired).type == EventType::MISSED);
    assert(!expired.recordSlotOpen(1,day,721));
    assert(take(expired).type == EventType::UNSCHEDULED_OPEN);
    assert(!scheduler.updateSchedule("UNKNOWN", 8, 0, true));
    std::cout << "HOST_SCHEDULER_TESTS_PASS\n";
    return 0;
}
