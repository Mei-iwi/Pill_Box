# Hộp đựng thuốc thông minh

Hệ thống dùng ESP32-S2 để nhắc lịch lấy thuốc, ghi nhận mở ba ngăn và theo dõi nhiệt độ/độ ẩm. Gateway Python nhận MQTT, lưu SQLite và cung cấp Dashboard tiếng Việt. Người chăm sóc xác minh mã thuốc, mở phiên nạp giới hạn thời gian rồi xác nhận sau khi mở đúng ngăn.

Mở ngăn chỉ xác nhận thao tác lấy thuốc. Cấu hình và dữ liệu kiểm thử dùng hồ sơ ẩn danh, không phải đơn thuốc hoặc lịch sử chăm sóc thật.

## 1. Chọn cách chạy

| Chế độ | Mục đích | Kết nối |
|---|---|---|
| Local, 6 hộp phần mềm | Test web, tài khoản, phân quyền, cảnh báo và nạp thuốc | Không cần Wokwi/broker |
| Wokwi + Gateway | Test firmware, nút bấm, LED/buzzer, DHT22 và MQTT | PB01 trên Wokwi |
| Triển khai bảo mật | MQTT TLS, ACL từng hộp, HTTPS và phân quyền | Xem [deploy/README.md](deploy/README.md) |

Hộp local trực tuyến nhờ tiến trình mô phỏng gửi heartbeat mỗi 5 giây. Đây là **mô phỏng phần mềm**, không phải sáu board thật. Dừng tiến trình sẽ báo ngoại tuyến; heartbeat quá 65 giây cũng bị coi là mất kết nối.

## 2. Clone và cài đặt

Cần Git, Python 3.11–3.13 và trình duyệt. Firmware cần VS Code, PlatformIO IDE và Wokwi Simulator.

```bash
git clone --branch feat/local-fleet-accounts --single-branch https://github.com/Mei-iwi/Pill_Box.git
cd Pill_Box
code .
```

Đã clone: lưu thay đổi cá nhân trước khi `git fetch origin`, `git switch feat/local-fleet-accounts`, `git pull --ff-only`.

Mọi lệnh chạy từ thư mục chứa `platformio.ini` và `gateway/`.

**Git Bash trên Windows:**

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r gateway/requirements.txt
```

**PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r gateway/requirements.txt
```

Linux/macOS: tạo bằng `python3 -m venv .venv`, dùng `./.venv/bin/python` trong các lệnh. Không cần Node.js hoặc SQLite server để chạy web.

Git Bash dùng `cd /d/StudyMaterials/...`; PowerShell dùng `cd D:\StudyMaterials\...`. Không nhập cú pháp `$env:...` hoặc `&` của PowerShell vào Git Bash.

## 3. Khởi tạo dữ liệu và tài khoản

**Dừng Gateway cũ bằng Ctrl+C trước khi reset.** Reset sao lưu DB vào `gateway/data/backups/`, xóa dữ liệu đang dùng rồi tạo cấu hình mới. Chỉ reset khi cần làm lại dữ liệu, không chạy mỗi lần khởi động.

Git Bash:

```bash
./.venv/Scripts/python.exe -m gateway.reset_data --db gateway/data/pillbox.db --realistic
./.venv/Scripts/python.exe -m gateway.accounts create
./.venv/Scripts/python.exe -m gateway.accounts show
```

PowerShell: thay `./.venv/Scripts/python.exe` bằng `.\.venv\Scripts\python.exe`.

Dữ liệu mới có **6 hộp, 6 hồ sơ ẩn danh theo khu/phòng, 18 ngăn, 24 lịch nhắc**. Không điền sẵn số đo, kết quả lấy thuốc hoặc trạng thái online; chúng xuất hiện khi mô phỏng/thiết bị gửi dữ liệu.

| Hộp | Hồ sơ | Khu/phòng | Nhóm chăm sóc |
|---|---|---|---|
| PB01 | P001 | A / 101 | NURSE_A |
| PB02 | P002 | A / 102 | NURSE_A |
| PB03 | P003 | A / 103 | NURSE_A |
| PB04 | P004 | B / 104 | NURSE_B |
| PB05 | P005 | B / 105 | NURSE_B |
| PB06 | P006 | B / 106 | NURSE_B |

Danh mục: MED001–Vitamin C, MED002–Vitamin D3, MED003–Canxi, MED004–Vitamin B12. Mã gán khác nhau giữa các hộp: xem mã đúng ở Nạp thuốc. PB01 tương thích firmware: S1/ngăn 1 lúc 08:00, S2/ngăn 1 lúc 14:00, S3/ngăn 2 lúc 09:00, S4/ngăn 3 lúc 20:00.

### Tài khoản có sẵn

