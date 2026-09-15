# Architecture

```text
RTC / buttons / DHT22 -> ESP32-S2 firmware -> Wi-Fi -> MQTT broker
                                      -> Python Gateway -> SQLite -> Flask dashboard
Dashboard/API -> Gateway -> MQTT command topic -> ESP32-S2
```

Firmware layers: `AppController` coordinates `Scheduler`, `Drivers`, `SettingsStore`, `WifiManager` and `MqttClient`. Domain scheduling does not include GPIO or MQTT. `main.cpp` contains only app construction, `setup()` and `loop()`.

The device keeps reminders local when disconnected. Events are buffered in a 16-item RAM queue and flushed after MQTT reconnect. The Gateway uses `device_id + seq` as the idempotency key.
