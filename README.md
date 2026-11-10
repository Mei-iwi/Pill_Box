# Hộp đựng thuốc thông minh — Smart Pill Box

Giao diện hiện dùng ảnh chụp lưu tại `gateway/static/images`, chữ đen, nút blue và menu cố định. Các danh sách lịch sử/kết quả/nạp thuốc/lệnh hỗ trợ `?page=1&page_size=8`; gọi API không có tham số vẫn trả mảng để giữ tương thích.

Dữ liệu khởi tạo dùng hồ sơ ẩn danh và danh mục Vitamin C, Vitamin D3, Canxi, Vitamin B12. Đây là dữ liệu cấu hình tham khảo, không phải hồ sơ người bệnh hay đơn thuốc thật. Lịch sử và số đo chỉ được ghi khi có thao tác/bản tin thiết bị.

Muốn tạo lại dữ liệu, dừng Gateway rồi chạy `python -m gateway.reset_data --db gateway/data/pillbox.db`. Lệnh sao lưu đầy đủ vào `gateway/data/backups/<thời điểm>/` trước khi xóa. Có thể khôi phục bằng file `.db` đã sao lưu khi Gateway đã dừng. Không đưa backup vào Git.

Kiểm thử phân trang/reset/phân quyền: `python -m unittest discover -s gateway/tests -t .` (33 test). Kiểm tra giao diện: `node test/ui_dashboard.mjs` khi Edge/Chromium có CDP port 9334 và profile riêng; các POST refill và GET phân trang thử được chặn riêng trong trang kiểm thử, không ghi dữ liệu giả vào DB chạy thật.

Đồ án IoT sử dụng ESP32-S2, RTC, ba nút/công tắc ngăn, LED/buzzer và DHT22 để nhắc lịch, ghi nhận thao tác lấy thuốc, theo dõi môi trường và gửi dữ liệu qua MQTT tới Flask Gateway → SQLite → Dashboard tiếng Việt.

Đây là prototype học tập. Mở ngăn/xác nhận lấy không chứng minh thuốc đã được uống. Hệ thống không kê đơn, chỉnh liều, hướng dẫn uống bù hoặc tự thay lịch sau một lần lấy trễ. Dữ liệu PB01/PB02, P001/P002 và MED001–MED004 đều là mã giả.

## Những gì đã triển khai

- Ba ngăn vật lý; bốn lịch trên PB01, gồm hai lịch cho cùng MED001/ngăn1.
- Occurrence riêng cho từng lịch/ngày; quá hạn vẫn tiếp tục theo dõi lấy trễ.
- 08:00 nhắc S1 → 08:15 MISSED → 10:00 xác nhận lấy muộn 120 phút; 14:00 S2 giữ nguyên.
- Mở sai ngăn không hoàn tất lịch; overlap cùng ngăn tạo AMBIGUOUS_OPEN.
- Ledger và cấu hình lịch có version trong NVS, hạn chế completion trùng sau reboot.
- MQTT worker riêng để reconnect/socket không chạy trên task scheduler; FIFO RAM 16 sự kiện chờ, thêm một bản đang gửi. Tràn bỏ oldest queued, có bộ đếm.
- Payload v2 có event_id, boot_id, occurrence_id và thời điểm phát sinh; Gateway chống trùng, vẫn nhận payload v1.
- Refill Verify → Confirm với token 5 phút dùng một lần; kiểm tra patient/box/slot/medication, actor, expiry và assignment version; ghi audit.
- DHT: lỗi sensor/NaN, 3 mẫu xác nhận vượt ngưỡng hoặc hồi phục, hysteresis 2 đơn vị.
- Dashboard theo hộp, ba ngăn, lịch, kết quả occurrence, sự kiện, môi trường và refill.
- Xác thực bearer tùy chọn với family/nurse/admin và phạm vi hộp, enforce phía API.

Build, unit/native/host và synthetic MQTT đã chạy được. Wokwi runtime và board thật chưa có bằng chứng; kết luận hiện tại: **NOT READY FOR DEMO**. Xem [báo cáo](docs/QUALITY_REPORT.md) và [ma trận kiểm thử](docs/TEST_MATRIX.md).

## Cấu trúc chính

| Thư mục/file | Nội dung |
|---|---|
| platformio.ini | Production Feather ESP32-S2; simulation riêng; native tests |
| src/app, include/app | AppController, Scheduler |
| include/domain | Model sự kiện, FIFO, logic cảnh báo môi trường |
| src/drivers, include/drivers | RTC, nút, LED, buzzer, DHT; interface HX711 chưa triển khai |
| src/communication | Wi-Fi, MQTT worker, command |
| src/storage | Preferences/NVS |
| gateway | Flask API, MQTT receiver, SQLite migration/seed, Dashboard |
| test, gateway/tests | Native/host và Gateway/broker tests |
| diagram.json, wokwi.toml | Mạch và đường dẫn artifact Wokwi |
| docs | Kiến trúc, phần cứng, luật xử lý, bảo mật, demo, bằng chứng |

