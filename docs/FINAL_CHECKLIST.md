# Final checklist

- [x] Production Feather ESP32-S2 build PASS.
- [x] Separate ESP32-S2 Wokwi build PASS.
- [x] Gateway tests PASS 11/11.
- [x] Public MQTT broker connection PASS.
- [x] Synthetic MQTT device → broker → Gateway → DB → dashboard API PASS.
- [x] Gateway command publish over real broker PASS.
- [x] Duplicate prevention PASS.
- [x] Refill verified/confirm and mismatch audit PASS.
- [x] Dashboard uses live APIs for status, events, environment, commands and refill.
- [x] Gateway survives broker unavailable at startup.
- [ ] Wokwi or real ESP32 heartbeat observed by Gateway.
- [ ] Firmware-generated on-time/late/missed/wrong-slot events observed end-to-end.
- [ ] Firmware DHT reading observed end-to-end.
- [ ] Firmware offline queue/reconnect flush observed end-to-end.
- [ ] ESP32/Wokwi command response observed.
- [ ] Native tests PASS; currently BLOCKED BY NATIVE TEST TOOLCHAIN.

**REAL HARDWARE: NOT TESTED**

**Simulation end-to-end: NOT TESTED** — simulation build passes, but Wokwi CLI/token is unavailable.

Current conclusion: **NOT READY FOR DEMO**.
