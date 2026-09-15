# Demo script — 5–7 minutes

## Preparation

Build firmware, start Gateway with `MQTT_HOST=test.mosquitto.org`, open `http://localhost:5000`, and start Wokwi or connect the real Feather. Use only synthetic patient data. The Wokwi RTC starts at 07:59:50 and simulation schedules run at 08:00, 08:02 and 08:04 with shortened demo windows; production schedules remain 08:00, 14:00 and 20:00.

1. **Architecture — 30 seconds:** explain ESP32-S2 → MQTT → Gateway → SQLite → Flask dashboard.
2. **Heartbeat — 45 seconds:** show `PB01` online and `last_seen` updating.
3. **On-time reminder — 45 seconds:** trigger slot 1, show LED/buzzer, press slot 1, then show `TAKEN_ON_TIME`.
4. **Wrong slot — 45 seconds:** trigger slot 2, press slot 1, show `WRONG_SLOT` while slot 2 remains active.
5. **Late/missed — 45 seconds:** use demo/test clock to show `TAKEN_LATE` with delay and `MISSED`; confirm the next schedule is unchanged.
6. **Refill verification — 60 seconds:** verify PB01/slot 1/MED001 and confirm; then submit MED002 and show mismatch plus audit row.
7. **Environment — 45 seconds:** raise virtual DHT values beyond the demo threshold; show reading and `STORAGE_WARNING`. State that thresholds are illustrative only.
8. **Offline-first — 60 seconds:** disconnect Wi-Fi/MQTT, trigger and acknowledge locally, reconnect, show queued event inserted once.
9. **Command — 30 seconds:** press “Request status”, show MQTT command and refreshed device status.

## Backup plan

Before presentation, record screenshots/video of Wokwi LEDs/buttons/DHT, Gateway console, dashboard and SQLite event/audit rows. Keep the real-broker integration output available. If public Internet fails, use the recording plus database evidence; do not fabricate a live PASS.