| Tài khoản | Quyền | Phạm vi |
|---|---|---|
| ADMIN01 | Quản trị; cập nhật lịch | Tất cả hộp |
| NURSE_A | Nạp thuốc, cảnh báo, điều khiển | PB01–PB03 |
| NURSE_B | Nạp thuốc, cảnh báo, điều khiển | PB04–PB06 |
| FAMILY01 | Theo dõi | PB01 |

`accounts create` tạo sẵn khóa riêng, lưu tại `gateway/auth.local.json`. Chạy lại giữ nguyên khóa. `accounts show` hiển thị tài khoản, quyền, hộp được phân công và khóa: chỉ sao chép chuỗi ở cột cuối vào web.

Khóa là bearer token, ai giữ khóa có quyền của tài khoản. Khóa mới dài **24 ký tự ngẫu nhiên** thay vì 43 ký tự trước đây; không cần tự nghĩ/gõ lại. Không dùng tên admin hoặc mã ngắn cố định. Mỗi máy sinh khóa riêng, không có khóa chung trong source.

Thay toàn bộ khóa: `./.venv/Scripts/python.exe -m gateway.accounts create --rotate`, sau đó khởi động lại Gateway. Khóa cũ được sao lưu. File chứa khóa và DB được Git bỏ qua. Tài khoản/phân công hiện quản lý bằng CLI/cấu hình, chưa có màn hình quản trị tài khoản. License Wokwi khác hoàn toàn khóa Dashboard.

## 4. Chạy local với 6 hộp trực tuyến

Git Bash:

```bash
./.venv/Scripts/python.exe -m gateway.local_system
```

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m gateway.local_system
```

Mở **http://127.0.0.1:5000**, nhập khóa tại **Tài khoản → Kết nối**. Tên tài khoản và vai trò hiện ngay trên thanh đầu trang. Hộp thoại báo rõ kết quả đăng nhập; nhấn × để đóng.

Chế độ local tự bật xác thực, dùng `gateway/data/pillbox.db`, không gửi dữ liệu ra broker. Chỉ chạy một Gateway trên cổng 5000. Cổng khác: thêm `--port 5001`. Dừng bằng Ctrl+C.

### Kiểm thử giao diện

Đăng nhập ADMIN01 hoặc nurse, chọn hộp rồi mở **Thiết bị → Mô phỏng phần mềm**. Nút tác động lên hộp đang chọn.

| Thử nghiệm | Thao tác | Kết quả |
|---|---|---|
| Đúng giờ | Nhắc ngăn 1 → Mở ngăn 1 | REMINDER_STARTED, TAKEN_ON_TIME |
| Sai ngăn | Nhắc ngăn 1 → Mở ngăn 2 | WRONG_SLOT và cảnh báo; chưa hoàn tất ngăn 1 |
| Lấy trễ | Quá giờ ngăn 1 → Mở ngăn 1 | MISSED rồi TAKEN_LATE, trễ 20 phút; cảnh báo quá giờ được giải quyết |
| Ngoài lịch | Hoàn tất lịch đang nhắc → Mở ngăn 3 | UNSCHEDULED_OPEN |
| Bảo quản | Nóng / ẩm cao → Môi trường bình thường | Số đo/cảnh báo thay đổi rồi hồi phục |
| Cảm biến | Lỗi cảm biến → Môi trường bình thường | SENSOR_ERROR rồi hồi phục |
| Mất kết nối | Ngắt kết nối → Cập nhật trạng thái | Ngoại tuyến, lệnh gửi thất bại |
| Kết nối lại | Kết nối lại → Cập nhật trạng thái | Trực tuyến, ACK Đã áp dụng |
| Tắt nhắc | Nhắc ngăn 1 → Tắt âm & đèn nhắc | Dừng cảnh báo, không tự ghi nhận lấy thuốc |
| Phân trang | Tạo hơn 8 thao tác → Lịch sử | Có trang tiếp theo |

Nút local tạo sự kiện kiểm thử mang nhãn `software_simulator`; mỗi lượt nhắc mới có occurrence riêng để thử lại. Chúng không chạy driver/thuật toán thời gian ESP32; dùng Wokwi để kiểm tra những phần đó.

### Nạp thuốc

1. Chọn PB01, mở Nạp thuốc: hồ sơ P001, ngăn 1, mã MED001.
2. Nhập MED002 để thử sai mã; đổi về MED001 → Xác minh mã.
3. Bắt đầu nạp, chờ ACK phiên.
4. Sang Thiết bị → Mở ngăn 1, rồi quay lại Nạp thuốc. Có REFILL_OPEN.
5. Xác nhận nạp: lịch sử ghi người thao tác, phiên kết thúc có ACK.
6. Thử xác nhận trước khi mở: bị từ chối. Mở sai ngăn không đủ điều kiện xác nhận. Kết thúc phiên hủy quyền mở để nạp; phiên hết hạn tối đa 5 phút.

REFILL_OPEN không hoàn tất lịch lấy thuốc. Đổi hộp/ngăn/mã cần xác minh lại.

### Tài khoản và phân quyền

Mở Tài khoản, nhập khóa khác → Kết nối để đổi người dùng. Khóa chỉ giữ trong bộ nhớ trang; tải lại trang cần nhập lại.

- ADMIN01 thấy 6 hộp; NURSE_A thấy PB01–PB03; NURSE_B thấy PB04–PB06.
- FAMILY01 chỉ thấy PB01, không có phần nạp thuốc/nút mô phỏng.
- Khóa sai bị từ chối. Nurse không được cập nhật lịch; admin được phép.

Chưa có form sửa lịch trên web. Thử API trong Git Bash, nhập khóa qua `read` để không lưu vào lịch sử lệnh:

```bash
read -s -p "Khoa truy cap: " TOKEN
curl -i -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5000/api/session
curl -i -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5000/api/devices/PB04/live
curl -i -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"command":"UPDATE_SCHEDULE","schedule_id":"S1","hour":8,"minute":10,"enabled":true}' \
  http://127.0.0.1:5000/api/devices/PB01/commands
