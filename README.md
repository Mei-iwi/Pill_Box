# Hộp đựng thuốc thông minh — Smart Pill Box

Smart Pill Box là đồ án IoT sử dụng ESP32-S2 để nhắc lịch lấy thuốc, theo dõi thao tác mở ngăn, giám sát nhiệt độ/độ ẩm và đồng bộ dữ liệu đến Gateway qua MQTT. Gateway lưu dữ liệu bằng SQLite và cung cấp Dashboard web cho người dùng, người chăm sóc hoặc điều dưỡng.

Hệ thống được thiết kế theo hướng **offline-first**: chức năng nhắc thuốc trên thiết bị vẫn hoạt động khi mất Wi-Fi/MQTT; sự kiện được đưa vào hàng đợi RAM và gửi lại khi kết nối được khôi phục.

> **Lưu ý an toàn:** Đây là prototype phục vụ học tập, không phải thiết bị y tế. Hệ thống không kê đơn, tính liều, thay đổi liều, hướng dẫn uống bù hoặc kết luận thuốc còn an toàn dựa trên cảm biến.

## Chức năng chính

- Quản lý ba ngăn thuốc và ba lịch nhắc mặc định.
- Nhắc bằng LED và buzzer theo cơ chế không chặn chương trình.
- Nhận biết thao tác mở ngăn qua ba nút nhấn hoặc reed switch.
- Ghi nhận các trạng thái:
  - `REMINDER_STARTED`: bắt đầu nhắc.
  - `TAKEN_ON_TIME`: mở đúng ngăn trong khoảng đúng giờ.
  - `TAKEN_LATE`: mở đúng ngăn nhưng trễ giờ.
  - `MISSED`: không mở đúng ngăn trước khi hết thời gian chờ.
  - `WRONG_SLOT`: mở nhầm ngăn; lời nhắc đúng vẫn tiếp tục.
- Đọc thời gian từ RTC DS3231 trên thiết bị thật hoặc DS1307 trong Wokwi.
- Đọc nhiệt độ và độ ẩm bằng DHT22, phát `STORAGE_WARNING` khi vượt ngưỡng minh họa.
- Kết nối Wi-Fi/MQTT, heartbeat định kỳ và tự động reconnect.
- Lưu cấu hình cơ bản bằng Preferences/NVS.
- Gateway Flask nhận MQTT, kiểm tra payload và lưu SQLite.
- Chống lưu trùng sự kiện bằng khóa `device_id + seq`.
- Dashboard theo dõi thiết bị, lịch sử, môi trường và refill audit.
- Xác minh nạp thuốc đúng hộp/ngăn/mã thuốc trước khi xác nhận.
- Chỉ chấp nhận ba MQTT command: `CLEAR_ALERT`, `REQUEST_STATUS`, `UPDATE_SCHEDULE`.

## Kiến trúc hệ thống

```text
RTC / Buttons / DHT22
          │
          ▼
   ESP32-S2 Firmware
          │ Wi-Fi + MQTT
          ▼
      MQTT Broker
          │
          ▼
 Python Flask Gateway
          │
          ▼
        SQLite
          │
          ▼
     Web Dashboard
```

Luồng command chạy theo chiều ngược lại:

```text
Dashboard/API → Gateway → MQTT command topic → ESP32-S2
```

## Cấu trúc repository

```text
Pill_Box/
├── platformio.ini             Cấu hình PlatformIO
├── src/                       Mã nguồn firmware
│   ├── main.cpp               Entry point tối giản
│   ├── app/                   AppController và Scheduler
│   ├── communication/         Wi-Fi và MQTT
│   ├── drivers/               RTC, button, LED, buzzer, DHT22
│   └── storage/               Preferences/NVS
├── include/                   Header, domain types, pin map và cấu hình
├── gateway/                   Flask, MQTT subscriber, SQLite, Dashboard
│   ├── app.py
│   ├── mqtt_service.py
│   ├── db.py
│   ├── schema.py
│   ├── templates/
│   ├── static/
│   └── tests/
├── test/                      Firmware/domain test source
├── docs/                      Tài liệu kiến trúc, test và demo
├── diagram.json               Sơ đồ mạch Wokwi
└── wokwi.toml                 Cấu hình chạy Wokwi
```

## Yêu cầu môi trường

