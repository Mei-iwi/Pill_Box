# State machine

```text
IDLE --schedule time--> REMINDING --correct slot/on-time--> IDLE + TAKEN_ON_TIME
                     |              --correct slot/late--> IDLE + TAKEN_LATE
                     |              --wrong slot--------> REMINDING + WRONG_SLOT
                     |              --timeout------------> IDLE + MISSED
```

`REMINDER_STARTED`, `TAKEN_ON_TIME`, `TAKEN_LATE`, `MISSED`, `WRONG_SLOT`, `STORAGE_WARNING`, `DEVICE_ONLINE` and `DEVICE_OFFLINE` are the event vocabulary. A cleared active reminder prevents duplicate take events; button input has 35 ms debounce and edge detection.

Late tracking records the actual delay and never changes the next schedule.