unset TOKEN
```

NURSE_A truy cập PB04 hoặc cập nhật lịch bị 403; ADMIN01 được phép. Lệnh gửi thành công trả 202, kiểm tra ACK ở Thiết bị. Không gửi khóa thì `/api/session` trả 401 khi xác thực bật.

## 5. Chạy firmware bằng Wokwi

Dừng local_system trước khi chuyển chế độ. Gateway thông thường không chạy sáu hộp phần mềm; chỉ hộp có thiết bị gửi heartbeat mới trực tuyến.

**Terminal 1, Git Bash:**

```bash
export PILLBOX_AUTH_FILE="gateway/auth.local.json"
export PILLBOX_DB="gateway/data/pillbox.db"
export MQTT_HOST="test.mosquitto.org"
export MQTT_PORT="1883"
export PILLBOX_MQTT_AUTOSTART="1"
export PILLBOX_BIND="127.0.0.1"
export PORT="5000"
./.venv/Scripts/python.exe -m gateway.app
```

**Terminal 1, PowerShell:**

```powershell
$env:PILLBOX_AUTH_FILE="gateway/auth.local.json"
$env:PILLBOX_DB="gateway/data/pillbox.db"
$env:MQTT_HOST="test.mosquitto.org"
$env:MQTT_PORT="1883"
$env:PILLBOX_MQTT_AUTOSTART="1"
$env:PILLBOX_BIND="127.0.0.1"
$env:PORT="5000"
.\.venv\Scripts\python.exe -m gateway.app
```

Đặt biến trong cùng terminal khởi chạy Gateway. Chương trình không tự đọc `.env`. Broker trên công khai/không mã hóa, chỉ dùng dữ liệu thử nghiệm.

**Terminal 2, Git Bash:**

```bash
"$HOME/.platformio/penv/Scripts/platformio.exe" run -e esp32s2_wokwi
```

**Terminal 2, PowerShell:**

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e esp32s2_wokwi
```

Chờ SUCCESS; `.pio/build/esp32s2_wokwi/` phải có firmware.bin và firmware.elf. F1 → Wokwi: Start Simulator. Người clone mới phải build vì `.pio` không được commit.

Thiếu/hết hạn license: F1 → Wokwi: Request a New License, kích hoạt rồi Wokwi: Manually Enter License Key nếu cần. License không lưu trong source.

Mặc định: PB01, Wi-Fi Wokwi-GUEST/mật khẩu trống, broker như trên. Không chạy hai PB01 trên cùng broker. Giữ simulator đang hiển thị.

### Kiểm thử simulator

- RTC bắt đầu 07:59:50; đến 08:00 ngăn 1 nhắc. Bấm nút 2 thử sai ngăn, nút 1 thử lấy đúng.
- View → Terminal → Wokwi Terminal: nhập `TIME 09:00` rồi Enter để thử ngăn 2, `TIME 20:00` để thử ngăn 3. Thành công hiện DEMO clock updated.
- Lượt chưa hoàn tất: `TIME 08:15`, `TIME 10:00`, bấm ngăn 1 để lấy trễ. Nếu lượt cùng ngày đã hoàn tất, đổi ngày `initTime` RTC trong diagram.json rồi Stop/Start; ledger chống ghi nhận lặp.
- DHT22: 32 °C/75% để cảnh báo, 25 °C/50% để hồi phục; cần 3 mẫu liên tiếp, khoảng 4–6 giây mô phỏng. Ngưỡng chỉ minh họa.
- Nạp như mục 4, thay nút local bằng nút ngăn trên Wokwi. Chờ Giờ UTC: Đã đồng bộ trước khi bắt đầu nạp.