## Chuẩn bị sau khi clone/pull

Cài Python 3, PlatformIO IDE/Core và VS Code. Muốn chạy simulation thì cài Wokwi Simulator extension và tự kích hoạt license. Mỗi người tự điền key/cấu hình cá nhân sau khi pull; repository không chứa license, token hoặc mật khẩu dùng chung.

Từ thư mục gốc repository:

```bash
python -m pip install -r gateway/requirements.txt
```

Secrets của board thật: sao chép include/config/Secrets.example.h thành include/config/Secrets.h rồi tự điền Wi-Fi/MQTT. Secrets.h đã được ignore; không dùng git add -f để đưa vào Git. Simulation dùng Wokwi-GUEST và test.mosquitto.org:1883 với credential trống, không cần Secrets.h.

Wokwi VS Code license khác WOKWI_CLI_TOKEN:

1. Cài extension Wokwi Simulator và kích hoạt personal license.
2. Nếu chưa được nhận tự động: F1 → Wokwi: Manually Enter License Key → tự dán key.
3. Không dán license vào README, source, diagram.json hoặc wokwi.toml.
4. CLI token chỉ cần khi dùng CLI; tự tạo và đặt trong biến môi trường. Extension không yêu cầu CLI token.

Sau pull/clean, build lại firmware nếu .pio/build chưa có. .env chỉ là file mẫu; chương trình không tự load .env.

## Chạy Gateway và xem kết quả

Mở terminal tại thư mục gốc. Chọn đúng cú pháp của shell, không gõ ký hiệu dấu nhắc $ vào lệnh.

Git Bash:

```bash
export PILLBOX_DB="gateway/data/care_demo.db"
export MQTT_HOST="test.mosquitto.org"
export MQTT_PORT="1883"
export PILLBOX_MQTT_AUTOSTART="1"
python -m gateway.app
```

PowerShell:

```powershell
$env:PILLBOX_DB="gateway/data/care_demo.db"
$env:MQTT_HOST="test.mosquitto.org"
$env:MQTT_PORT="1883"
$env:PILLBOX_MQTT_AUTOSTART="1"
python -m gateway.app
```

Giữ terminal này đang chạy. Mở **http://127.0.0.1:5000** trong trình duyệt. Gateway mặc định chỉ lắng nghe localhost; chưa có firmware kết nối thì hiện offline/chưa có mẫu cảm biến.

Dùng care_demo.db để nhận seed mới; database cũ vẫn giữ lịch/cấu hình của người dùng. Nếu bỏ PILLBOX_DB, mặc định là gateway/data/pillbox.db. Migration giữ dữ liệu cũ, không tự sửa lịch đã có sang mẫu mới.

| Hộp / người dùng | Ngăn | Mã demo | Lịch |
|---|---:|---|---|
| PB01 / P001 | 1 | MED001 | S1 08:00, S2 14:00 |
| PB01 / P001 | 2 | MED002 | S3 09:00 |
| PB01 / P001 | 3 | MED003 | S4 20:00 |
| PB02 / P002 | 1 | MED004 | S5 07:30 |

PB02 là seed phía Gateway; firmware/mạch hiện tại chỉ đại diện PB01.

API xem dữ liệu:

```bash
curl http://127.0.0.1:5000/api/devices
curl http://127.0.0.1:5000/api/devices/PB01/events
curl http://127.0.0.1:5000/api/devices/PB01/occurrences
curl http://127.0.0.1:5000/api/devices/PB01/environment
curl http://127.0.0.1:5000/api/devices/PB01/commands
```

Trong PowerShell dùng curl.exe thay curl nếu curl là alias.

## Build firmware và chạy Wokwi

Nếu PlatformIO có trong PATH:

```bash
pio run -e adafruit_feather_esp32s2
pio run -e esp32s2_wokwi
```

Nếu chưa có trong PATH, Git Bash dùng:

```bash
"$HOME/.platformio/penv/Scripts/platformio.exe" run -e esp32s2_wokwi
```

