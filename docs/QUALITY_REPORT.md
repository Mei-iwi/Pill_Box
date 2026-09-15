# Quality report

| Command | Result | Evidence |
|---|---|---|
| `platformio.exe run -e adafruit_feather_esp32s2` | PASS | RAM 58,488/327,680; flash 744,594/1,441,792 |
| `platformio.exe run -e esp32s2_wokwi` | PASS | firmware.bin and firmware.elf generated |
| `python -m unittest discover -s gateway/tests -t . -v` | PASS | 11 tests OK |
| `python -m gateway.tests.mqtt_e2e` | PASS for synthetic-device integration | heartbeat/events/environment/command/refill/duplicate checks true through `test.mosquitto.org:1883` |
| `platformio.exe test -e native` | BLOCKED BY NATIVE TEST TOOLCHAIN | Build stage fails before test execution |
| `cc1plus.exe --version` | FAIL | Process exits `-1073741511`, independent of test source |
| Gateway start against `127.0.0.1:1` | PASS | Async client starts/stops without crashing |
| `python -m json.tool diagram.json` | PASS | Valid JSON syntax |

## Quality gate review

- Production board remains `adafruit_feather_esp32s2`; simulation is separate.
- `Secrets.h`, `.env`, generated DB and `.pio` are ignored.
- No long `delay()` exists in application loop.
- GPIO is centralized and application code is outside generated folders.
- MQTT command API publishes normalized allow-listed JSON and checks that the device exists.
- Gateway schema initializes cleanly and duplicate `(device_id, seq)` is rejected.
- Dashboard reads live APIs; no embedded mock values are used.
- Broker outage does not crash Gateway startup.

## Known limitations

- Wokwi runtime was not executed because `wokwi-cli` and `WOKWI_CLI_TOKEN` are unavailable.
- Real hardware is not tested.
- Synthetic MQTT E2E validates transport/server behavior but does not prove ESP32 peripherals, scheduler, or firmware offline queue execution.
- The public broker is for testing only and can be unavailable or observed by third parties.