Heartbeat 5 giây, DHT 2 giây, web cập nhật khoảng 1 giây/lần. Sau sửa firmware: build → Stop/Start; sau sửa web: khởi động lại Gateway → Ctrl+Shift+R.

## 6. Kiểm thử tự động

Git Bash:

```bash
./.venv/Scripts/python.exe -m unittest discover -s gateway/tests -t . -q
node test/ui_auth.mjs
```

Tests dùng DB tạm. Test đăng nhập cần Node.js 22+, không cần broker. TLS cần OpenSSL; xem kết quả skip nếu máy thiếu.

Firmware: `pio test -e native` cần compiler C++; `pio run -e esp32s2_wokwi` kiểm tra mô phỏng, `pio run -e adafruit_feather_esp32s2` kiểm tra board thật. Host harness:

```bash
g++ -std=c++11 -Iinclude test/host_scheduler/main.cpp src/app/Scheduler.cpp -o .pio/host_scheduler.exe
./.pio/host_scheduler.exe
```

Tùy chọn: chạy `python -m gateway.tests.mqtt_e2e` bằng Python .venv để test broker bằng dữ liệu tổng hợp, cần mạng. `test/ui_dashboard.mjs` cần Edge/Chromium CDP và Gateway với DB kiểm thử riêng. Không chạy vào dữ liệu chăm sóc thật.

`node test/ui_local_system.mjs` kiểm tra 4 tài khoản, phạm vi hộp, tên tài khoản luôn hiện và bố cục desktop/mobile trên bản local. Cần Edge/Chromium đã mở CDP cổng 9336 bằng profile kiểm thử riêng; script chỉ đăng nhập/đọc dữ liệu, không bấm các nút tạo sự kiện. Có thể đặt `PILLBOX_CDP` và `PILLBOX_URL` để đổi địa chỉ.

## 7. Lỗi thường gặp

| Hiện tượng | Xử lý |
|---|---|
| Address already in use | Dừng Gateway cũ, chỉ chạy một tiến trình trên cổng 5000 |
| Không yêu cầu khóa truy cập | Chưa bật PILLBOX_AUTH_FILE; local_system tự bật |
| Kết nối bị kẹt/trang cũ | Khởi động lại Gateway rồi Ctrl+Shift+R |
| 401 | Sai/thiếu khóa hoặc Gateway dùng file auth khác |
| 403 | Vượt quyền thao tác/hộp được phân công |
| Chỉ thấy ít hộp | Kiểm tra tài khoản; admin thấy đủ 6 hộp |
| Không có nút mô phỏng | Chỉ hiện với local_system và nurse/admin |
| Firmware not found | Build đúng esp32s2_wokwi trước khi Start Simulator |
| Bash lỗi tại & | Dùng đúng lệnh Git Bash, không dùng cú pháp PowerShell |
| Nạp chưa bắt đầu | Kiểm tra online, UTC, phiên/ACK và đúng ngăn |
| Wokwi Terminal không nhập được | Chọn đúng terminal, build lại và Stop/Start simulator |

## 8. Cấu trúc và giới hạn

- `src/`, `include/`: firmware Scheduler, MQTT, NVS, cảm biến/điều khiển.
- `gateway/`: Flask, SQLite, phân quyền, phiên nạp/cảnh báo, CLI tài khoản và local simulator.
- `gateway/templates/`, `gateway/static/`: HTML/CSS/JS, favicon, ảnh tải sẵn.
- `gateway/data/`: DB và backup, được Git bỏ qua.
- `deploy/`: Docker, Mosquitto TLS/ACL, Caddy HTTPS, cấp khóa.
- `gateway/tests/`, `test/`: kiểm thử API, TLS, local simulator, firmware và giao diện.

Queue firmware nằm trong RAM, có giới hạn; reset/mất điện có thể mất sự kiện chưa gửi. Chưa có application ACK bền vững cho event; ACK lệnh xử lý riêng. HX711, deep sleep, pin và triển khai VLAN cần nghiệm thu riêng. Cấu hình Docker/TLS sẵn không đồng nghĩa đã kiểm thử trên hạ tầng thật.

Ảnh: [Anna Shvets](https://www.pexels.com/photo/photo-medication-pills-on-white-plastic-container-3683074/) và [Polina Tankilevitch](https://www.pexels.com/photo/photo-of-pills-on-container-3873162/) trên Pexels, chỉ dùng minh họa.