PowerShell dùng:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e esp32s2_wokwi
```

Cú pháp & "$env:..." thuộc PowerShell, dùng trong Git Bash sẽ gây lỗi syntax near '&'.

Build kết thúc SUCCESS sẽ tạo:

```text
.pio/build/esp32s2_wokwi/firmware.bin
.pio/build/esp32s2_wokwi/firmware.elf
```

wokwi.toml đã trỏ đúng hai file trên. Nếu gặp “firmware binary not found”, mở đúng workspace gốc chứa platformio.ini và chạy build env esp32s2_wokwi trước khi Start Simulator; không trỏ tới file firmware chưa được tạo.

Trong VS Code: F1 → Wokwi: Start Simulator. [Tài liệu Wokwi](https://docs.wokwi.com/vscode/platformio) liệt kê esp32-s2-saola-1 tương ứng board-esp32-s2-devkitm-1; production vẫn giữ board Feather.

RTC simulation bắt đầu 07:59:50 ngày 10/11/2026. Cửa sổ và lịch giống production; không rút ngắn âm thầm. Chờ tới 08:00 sẽ nhắc ngăn1. Dùng Serial Monitor gửi từng dòng có newline để nhảy giờ:

```text
TIME 08:15
TIME 10:00
TIME 14:00
```

Kịch bản lấy muộn:

1. 08:00: nhấn ngăn2 để thử WRONG_SLOT; ngăn1 vẫn nhắc.
2. TIME 08:15: S1 có MISSED, occurrence vẫn theo dõi.
3. TIME 10:00 rồi nhấn ngăn1: S1 thành LATE, trễ120 phút. Do S3 có lịch09:00, khi nhảy tới10:00 có thể có LED2/overdue S3 độc lập; xử lý ngăn2 riêng.
4. TIME 14:00: S2 vẫn nhắc ngăn1; nhấn đúng để có ON_TIME.
5. Dashboard: xem occurrence S1=LATE; lịch sử vẫn giữ MISSED. Polling mỗi4 giây.

TIME chỉ hoạt động trong simulation, không chỉnh RTC board thật. Để thử lại một occurrence đã hoàn tất cùng ngày, dùng phiên simulation sạch hoặc ngày RTC mới; không xóa NVS/database người dùng.

DHT mặc định31.5°C/72%. Ngưỡng demo30°C/70%, publish mỗi60 giây, cần3 mẫu liên tiếp để cảnh báo. Đưa xuống <28°C và <68% đủ3 mẫu để kết thúc cảnh báo. Nhãn/bao bì và hướng dẫn dược sĩ mới là cơ sở bảo quản; không suy ra chất lượng thuốc từ DHT.

Agent chưa điều khiển GUI Wokwi hoặc quan sát GPIO. Các bước trên là checklist cần thực thi; [demo script](docs/DEMO_SCRIPT.md) ghi rõ cách thu bằng chứng.

## Xác minh nạp thuốc hai bước

Chọn hộp, nhập patient_id, ngăn và mã trên bao bì ở Dashboard:

- PB01/P001/ngăn1/MED001 → VERIFIED; sau đó nhấn Xác nhận nạp.
- MED002 ở ngăn1 PB01 → MEDICATION_MISMATCH.
- PB02 nhưng patient P001 → PATIENT_BOX_MISMATCH.
- Token hết hạn5 phút, dùng lại, đổi actor hoặc đổi assignment → bị chặn.
- Đổi form/hộp sau Verify sẽ khóa Confirm; xác minh lại trước khi nạp.

API Verify nhận box_id, patient_id, slot_id, medication_code và actor_id trong demo chưa auth. Trả verification_id/expires_at. Confirm nhận verification_id và actor_id khi chưa auth; actor được máy chủ quyết định nếu bật auth. Audit ghi cả thành công và sai lệch.

Quy trình xác minh mã bao bì không chứng minh viên thực tế trong ngăn là đúng.

## Bật xác thực API và phân quyền

Mặc định là demo cục bộ chưa auth. Muốn dùng quyền family/nurse/admin:

```powershell
Copy-Item gateway/auth.example.json gateway/auth.local.json
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Tự tạo một token khác nhau cho từng tài khoản và thay TOÀN BỘ tên key REPLACE_WITH... trong auth.local.json. Máy chủ từ chối mẫu placeholder. Chỉnh devices theo phạm vi phân công; không commit file này.

PowerShell:

```powershell
$env:PILLBOX_AUTH_FILE="gateway/auth.local.json"
python -m gateway.app
```

Git Bash:

```bash
export PILLBOX_AUTH_FILE="gateway/auth.local.json"
python -m gateway.app
```

Nhập token cá nhân vào ô Khóa truy cập API trên Dashboard rồi Kết nối. Family chỉ hộp được gán; nurse được refill/audit trong phạm vi; admin được cập nhật lịch. Actor từ phiên xác thực, không tin actor_id tự gửi. Khi gọi API bằng curl, thêm header Authorization: Bearer TOKEN_CUA_BAN.

Đây là bearer auth đơn giản, chưa có JWT/password login, HTTPS hoặc broker ACL/TLS. Không mở chế độ demo chưa auth ra Internet. Chi tiết [SECURITY.md](docs/SECURITY.md).

## Command từ API

