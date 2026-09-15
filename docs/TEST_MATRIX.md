# Test matrix

Actual results were recorded from commands executed on 2026-09-15. `PASS` is used only when the stated expected path was exercised.

| ID | Layer | Precondition | Action | Expected | Actual | PASS/FAIL | Evidence |
|---|---|---|---|---|---|---|---|
| TC01 | Firmware | PlatformIO installed | Build production env | Feather ESP32-S2 firmware builds | SUCCESS; RAM 17.8%, flash 51.6% | PASS | `pio run -e adafruit_feather_esp32s2` |
| TC02 | E2E heartbeat | ESP32/Wokwi connected | Publish heartbeat | Firmware → broker → DB → dashboard online | Synthetic MQTT client completed path; ESP32/Wokwi not run | FAIL | `python -m gateway.tests.mqtt_e2e` |
| TC03 | E2E reminder | Firmware schedule due | Trigger reminder | Firmware event reaches dashboard | Broker/Gateway/DB path passed with synthetic event only | FAIL | integration command output |
| TC04 | E2E on-time | Active slot 1 reminder | Open slot 1 | `TAKEN_ON_TIME` end-to-end | Synthetic event stored/displayed; no virtual/real button run | FAIL | integration command output |
| TC05 | E2E late | Active reminder | Open correct slot late | Delay stored; next schedule unchanged | Synthetic `TAKEN_LATE` stored; firmware source not executed | FAIL | integration command output |
| TC06 | E2E missed | Active reminder | Let window expire | `MISSED` end-to-end | Synthetic `MISSED` stored; firmware clock not executed | FAIL | integration command output |
| TC07 | E2E wrong slot | Slot 2 reminder | Open slot 1 | `WRONG_SLOT`; reminder continues | Synthetic event stored; button/reminder continuation not run | FAIL | integration command output |
| TC08 | Environment | DHT available | Publish reading/warning | DB and dashboard update | Synthetic 31.5°C/72% plus warning reached DB/dashboard API | FAIL | Device source was synthetic, not DHT/Wokwi |
| TC09 | Offline queue | Firmware connected | Disconnect and trigger event | Local queue retains event | Python device harness queued one event; firmware queue not executed | FAIL | `mqtt_e2e.py` |
| TC10 | Reconnect sync | Queued event exists | Reconnect | Exactly one DB row | Synthetic client reconnect produced exactly one row | FAIL | Firmware queue not executed |
| TC11 | Duplicate prevention | Same PB01 sequence | Publish twice via real broker | One DB row | Exactly one row persisted | PASS | `mqtt_e2e.py`, SQLite UNIQUE |
| TC12 | Refill verified | PB01 slot 1 expects MED001 | Verify and confirm | VERIFIED then CONFIRMED; audit row | Both API operations and audit succeeded | PASS | Unit + integration checks |
| TC13 | Medication mismatch | PB01 slot 1 expects MED001 | Submit MED002 | Mismatch; confirmation blocked | `MEDICATION_MISMATCH`; mismatch audited | PASS | Unit + integration checks |
| TC14 | Command publish | Gateway and broker connected | POST REQUEST_STATUS | Publish correct topic/payload | Real broker delivered command and synthetic device returned status | PASS | `mqtt_e2e.py` |
| TC15 | Invalid command | Gateway available | POST arbitrary command | HTTP 400; no MQTT publish | HTTP 400; fake MQTT had zero calls | PASS | Gateway unit test |
| TC16 | Gateway tests | Python dependencies installed | Run unittest discovery | All tests pass | 11 tests OK | PASS | unittest output |
| TC17 | Simulation build | ESP32-S2 Wokwi env | Build firmware | Firmware artifacts generated | Build SUCCESS | PASS | `pio run -e esp32s2_wokwi` |
| TC18 | Wokwi runtime | CLI token and simulator | Start simulation | ESP32-S2 firmware runs peripherals/MQTT | CLI/token unavailable; not executed | FAIL | Environment audit |
| TC19 | Native domain tests | Working host compiler | Run Unity/host harness | Scheduler transitions pass | `cc1plus.exe` crashes with exit `-1073741511` before compiling | FAIL | Direct compiler probe |
