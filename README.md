# Smart Pill Box — Hộp đựng thuốc thông minh

Prototype IoT học tập cho Adafruit Feather ESP32-S2. Hệ thống nhắc thuốc offline-first, ghi nhận `TAKEN_ON_TIME`, `TAKEN_LATE`, `MISSED`, `WRONG_SLOT`, gửi MQTT khi có mạng và lưu Gateway vào SQLite.

Đây không phải thiết bị y tế: hệ thống không kê đơn, tính liều, đổi lịch, hướng dẫn uống bù hay kết luận thuốc còn an toàn.

## Cấu trúc

- `src/`: firmware Arduino, `main.cpp` chỉ khởi tạo và gọi `app.begin()/app.update()`.
- `include/`: domain, pin map, driver và cấu hình.
- `gateway/`: Flask, paho-mqtt, SQLite, dashboard và integration checks.
- `test/`: host Scheduler harness và PlatformIO Unity suite.
- `wokwi.toml`, `diagram.json`: simulation target riêng; production board không thay đổi.
- `docs/`: kiến trúc, bảo mật, test matrix và demo.

## Build firmware

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e adafruit_feather_esp32s2
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e esp32s2_wokwi
```

Tạo `include/config/Secrets.h` từ `include/config/Secrets.example.h`, điền Wi-Fi và broker; file đã được ignore. Demo hiện dùng broker công khai `test.mosquitto.org:1883`, vì vậy không gửi dữ liệu nhạy cảm.

## Chạy Gateway

```powershell
python -m pip install -r gateway/requirements.txt
$env:MQTT_HOST="test.mosquitto.org"
$env:MQTT_PORT="1883"
$env:PILLBOX_MQTT_AUTOSTART="1"
python -m gateway.app
```

Mở `http://localhost:5000`. Database demo được tạo tại `gateway/data/pillbox.db`.

## Kiểm thử

```powershell
python -m unittest discover -s gateway/tests -t . -v
python -m gateway.tests.mqtt_e2e
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" test -e native
```

## Trạng thái hiện tại

Production và simulation builds PASS; Gateway tests PASS 11/11; real-broker integration PASS với synthetic MQTT device. Wokwi runtime và real hardware chưa chạy. Native toolchain bị crash trong `cc1plus.exe`; xem `docs/PROJECT_STATUS.md` và `docs/QUALITY_REPORT.md`.