Ví dụ Git Bash (PowerShell có thể dùng Invoke-RestMethod):

```bash
curl -X POST http://127.0.0.1:5000/api/devices/PB01/commands \
  -H "Content-Type: application/json" \
  -d '{"command":"REQUEST_STATUS"}'
```

Hai command còn lại: {"command":"CLEAR_ALERT"} và {"command":"UPDATE_SCHEDULE","schedule_id":"S2","hour":14,"minute":0,"enabled":true}. Không dùng slot_id để chọn lịch, vì một ngăn có nhiều lịch.

HTTP202 nghĩa đã gửi yêu cầu tới broker, chưa phải đã áp dụng. Xem /api/devices/PB01/commands để chờ APPLIED/REJECTED; DB chỉ đổi lịch khi nhận ACK khớp và firmware đã lưu NVS. Broker không khả dụng trả503. CLEAR_ALERT chỉ tắt âm/đèn; không hoàn tất lịch.

## Chạy trên board thật

Tạo Secrets.h từ mẫu và tự điền thông tin mạng. Kiểm tra đấu nối theo [HARDWARE.md](docs/HARDWARE.md), đặt RTC DS3231 đúng giờ Việt Nam; RTC mất nguồn/chưa hợp lệ sẽ dùng fallback unsynchronized.

```bash
pio run -e adafruit_feather_esp32s2 -t upload
pio device monitor -e adafruit_feather_esp32s2
```

Board thật không có Serial TIME. Chưa có kiểm thử phần cứng, HX711 concrete driver, đo pin hoặc Deep Sleep. Interface LoadcellDriver hiện chỉ là hợp đồng để bổ sung sau.

## Kiểm thử và mức bằng chứng

```bash
python -m unittest discover -s gateway/tests -t . -v
pio test -e native
python -m gateway.tests.mqtt_e2e
node --check gateway/static/dashboard.js
```

Trên máy Windows dùng MSYS2 UCRT64, thêm thư mục DLL vào PATH trước native/host test.

PowerShell:

```powershell
$env:PATH="C:\msys64\ucrt64\bin;" + $env:PATH
g++ -std=c++11 -Iinclude test/host_scheduler/main.cpp src/app/Scheduler.cpp -o .pio/host_scheduler.exe
& .\.pio\host_scheduler.exe
```

Git Bash:

```bash
export PATH="/c/msys64/ucrt64/bin:$PATH"
g++ -std=c++11 -Iinclude test/host_scheduler/main.cpp src/app/Scheduler.cpp -o .pio/host_scheduler.exe
./.pio/host_scheduler.exe
```

Host test bao gồm ledger/reboot, midnight, overlap, late expiry, FIFO overflow và môi trường. Native Unity có4 test. Broker test dùng mã PBTEST ngẫu nhiên và database tạm, không đổ dữ liệu vào Dashboard đang chạy. Nó kiểm tra MQTT v2, occurrence, ba command/ACK, sensor error, refill và synthetic reconnect.

Các lệnh đã chạy ngày10/11/2026: Gateway28/28 PASS; native4/4 PASS; host PASS; hai build PASS; broker synthetic PASS. Đây không phải kết quả Wokwi/hardware. Xem [TEST_MATRIX.md](docs/TEST_MATRIX.md) và [QUALITY_REPORT.md](docs/QUALITY_REPORT.md) để biết giới hạn.

## Giới hạn và tài liệu

Queue RAM không sống qua reset; publish thành công chưa chứng minh SQLite commit. Chưa có ACK ứng dụng cho event. Theo dõi trễ dừng ở ngày địa phương mới, chưa hỗ trợ cửa sổ xuyên nửa đêm. Ledger NVS không phải durable event outbox. Board PB01 có4 lịch cố định; PB02 hiện chỉ là seed phía server.

Public broker1883 không mã hóa/xác thực, chỉ dùng dữ liệu giả. Key Wokwi/Wi-Fi/API mỗi người tự nhập sau pull, không đưa vào Git.

- [Kiến trúc](docs/ARCHITECTURE.md), [state machine](docs/STATE_MACHINE.md), [quy tắc lấy thuốc](docs/ADHERENCE_RULES.md)
- [MQTT](docs/MQTT.md), [lưu trữ/migration](docs/PERSISTENCE.md), [bảo mật](docs/SECURITY.md)
- [Phần cứng](docs/HARDWARE.md), [demo và checklist runtime](docs/DEMO_SCRIPT.md)
- [Ma trận test](docs/TEST_MATRIX.md), [báo cáo chất lượng](docs/QUALITY_REPORT.md), [trạng thái](docs/PROJECT_STATUS.md)
- [Ánh xạ đề cương](docs/COURSE_REQUIREMENTS_MAPPING.md), [checklist cuối](docs/FINAL_CHECKLIST.md)
