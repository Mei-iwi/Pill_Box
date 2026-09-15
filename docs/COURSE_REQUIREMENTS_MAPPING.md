# Course requirements mapping

| IoT requirement | System component | Evidence source | Demo evidence |
|---|---|---|---|
| Embedded device | ESP32-S2 | `platformio.ini`, `src/` | device build |
| Inputs/sensors | RTC, 3 buttons, DHT22 | `src/drivers/`, `docs/HARDWARE.md` | reminders/environment |
| Outputs/actuators | 3 LEDs, buzzer | `src/drivers/` | on-time/wrong-slot |
| Connectivity | Wi-Fi | `WifiManager` | offline/reconnect |
| IoT protocol | MQTT | `MqttClient`, `mqtt_service.py` | event sync |
| Collection service | Gateway subscriber | `gateway/mqtt_service.py` | event in DB |
| Control service | MQTT command path | `MqttClient`, command API | status/schedule command |
| Keep-alive | heartbeat | `publishHeartbeat` | device status |
| Storage | SQLite | `gateway/schema.py` | history/audit |
| Representation | Flask dashboard | `gateway/templates/` | family/caregiver view |
| Security | validation, secrets, audit | `docs/SECURITY.md` | malformed/refill mismatch |
| Application | Smart Pill Box | whole repository | 8 demo scenarios |