- Python 3 và `pip`.
- PlatformIO Core hoặc PlatformIO IDE extension cho VS Code.
- MQTT broker. Hướng dẫn này dùng `test.mosquitto.org:1883` để demo.
- Tùy chọn một trong hai:
  - Wokwi CLI/extension và token Wokwi;
  - Adafruit Feather ESP32-S2 cùng RTC, DHT22, ba nút, ba LED và buzzer.

Trên máy Windows của project này, PlatformIO executable nằm tại:

```text
C:\Users\admin\.platformio\penv\Scripts\platformio.exe
```

## Thiết lập key và thông tin bí mật sau khi clone/pull

Repository **không chứa sẵn key hoặc mật khẩu cá nhân**. Sau khi clone project lần đầu, mỗi người dùng phải tự nhập thông tin trên máy của mình. Các file/biến chứa thông tin bí mật không được commit hoặc push lên Git.

| Thông tin | Nơi cấu hình | Có trong Git? | Người dùng cần làm gì? |
|---|---|---|---|
| Wi-Fi SSID/password | `include/config/Secrets.h` | Không | Tạo từ `Secrets.example.h` và tự điền |
| MQTT host/port/account | `include/config/Secrets.h` và biến môi trường Gateway | Không | Dùng broker của người dùng hoặc broker test |
| Wokwi VS Code license | Wokwi extension trong VS Code | Không | Kích hoạt hoặc nhập license thủ công |
| Wokwi CLI token | Biến môi trường `WOKWI_CLI_TOKEN` | Không | Tự tạo token và export trước khi chạy CLI |
| SQLite runtime database | `gateway/data/pillbox.db` | Không | Gateway tự tạo khi khởi động |

### Sau khi clone project lần đầu

Git Bash:

```bash
git clone <DIA_CHI_REPOSITORY>
cd Pill_Box
cp include/config/Secrets.example.h include/config/Secrets.h
```

PowerShell:

```powershell
git clone <DIA_CHI_REPOSITORY>
Set-Location Pill_Box
Copy-Item include/config/Secrets.example.h include/config/Secrets.h
```

Sau đó mở `include/config/Secrets.h` và thay các giá trị mẫu bằng cấu hình cá nhân. Không dùng `git add -f` để ép Git theo dõi file này.

### Sau khi chạy `git pull`

- `Secrets.h` hiện có trên máy sẽ không bị Git ghi đè vì file đã được ignore.
- Wokwi license và CLI token vẫn thuộc cấu hình cá nhân, không được tải về từ repository.
- Nếu `Secrets.example.h` có thêm trường mới, người dùng cần đối chiếu và bổ sung thủ công vào `Secrets.h`.
- Nếu `.pio` đã bị xóa hoặc vừa chạy clean, phải build lại firmware trước khi mở Wokwi.

### Nhập Wokwi VS Code license

License của Wokwi VS Code khác với `WOKWI_CLI_TOKEN`. Để nhập license cho extension:

1. Cài extension **Wokwi Simulator** trong VS Code.
2. Tạo/kích hoạt personal license trên trang Wokwi.
3. Nhấn `F1` hoặc `Ctrl+Shift+P`.
4. Chọn `Wokwi: Manually Enter License Key`.
5. Dán license vào hộp nhập của extension, không dán vào source code hoặc `wokwi.toml`.

Nếu sử dụng Wokwi CLI thay cho extension, tự đặt token trong terminal đang chạy:

Git Bash:

```bash
export WOKWI_CLI_TOKEN="wok_TOKEN_CUA_BAN"
```

PowerShell:

```powershell
$env:WOKWI_CLI_TOKEN="wok_TOKEN_CUA_BAN"
```

Các biến trên chỉ tồn tại trong terminal hiện tại. Đây là cách an toàn hơn so với ghi token trực tiếp vào repository.

## Chạy nhanh Gateway và Dashboard

### Bước 1: Cài thư viện Python

Tại thư mục gốc của project:

```bash
python -m pip install -r gateway/requirements.txt
```

### Bước 2: Khởi động Gateway bằng Git Bash

```bash
export MQTT_HOST="test.mosquitto.org"
export MQTT_PORT="1883"
export PILLBOX_MQTT_AUTOSTART="1"

python -m gateway.app
```

Nếu dùng PowerShell:

```powershell
$env:MQTT_HOST="test.mosquitto.org"
$env:MQTT_PORT="1883"
$env:PILLBOX_MQTT_AUTOSTART="1"

python -m gateway.app
```

