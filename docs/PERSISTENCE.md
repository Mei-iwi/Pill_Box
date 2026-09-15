# Persistence

Firmware uses ESP32 `Preferences`/NVS namespace `pillbox` for config version and demo temperature/humidity thresholds. Missing or unreadable keys fall back to defaults; boot does not crash.

Gateway uses SQLite tables for devices, demo patients, schedules, medication catalog, slot assignments, medication events, environment readings and refill audit logs. The seed data uses synthetic `P001` and `MED001`–`MED003`; no real patient data is expected.
