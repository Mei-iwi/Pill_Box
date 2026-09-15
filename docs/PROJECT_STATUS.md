# Project status

## Integration status

| Capability | Status | Evidence |
|---|---|---|
| Production firmware build | DONE | Feather ESP32-S2 build SUCCESS |
| Simulation firmware build | DONE | Separate `esp32s2_wokwi` build SUCCESS |
| Wokwi project files | DONE | `wokwi.toml`, `diagram.json` |
| Wokwi runtime | NOT_STARTED | CLI and token unavailable |
| Real hardware | NOT_STARTED | No connected hardware evidence |
| Public MQTT broker | DONE | `test.mosquitto.org:1883`, Paho connect rc=0 |
| Broker → Gateway → SQLite → dashboard API | DONE | Real-broker synthetic-device integration PASS |
| Gateway command publish | DONE | API → MQTT QoS 1 → synthetic subscriber PASS |
| ESP32 command response | NOT_STARTED | Firmware builds; ESP32/Wokwi runtime absent |
| Offline firmware queue | PARTIAL | Implementation builds; only synthetic reconnect test executed |
| Duplicate prevention | DONE | Duplicate real-broker event produced one SQLite row |
| Refill workflow | DONE | VERIFIED/CONFIRMED and mismatch audit tests PASS |
| Environment path | PARTIAL | MQTT/DB/dashboard path PASS; DHT source not executed |
| Gateway tests | DONE | 11/11 PASS |
| Native firmware tests | BROKEN | `cc1plus` runtime exits `-1073741511` before compilation |

## Blockers to READY FOR DEMO

1. Run either Wokwi or the real Feather ESP32-S2 and prove heartbeat plus at least one command response.
2. Execute scheduler/button/DHT events from that firmware through MQTT to dashboard.
3. Execute the firmware's own offline queue and reconnect flush.

Wokwi is preferred. It requires a valid `WOKWI_CLI_TOKEN`; simulation artifacts/configuration now exist but no token is stored.

Current conclusion: **NOT READY FOR DEMO**.