Khi terminal hiển thị `Running on http://127.0.0.1:5000`, mở trình duyệt tại:

```text
http://127.0.0.1:5000
```

Database được tạo tự động tại `gateway/data/pillbox.db`. Nếu chưa chạy ESP32 hoặc Wokwi, thiết bị `PB01` sẽ hiển thị `offline` và chưa có dữ liệu cảm biến.

Kiểm tra API bằng terminal khác:

```bash
curl http://127.0.0.1:5000/api/devices
curl http://127.0.0.1:5000/api/devices/PB01/events
curl http://127.0.0.1:5000/api/devices/PB01/environment
```

## Build firmware

### Git Bash

Build cho Adafruit Feather ESP32-S2 thật:

```bash
"/c/Users/admin/.platformio/penv/Scripts/platformio.exe" run -e adafruit_feather_esp32s2
```

Build cho Wokwi bằng simulation environment riêng:

```bash
"/c/Users/admin/.platformio/penv/Scripts/platformio.exe" run -e esp32s2_wokwi
```

### PowerShell

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e adafruit_feather_esp32s2
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e esp32s2_wokwi
```

Kết quả build thành công kết thúc bằng `SUCCESS`. Firmware Wokwi được tạo tại:

```text
.pio/build/esp32s2_wokwi/firmware.bin
.pio/build/esp32s2_wokwi/firmware.elf
```

## Chạy mô phỏng Wokwi

Gateway ở phần trước phải đang chạy và kết nối cùng broker.

Trước khi chạy, người dùng phải tự kích hoạt Wokwi VS Code license hoặc tự đặt `WOKWI_CLI_TOKEN` như phần thiết lập key. Project không và không được phép tự tải key từ Git.

### Dùng Wokwi CLI trong Git Bash

```bash
export WOKWI_CLI_TOKEN="wok_TOKEN_CUA_BAN"
wokwi-cli . --timeout 480000
```

Hoặc mở project bằng VS Code, cài extension Wokwi và chọn:

```text
F1 → Wokwi: Start Simulator
```

Simulation sử dụng ESP32-S2, DS1307, DHT22, ba nút, ba LED và buzzer. RTC bắt đầu tại `07:59:50`, với lịch demo tăng tốc:

| Lịch | Ngăn | Thời gian |
|---|---:|---:|
| S1 | 1 | 08:00 |
| S2 | 2 | 08:02 |
| S3 | 3 | 08:04 |

Nhấn đúng button khi LED ngăn sáng để tạo `TAKEN_ON_TIME`. Nhấn button ngăn khác để tạo `WRONG_SLOT`. Dashboard polling khoảng bốn giây một lần nên dữ liệu không xuất hiện tức thời.

## Chạy trên ESP32-S2 thật

### Bước 1: Tạo file cấu hình riêng

Không sửa `Secrets.example.h` để chứa mật khẩu thật. Hãy tạo `Secrets.h`:

Git Bash:

```bash
cp include/config/Secrets.example.h include/config/Secrets.h
```

PowerShell:

```powershell
Copy-Item include/config/Secrets.example.h include/config/Secrets.h
```

Điền cấu hình trong `include/config/Secrets.h`:

```cpp
#define PILLBOX_WIFI_SSID "TEN_WIFI"
#define PILLBOX_WIFI_PASSWORD "MAT_KHAU_WIFI"
#define PILLBOX_MQTT_HOST "test.mosquitto.org"
#define PILLBOX_MQTT_PORT 1883
#define PILLBOX_MQTT_USER ""
#define PILLBOX_MQTT_PASSWORD ""
```

`Secrets.h` đã được `.gitignore` và không được commit.

### Bước 2: Upload firmware

Git Bash:

```bash
"/c/Users/admin/.platformio/penv/Scripts/platformio.exe" run \
  -e adafruit_feather_esp32s2 \
  -t upload
```

PowerShell:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run `
  -e adafruit_feather_esp32s2 `
  -t upload
```

Mở Serial Monitor:

```bash
"/c/Users/admin/.platformio/penv/Scripts/platformio.exe" device monitor -e adafruit_feather_esp32s2
```

Lịch production mặc định là 08:00, 14:00 và 20:00. RTC DS3231 cần được đặt đúng thời gian trước khi kiểm tra lịch.

Pin map và BOM xem tại [docs/HARDWARE.md](docs/HARDWARE.md).

