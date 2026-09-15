#include <unity.h>
#include "../../src/app/Scheduler.cpp"

void test_before_time_is_idle() {
    Scheduler scheduler; scheduler.update(7 * 60 + 59); SchedulerEvent event;
    TEST_ASSERT_FALSE(scheduler.takeEvent(event));
}
void test_reminder_and_on_time() {
    Scheduler scheduler; scheduler.update(8 * 60); SchedulerEvent event;
    TEST_ASSERT_TRUE(scheduler.takeEvent(event)); TEST_ASSERT_EQUAL(EventType::REMINDER_STARTED, event.type);
    TEST_ASSERT_TRUE(scheduler.recordSlotOpen(1, 8 * 60 + 3)); TEST_ASSERT_TRUE(scheduler.takeEvent(event));
    TEST_ASSERT_EQUAL(EventType::TAKEN_ON_TIME, event.type);
}
void test_late_does_not_change_next_schedule() {
    Scheduler scheduler; scheduler.update(8 * 60); SchedulerEvent event; scheduler.takeEvent(event);
    TEST_ASSERT_TRUE(scheduler.recordSlotOpen(1, 8 * 60 + 30)); TEST_ASSERT_TRUE(scheduler.takeEvent(event));
    TEST_ASSERT_EQUAL(EventType::TAKEN_LATE, event.type); scheduler.update(14 * 60);
    TEST_ASSERT_TRUE(scheduler.takeEvent(event)); TEST_ASSERT_EQUAL(2, event.slotId);
}
void test_missed_and_wrong_slot() {
    Scheduler scheduler; scheduler.update(8 * 60); SchedulerEvent event; scheduler.takeEvent(event);
    TEST_ASSERT_FALSE(scheduler.recordSlotOpen(2, 8 * 60 + 1)); TEST_ASSERT_TRUE(scheduler.takeEvent(event));
    TEST_ASSERT_EQUAL(EventType::WRONG_SLOT, event.type); scheduler.update(10 * 60 + 1);
    TEST_ASSERT_TRUE(scheduler.takeEvent(event)); TEST_ASSERT_EQUAL(EventType::MISSED, event.type);
}

void setup() {
    UNITY_BEGIN();
    RUN_TEST(test_before_time_is_idle); RUN_TEST(test_reminder_and_on_time);
    RUN_TEST(test_late_does_not_change_next_schedule); RUN_TEST(test_missed_and_wrong_slot);
    UNITY_END();
}
void loop() {}
