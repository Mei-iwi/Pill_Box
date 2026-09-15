# Hardware and pin map

| Component | Quantity | Pin / interface | Purpose |
|---|---:|---|---|
| Adafruit Feather ESP32-S2 | 1 | board | edge device |
| DS3231/DS1307 RTC | 1 | I2C SDA 3, SCL 4 | real time |
| Push button/reed switch | 3 | GPIO 5, 6, 7 to GND | slot-open input, `INPUT_PULLUP` |
| LED | 3 | GPIO 8, 9, 10 through resistor | slot reminder |
| Active buzzer | 1 | GPIO 11 | non-blocking alert |
| DHT22 | 1 | GPIO 12 | temperature/humidity prototype |

Use a common ground and a resistor for each LED. Verify the exact Feather ESP32-S2 pin labels and voltage levels before wiring. DHT22 is read no more often than every 10 seconds.

No servo, OLED, camera or hazardous chemical is required for the minimum demo. Desiccant is only a packaging-dependent physical option; the sensor threshold is a prototype warning, not a safety claim about medication.