## Gửi command từ API

Yêu cầu ESP32/Wokwi, Gateway và broker đều đang kết nối.

Yêu cầu thiết bị gửi trạng thái:

```bash
curl -X POST http://127.0.0.1:5000/api/devices/PB01/commands \
  -H "Content-Type: application/json" \
  -d '{"command":"REQUEST_STATUS"}'
```

Tắt LED/buzzer của cảnh báo hiện tại nhưng không thay đổi lịch:

```bash
curl -X POST http://127.0.0.1:5000/api/devices/PB01/commands \
  -H "Content-Type: application/json" \
  -d '{"command":"CLEAR_ALERT"}'
```

Cập nhật một lịch hợp lệ:

```bash
curl -X POST http://127.0.0.1:5000/api/devices/PB01/commands \
  -H "Content-Type: application/json" \
  -d '{"command":"UPDATE_SCHEDULE","slot_id":1,"hour":9,"minute":15,"enabled":true}'
```

## Kiểm thử

Chạy Gateway unit tests:

```bash
python -m unittest discover -s gateway/tests -t . -v
```

Kết quả hiện tại mong đợi:

```text
Ran 11 tests
OK
```

Chạy kiểm tra tích hợp qua broker thật bằng MQTT device tổng hợp:

```bash
python -m gateway.tests.mqtt_e2e
```

Script này dùng database tạm và không đưa dữ liệu vào Dashboard đang chạy. Nó kiểm tra heartbeat, events, environment, command, duplicate prevention và refill workflow trong terminal.

Native PlatformIO tests có thể chạy bằng:

```bash
"/c/Users/admin/.platformio/penv/Scripts/platformio.exe" test -e native -vvv
```

Trên môi trường Windows hiện tại, native toolchain đang bị lỗi `cc1plus.exe`; lỗi này không ảnh hưởng đến production firmware build.

## Refill verification

Dữ liệu demo mặc định:

| Box | Patient | Slot | Medication code |
|---|---|---:|---|
| PB01 | P001 | 1 | MED001 |
| PB01 | P001 | 2 | MED002 |
| PB01 | P001 | 3 | MED003 |

Ví dụ đúng: slot 1 với `MED001` trả về `VERIFIED` và mới được phép confirm. Slot 1 với `MED002` trả về `MEDICATION_MISMATCH`, bị chặn confirm và vẫn được ghi audit.

Tất cả patient/medication trong project đều là dữ liệu giả lập.

## Bảo mật và quyền riêng tư

- Không commit `Secrets.h`, `.env` hoặc SQLite database.
- Gateway kiểm tra topic, `device_id`, event type, slot và sequence.
- Command ngoài whitelist bị từ chối.
- Không ghi credential vào log.
- Broker `test.mosquitto.org:1883` là broker công khai, không dùng cho dữ liệu thật.
- Đây không phải kiến trúc bảo mật cho thiết bị y tế production.

## Trạng thái hiện tại

- Production Feather ESP32-S2 build: **PASS**.
- Simulation ESP32-S2 build: **PASS**.
- Gateway tests: **PASS 11/11**.
- MQTT broker/Gateway/SQLite integration bằng synthetic device: **PASS**.
- Wokwi runtime: **CHƯA CHẠY**, cần Wokwi CLI/extension và token.
- Phần cứng thật: **CHƯA KIỂM TRA**.
- Native firmware tests: **BLOCKED BY NATIVE TEST TOOLCHAIN**.

Do chưa có bằng chứng runtime từ Wokwi hoặc ESP32 thật, trạng thái tổng thể hiện vẫn là **NOT READY FOR DEMO**.

## Tài liệu liên quan

- [Kiến trúc hệ thống](docs/ARCHITECTURE.md)
- [Phần cứng và pin map](docs/HARDWARE.md)
- [State machine](docs/STATE_MACHINE.md)
- [MQTT contract](docs/MQTT.md)
- [Luật adherence](docs/ADHERENCE_RULES.md)
- [Persistence](docs/PERSISTENCE.md)
- [Bảo mật](docs/SECURITY.md)
- [Kịch bản demo](docs/DEMO_SCRIPT.md)
- [Test matrix](docs/TEST_MATRIX.md)
- [Quality report](docs/QUALITY_REPORT.md)
- [Project status](docs/PROJECT_STATUS.md)
- [Final checklist](docs/FINAL_CHECKLIST.md)
