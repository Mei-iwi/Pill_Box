# Hộp đựng thuốc thông minh

Hệ thống dùng ESP32-S2 để nhắc lịch lấy thuốc, ghi nhận mở ba ngăn và theo dõi nhiệt độ/độ ẩm. Gateway Python nhận MQTT, lưu SQLite và cung cấp Dashboard tiếng Việt. Người chăm sóc xác minh mã thuốc, mở phiên nạp giới hạn thời gian rồi xác nhận sau khi mở đúng ngăn.

Mở ngăn chỉ xác nhận thao tác lấy thuốc. Cấu hình và dữ liệu kiểm thử dùng hồ sơ ẩn danh, không phải đơn thuốc hoặc lịch sử chăm sóc thật.

**Lần đầu:** làm mục 2 → 3 → 4 để chạy local. **Những lần sau:** chạy `./.venv/Scripts/python.exe -m gateway`. Chế độ, DB, cổng web và broker được giữ trong `gateway/.env`; không cần khai báo lại biến hoặc reset dữ liệu.

### Khởi động nhanh khi đã thiết lập

Mở terminal tại thư mục gốc project, chỉ chạy **một** lệnh phù hợp với terminal đang dùng:

Git Bash:

```bash
./.venv/Scripts/python.exe -m gateway
```

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m gateway
```

Mở **http://127.0.0.1:5000** với cấu hình mặc định. Nếu đã đổi `PORT`, mở đúng cổng đã lưu. Giữ terminal Gateway chạy; nhấn Ctrl+C để dừng trước khi chạy lại.

Muốn đổi chế độ, DB hoặc cổng, sửa **`gateway/.env`** rồi khởi động lại. File đã tồn tại và đúng cấu hình thì giữ nguyên. Khi người khác clone về, họ cần tạo `.env` từ mẫu vì file cấu hình riêng không được đưa lên Git.

| Cần làm | Hướng dẫn |
|---|---|
| Tài khoản, nạp thuốc và sáu hộp | [Chạy local](#4-chạy-local-với-6-hộp-trực-tuyến) |
| Nút, LED/buzzer và firmware | [Wokwi](#5-chạy-firmware-bằng-wokwi) |
| Biểu đồ, HTTP và thông báo | [Chức năng tích hợp lab](#6-chức-năng-tích-hợp-từ-các-bài-lab) |
| Kiểm thử tự động | [Chạy test](#7-kiểm-thử-tự-động) |
| Broker riêng và HTTPS | [Triển khai bảo mật](deploy/README.md) |

## 1. Chọn cách chạy

| Chế độ | Mục đích | Kết nối |
|---|---|---|
| Local, 6 hộp phần mềm | Test web, tài khoản, phân quyền, cảnh báo và nạp thuốc | Không cần Wokwi/broker |
| Wokwi + Gateway | Test firmware, nút bấm, LED/buzzer, DHT22 và MQTT | PB01 trên Wokwi |
| ESP32-S2 thật + Gateway | Chạy trên mạch đã nối và cấu hình riêng | Board và Gateway cùng truy cập được broker |
| Triển khai bảo mật | MQTT TLS, ACL từng hộp, HTTPS và phân quyền | Xem [deploy/README.md](deploy/README.md) |

Hộp local trực tuyến nhờ tiến trình mô phỏng gửi heartbeat mỗi 5 giây. Đây là **mô phỏng phần mềm**, không phải sáu board thật. Dừng tiến trình sẽ báo ngoại tuyến; heartbeat quá 65 giây cũng bị coi là mất kết nối.

## 2. Clone và cài đặt

Cần Git, Python 3.11–3.13 và trình duyệt. Firmware cần VS Code, PlatformIO IDE và Wokwi Simulator.

Clone bản trên nhánh `main`; nếu đã có project thì bỏ qua bước clone. Khi thử một tính năng chưa merge vào main, chuyển sang đúng nhánh được cung cấp.

Hướng dẫn chạy bằng `.env` cần phiên bản có `gateway/config.py` và `gateway/__main__.py`. Nếu hai file chưa có, bản source đang dùng chưa chứa thay đổi cấu hình này.

```bash
git clone https://github.com/Mei-iwi/Pill_Box.git
cd Pill_Box
code .
```

Đã clone: lưu/commit thay đổi cá nhân trước khi cập nhật:

```bash
git fetch origin
git switch main
git pull --ff-only
```

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

Không cần chạy `Activate.ps1`: các lệnh gọi thẳng Python trong `.venv`. Nếu Windows chưa nhận `python`, dùng `py -3` khi tạo môi trường. Các lần mở project sau không phải tạo lại `.venv`.

Sau khi pull phiên bản bổ sung dependency, chạy lại lệnh `pip install -r gateway/requirements.txt` bằng Python `.venv` ở trên. Cơ chế đọc `.env` sử dụng `python-dotenv`.

Git Bash dùng `cd /d/StudyMaterials/...`; PowerShell dùng `cd D:\StudyMaterials\...`. Không nhập cú pháp `$env:...` hoặc `&` của PowerShell vào Git Bash.

### Tạo file cấu hình một lần

Tạo file cấu hình local từ mẫu, chỉ làm lần đầu:

Git Bash:

```bash
cp -n gateway/.env.example gateway/.env
```

PowerShell:

```powershell
if (-not (Test-Path gateway/.env)) {
    Copy-Item gateway/.env.example gateway/.env
}
```

Mở `gateway/.env` trong VS Code để chỉnh. Mẫu mặc định chạy sáu hộp phần mềm local:

```dotenv
PILLBOX_MODE=local
PILLBOX_DB=gateway/data/pillbox.db
PILLBOX_AUTH_FILE=gateway/auth.local.json
PILLBOX_BIND=127.0.0.1
PORT=5000
PILLBOX_MQTT_AUTOSTART=0
PILLBOX_HTTP_INGEST=1
```

| File | Khi nào sử dụng |
|---|---|
| `gateway/.env` | File đang được chương trình đọc; chỉnh ở đây để áp dụng cho những lần chạy sau |
| `gateway/.env.example`, `gateway/.env.local.example` | Mẫu local để tạo file mới; sửa mẫu không tự đổi cấu hình đang chạy |
| `gateway/.env.wokwi.example` | Mẫu MQTT/Wokwi; xem mục 5 để chuyển chế độ |
| `gateway/auth.local.json` | Tài khoản và khóa truy cập; có thể đổi đường dẫn bằng PILLBOX_AUTH_FILE |
| `include/config/Secrets.h` | Wi-Fi/broker/ID của firmware ESP32; cần build/nạp lại khi thay đổi |

| Biến | Ý nghĩa |
|---|---|
| `PILLBOX_MODE` | `local`: sáu hộp phần mềm; `mqtt`: Gateway kết nối thiết bị qua broker |
| `PILLBOX_DB` | Đường dẫn SQLite; mặc định `gateway/data/pillbox.db` |
| `PILLBOX_AUTH_FILE` | File tài khoản và khóa; lệnh `accounts create/show` cũng đọc biến này |
| `PILLBOX_BIND`, `PORT` | Địa chỉ và cổng web |
| `PILLBOX_MQTT_AUTOSTART` | `1` bật MQTT listener ở chế độ mqtt; local luôn tắt MQTT bên ngoài |
| `PILLBOX_HTTP_INGEST` | `1` mở API telemetry thử nghiệm cho admin; `0` tắt API này |
| `MQTT_HOST`, `MQTT_PORT` | Địa chỉ và cổng broker; cần khớp firmware |
| `MQTT_TLS`, `MQTT_CA_FILE` | Bật TLS và đường dẫn CA của broker riêng |
| `MQTT_USER`, `MQTT_PASSWORD` | Tài khoản broker khi cần xác thực |

<details>
<summary>Cấu hình nâng cao và thứ tự ưu tiên</summary>

Quy tắc cấu hình:

- Thứ tự ưu tiên: **tham số CLI → biến terminal/Docker → file `.env` → giá trị mặc định**. Biến đã export trong terminal vẫn thắng file; mở terminal mới hoặc bỏ biến cũ nếu thấy cấu hình không đổi.
- Chỉ tự đọc `gateway/.env`, không dò file `.env` ở thư mục cha. Đường dẫn tương đối cho DB, tài khoản và chứng chỉ tính từ thư mục gốc repository; trên Windows có thể dùng dấu `/`.
- Sửa file rồi khởi động lại Gateway. Không cần `source .env`, `export` hay `$env:...` mỗi lần chạy. File không được thực thi như script; `${...}` trong giá trị được giữ nguyên, không nội suy. Đặt giá trị chứa dấu `#` hoặc khoảng trắng trong dấu nháy.
- File `.env`, các profile `.env.*` riêng và khóa tài khoản được Git bỏ qua, không chép vào Docker image. Chỉ các file `.example` được đưa lên Git.
- Các lệnh cũ `python -m gateway.local_system` và `python -m gateway.app` vẫn chạy; chúng chọn trực tiếp local hoặc Gateway thông thường. Lệnh chung `python -m gateway` mới chọn theo `PILLBOX_MODE`.

Kiểm tra cấu hình hiệu lực, không in khóa hoặc mật khẩu:

```bash
./.venv/Scripts/python.exe -m gateway.config
```

Ghi đè tạm thời hoặc dùng file cấu hình riêng:

```bash
./.venv/Scripts/python.exe -m gateway --port 5001
./.venv/Scripts/python.exe -m gateway --env-file gateway/.env.wokwi
```

Lệnh thứ hai cần file `gateway/.env.wokwi` tồn tại, có thể tạo từ `gateway/.env.wokwi.example`. Thêm `--db`, `--bind`, `--mode local` hoặc `--mode mqtt` khi cần ghi đè. `PILLBOX_ENV_FILE` trong terminal/Docker cũng chọn được file; `PILLBOX_LOAD_ENV=0` tắt đọc file và chỉ dùng biến môi trường. Hai biến chọn/tắt file chỉ nhận từ terminal hoặc CLI, không đọc từ nội dung `.env`.

Chỉ thêm `--mode mqtt` không bật listener nếu `PILLBOX_MQTT_AUTOSTART` vẫn là `0`; cấu hình Wokwi cần cả chế độ mqtt và autostart bằng `1` như mục 5.

</details>

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

Nếu đổi `PILLBOX_DB` trong `.env`, dùng đúng đường dẫn đó cho lệnh reset/khởi tạo, ví dụ `--db gateway/data/lab-check.db`. Reset local chỉ cho phép DB trong `gateway/data`; không tự xóa DB mỗi lần khởi động.

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

`accounts create` tạo sẵn khóa riêng trong file `PILLBOX_AUTH_FILE`, mặc định `gateway/auth.local.json`. Chạy lại giữ nguyên khóa. `accounts show` đọc cùng file và hiển thị tài khoản, quyền, hộp được phân công, khóa: chỉ sao chép chuỗi ở cột cuối vào web.

Khóa là bearer token, ai giữ khóa có quyền của tài khoản. Khóa được tạo mới dài **24 ký tự ngẫu nhiên**, không cần tự nghĩ/gõ lại. Mỗi máy sinh khóa riêng; tên ADMIN01 hoặc NURSE_A không dùng thay cho khóa.

Thay toàn bộ khóa: `./.venv/Scripts/python.exe -m gateway.accounts create --rotate`, sau đó khởi động lại Gateway. Khóa cũ được sao lưu. File chứa khóa và DB được Git bỏ qua. Tài khoản/phân công hiện quản lý bằng CLI/cấu hình, chưa có màn hình quản trị tài khoản. License Wokwi khác hoàn toàn khóa Dashboard.

Nếu nâng cấp từ bản cũ đã có `auth.local.json`, lệnh `create` không tự thêm hoặc đổi tài khoản cũ. Chỉ dùng `--rotate` khi muốn tạo lại bộ bốn tài khoản ở bảng trên; khi đó phải phân phối lại khóa mới.

## 4. Chạy local với 6 hộp trực tuyến

Git Bash:

```bash
./.venv/Scripts/python.exe -m gateway
```

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m gateway
```

Mở **http://127.0.0.1:5000** hoặc cổng đã đặt trong `.env`, nhập khóa tại **Tài khoản → Kết nối**. Tên tài khoản và vai trò hiện ngay trên thanh đầu trang. Hộp thoại báo rõ kết quả đăng nhập; nhấn × để đóng.

Giữ `PILLBOX_MODE=local` trong `.env` để chạy sáu hộp. Chế độ này tự bật xác thực, dùng DB/tài khoản/cổng đã cấu hình và không gửi dữ liệu ra broker. Chỉ chạy một Gateway trên cùng cổng. Dừng bằng Ctrl+C.

Cả local và MQTT đọc `PILLBOX_AUTH_FILE`. Muốn dùng DB kiểm thử khác, khởi tạo DB đó rồi đặt `PILLBOX_DB` trong `.env` hoặc chạy `./.venv/Scripts/python.exe -m gateway --db gateway/data/lab-check.db --port 5001`. `accounts create/show` mặc định dùng cùng file tài khoản, có thể ghi đè bằng `--file`.

Đăng nhập ADMIN01 để kiểm tra đủ PB01–PB06 và số đo mới. Đăng nhập nurse/family sẽ thấy ít hộp hơn theo phân quyền. Trên web, nhấn Ctrl+Shift+R sau khi cập nhật source; Gateway đang chạy cần khởi động lại để nạp mã Python mới.

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

Nếu cần lấy lại khóa khi Gateway đang chạy, mở **terminal thứ hai** tại project và chạy `./.venv/Scripts/python.exe -m gateway.accounts show`; không nhập lệnh vào terminal đang phục vụ web. Với PowerShell dùng đường dẫn Python tương ứng ở mục 2.

- ADMIN01 thấy 6 hộp; NURSE_A thấy PB01–PB03; NURSE_B thấy PB04–PB06.
- FAMILY01 chỉ thấy PB01, không có phần nạp thuốc/nút mô phỏng.
- FAMILY01 không được gửi lệnh điều khiển, kể cả gọi trực tiếp API. Có khóa đúng nhưng vượt quyền sẽ nhận 403.
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

Ví dụ trên làm đổi lịch S1 của PB01 sang 08:10 khi nhận ACK. Sau khi thử, gửi lại với `"minute":0` để trở về lịch 08:00 của kịch bản Wokwi. Không gửi lại chỉ vì thấy PENDING; kiểm tra ACK và trạng thái trước.

## 5. Chạy firmware bằng Wokwi

Dừng Gateway local bằng Ctrl+C trước khi chuyển chế độ. Gateway MQTT không chạy sáu hộp phần mềm; chỉ hộp có thiết bị gửi heartbeat mới trực tuyến.

Chỉnh và lưu các dòng sau trong `gateway/.env` **một lần** khi chuyển sang Wokwi:

```dotenv
PILLBOX_MODE=mqtt
PILLBOX_MQTT_AUTOSTART=1
PILLBOX_HTTP_INGEST=0
MQTT_HOST=test.mosquitto.org
MQTT_PORT=1883
MQTT_TLS=0
```

Giữ DB và file tài khoản đang dùng. Có thể tham khảo toàn bộ mẫu `gateway/.env.wokwi.example`. Broker công khai/không mã hóa chỉ dùng dữ liệu thử nghiệm; cấu hình broker riêng xem `deploy/README.md`. Đổi `.env` chỉ cấu hình Gateway, không tự đổi hoặc nạp lại firmware ESP32.

**Terminal 1, Git Bash:**

```bash
./.venv/Scripts/python.exe -m gateway
```

**Terminal 1, PowerShell:**

```powershell
.\.venv\Scripts\python.exe -m gateway
```

Các lần chạy sau dùng lại đúng một lệnh này. Muốn trở về sáu hộp phần mềm, đổi `PILLBOX_MODE=local` rồi khởi động lại. Giữ terminal Gateway đang chạy trong lúc mở simulator.

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

Heartbeat 5 giây, DHT đọc mỗi 2 giây. Firmware gửi số đo khi thay đổi ít nhất 0,3 °C hoặc 2% RH, đổi trạng thái cảm biến/cảnh báo, kết nối lại hoặc hết 30 giây; sự kiện cảnh báo vẫn gửi ngay. Web cập nhật khoảng 1 giây/lần. Sau sửa firmware: build → Stop/Start; sau sửa web: khởi động lại Gateway → Ctrl+Shift+R.

### Kết nối nhiều hộp Wokwi hoặc board thật

Một Gateway nhận nhiều hộp qua cùng broker. `local_system` không làm cầu nối MQTT với Wokwi; dừng local trước khi chuyển sang Gateway MQTT.

Mỗi thiết bị cần firmware được build với ID và prefix lịch riêng trong `include/config/Secrets.h`, tạo từ `Secrets.example.h`:

| Hộp | `PILLBOX_DEVICE_ID` | `PILLBOX_SCHEDULE_PREFIX` |
|---|---|---|
| PB01 | `"PB01"` | `""` |
| PB02 | `"PB02"` | `"PB02_"` |
| PB03 | `"PB03"` | `"PB03_"` |

1. Khai báo cùng địa chỉ/cổng broker với Gateway; board thật điền Wi-Fi riêng. Wokwi dùng Wokwi-GUEST.
2. Build/nạp riêng từng hộp; nhiều phiên Wokwi cần thư mục và firmware riêng để không dùng nhầm binary. Giữ các phiên mô phỏng hoạt động.
3. PB01–PB06 đã được đăng ký trong bộ dữ liệu. Hộp ngoài danh sách cần `gateway.provision`, quyền tài khoản và ACL broker tương ứng; xem [deploy/README.md](deploy/README.md).
4. Đối chiếu giờ, mã thuốc và lịch từng ngăn. Firmware mặc định dùng bộ mã/lịch PB01; **đổi ID/prefix chưa tự đồng bộ giờ và mã thuốc của bộ dữ liệu mới**. Giờ có thể cập nhật qua UPDATE_SCHEDULE; mã thuốc cần khớp firmware và gán ngăn tại Gateway.
5. Đăng nhập ADMIN01, kiểm tra heartbeat/boot mới của từng hộp; thao tác ở hộp này không tác động hộp khác.

Board thật build bằng environment `adafruit_feather_esp32s2`, nạp qua PlatformIO Upload với đúng cổng. Nguồn, RTC và cảm biến cần kiểm tra trên mạch; build thành công chưa chứng minh phần cứng hoạt động ổn định.

## 6. Chức năng tích hợp từ các bài lab

- Lịch sử có biểu đồ nhiệt độ/độ ẩm với khoảng 1 giờ hoặc 24 giờ, gom mẫu và cập nhật mỗi 10 giây.
- Danh sách lệnh hiển thị thời gian ACK đo tại Gateway. Quá 60 giây chưa ACK chuyển TIMEOUT khi web/API được truy cập.
- Thiết bị có RSSI/IP khi firmware gửi heartbeat; board thật đồng bộ RTC từ NTP khi có UTC hợp lệ và mỗi 6 giờ, không thay giờ TIME của Wokwi.
- Family chỉ xem, không gọi được API điều khiển. API POST telemetry dành cho admin trong chế độ local; Gateway thông thường mặc định tắt.
- Rule chain phân loại cảnh báo đã xác nhận thành warning/critical, có hồi phục và outbox thông báo chống lặp. Email mặc định không gửi.

Xem [đối chiếu đầy đủ Lab 1–9 và Lab 5_1](docs/lab-integration.md) để thử HTTP bằng Postman, kiểm tra outbox và cấu hình SMTP TLS tùy chọn.

### Biểu đồ và thời gian phản hồi

Mở **Lịch sử → Biểu đồ môi trường**, chọn **1 giờ** hoặc **24 giờ**. Biểu đồ dùng thời điểm Gateway nhận mẫu, trung bình theo phút hoặc 10 phút, tối đa 145 điểm; chỉ mẫu cảm biến hợp lệ được vẽ. Mẫu ổn định tạo đường ngang; lỗi cảm biến vẫn được ghi ở lịch sử/cảnh báo.

Trong **Thiết bị**, lệnh APPLIED có thời gian ACK đo tại Gateway. TIMEOUT nghĩa là chưa nhận ACK trong thời hạn, không khẳng định thiết bị chưa thực thi. ACK muộn không đổi TIMEOUT thành APPLIED; đọc trạng thái trước khi quyết định gửi lại.

### Kiểm thử HTTP/JSON và mức cảnh báo

Dùng ADMIN01 với DB kiểm thử riêng. Mẫu `.env` local đặt `PILLBOX_HTTP_INGEST=1`; mẫu Wokwi đặt `0`. Đặt `1` trong `.env` rồi khởi động lại để mở API thử nghiệm, đặt `0` để tắt. Quyền admin vẫn bắt buộc ở cả hai chế độ.

Trong Postman, gửi `POST http://127.0.0.1:5000/api/devices/PB06/telemetry`, chọn **Authorization → Bearer Token**, nhập khóa admin, chọn **Body → raw → JSON**:

```json
{
  "kind": "environment",
  "message": {
    "device_id": "PB06",
    "boot_id": "postman-lab",
    "seq": 1,
    "sensor_ok": true,
    "temperature_c": 32,
    "humidity_percent": 75,
    "storage_status": "WARNING"
  }
}
```

Kỳ vọng HTTP **201**, nội dung `{"result":"STORED"}`. Chọn **PB06 → Thiết bị → Ngắt kết nối** trước khi thử chuỗi POST để heartbeat local không thay thế mẫu thủ công sau 5 giây; hoàn tất thì **Kết nối lại**. Đây là dữ liệu kiểm thử, không phải phép đo firmware. Nếu chạy DB riêng trên cổng 5001, đổi URL tương ứng.

| Mẫu gửi | Kết quả cần kiểm tra |
|---|---|
| seq 1, 32 °C/75%, WARNING | Cảnh báo warning |
| seq 2, 40 °C/75%, WARNING | Nâng critical, ghi ESCALATED |
| seq 3, 25 °C/50%, NORMAL | Hồi phục, ghi RECOVERED |
| Gửi lại cùng boot_id/seq | Không thêm mẫu hoặc tạo chuyển cảnh báo mới |
| Thiếu khóa / khóa family hoặc nurse | 401 / 403 |
| Sai schema / body trên 8 KiB | 400 / 413 |

Trong firmware, vượt 30 °C/70% RH và hồi phục dưới 28 °C/68% cần 3 mẫu mới liên tiếp. Gateway nâng critical trên WARNING đã xác nhận khi >35 °C hoặc >85% RH; hạ critical cần ≤33 °C và ≤83% RH, hoặc nhận NORMAL. Ngưỡng phục vụ đồ án, không áp dụng chung cho mọi thuốc.

### Outbox và email tùy chọn

OPEN, ESCALATED, RECOVERED được lưu trong SQLite; trạng thái lặp không sinh thông báo liên tục. ADMIN01 đọc bản ghi gần đây qua `GET /api/notifications` với Bearer token.

Kiểm tra hàng đợi mà **không gửi email**:

```bash
./.venv/Scripts/python.exe -m gateway.notifications --db gateway/data/pillbox.db
```

Email không tự gửi khi mở web. Gửi thật cần quản trị viên cấu hình SMTP TLS và chủ động chạy CLI với `--send`; xem [hướng dẫn SMTP](docs/lab-integration.md#thông-báo-cảnh-báo). Mỗi bản ghi lỗi được thử tối đa 3 lần qua các lần gọi CLI, không có retry nền tự động. Các test dùng transport giả; dịch vụ SMTP thực tế chưa được nghiệm thu.

## 7. Kiểm thử tự động

Git Bash:

```bash
./.venv/Scripts/python.exe -m unittest discover -s gateway/tests -t . -q
node test/ui_auth.mjs
```

Tests dùng DB tạm. Test đăng nhập cần Node.js 22+, không cần broker. TLS cần OpenSSL; xem kết quả skip nếu máy thiếu.

Lần kiểm tra bản cấu hình `.env` đạt **97/97 test Gateway**, trong đó có 15 test cấu hình/CLI về thứ tự ưu tiên, đường dẫn, profile, tài khoản và cách khởi động. Các kiểm tra trước đó của bản tích hợp lab gồm 4 test native, host C++, build Wokwi/Feather/profile TLS và browser desktop/mobile. Test SMTP dùng transport giả; build không thay thế nghiệm thu board thật.

Firmware: `pio test -e native` cần compiler C++; `pio run -e esp32s2_wokwi` kiểm tra mô phỏng, `pio run -e adafruit_feather_esp32s2` kiểm tra board thật. Host harness:

```bash
g++ -std=c++11 -Iinclude test/host_scheduler/main.cpp src/app/Scheduler.cpp -o .pio/host_scheduler.exe
./.pio/host_scheduler.exe
```

Tùy chọn: chạy `python -m gateway.tests.mqtt_e2e` bằng Python .venv để test broker bằng dữ liệu tổng hợp, cần mạng. `test/ui_dashboard.mjs` cần Edge/Chromium CDP và Gateway với DB kiểm thử riêng. Không chạy vào dữ liệu chăm sóc thật.

`node test/ui_local_system.mjs` kiểm tra 4 tài khoản, phạm vi hộp, tên tài khoản luôn hiện và bố cục desktop/mobile trên bản local. Cần Edge/Chromium đã mở CDP cổng 9336 bằng profile kiểm thử riêng; script chỉ đăng nhập/đọc dữ liệu, không bấm các nút tạo sự kiện. Có thể đặt `PILLBOX_CDP` và `PILLBOX_URL` để đổi địa chỉ.

Ví dụ mở browser kiểm thử bằng **PowerShell** sau khi Gateway local đã chạy:

```powershell
New-Item -ItemType Directory -Force .pio | Out-Null
$browserProfile = Join-Path (Get-Location) '.pio\browser-test-profile'
Start-Process -FilePath 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' -ArgumentList '--headless=new','--remote-debugging-port=9336',('--user-data-dir="' + $browserProfile + '"'),'about:blank' -WindowStyle Hidden
node test/ui_local_system.mjs
```

Sửa đường dẫn executable nếu Edge được cài ở vị trí khác. Profile này tách khỏi trình duyệt cá nhân; các ảnh kiểm tra nằm trong `.pio/`. Nếu Gateway dùng cổng khác, đặt `PILLBOX_URL` trước khi chạy script.

## 8. Lỗi thường gặp

| Hiện tượng | Xử lý |
|---|---|
| Address already in use | Dừng Gateway cũ, chỉ chạy một tiến trình trên cổng 5000 |
| No module named dotenv | Cài lại requirements bằng Python trong `.venv` |
| Sửa .env nhưng cấu hình không đổi | Khởi động lại; xem `python -m gateway.config`; biến terminal/Docker có ưu tiên cao hơn |
| Không tìm thấy env file | Tạo file đã chọn hoặc kiểm tra --env-file/PILLBOX_ENV_FILE |
| PORT/MQTT_PORT không hợp lệ | Dùng số 1–65535; cờ boolean nhận 0 hoặc 1 |
| Không yêu cầu khóa truy cập | Chưa bật PILLBOX_AUTH_FILE; local_system tự bật |
| Kết nối bị kẹt/trang cũ | Khởi động lại Gateway rồi Ctrl+Shift+R |
| 401 | Sai/thiếu khóa hoặc Gateway dùng file auth khác |
| 403 | Vượt quyền thao tác/hộp được phân công |
| Chỉ thấy ít hộp | Kiểm tra tài khoản; admin thấy đủ 6 hộp |
| Không có nút mô phỏng | Chỉ hiện với local_system và nurse/admin |
| Firmware not found | Build đúng esp32s2_wokwi trước khi Start Simulator |
| Bash lỗi tại & | Dùng đúng lệnh Git Bash, không dùng cú pháp PowerShell |
| Nạp chưa bắt đầu | Kiểm tra online, UTC, phiên/ACK và đúng ngăn |
| TIMEOUT | Chưa nhận ACK trong 60 giây; đọc trạng thái trước khi gửi lại |
| HTTP telemetry trả 404 | Đặt PILLBOX_HTTP_INGEST=1 trong .env rồi khởi động lại |
| Mẫu Postman bị đổi sau vài giây | LocalFleet vẫn phát mẫu; ngắt hộp mô phỏng trước khi thử mẫu thủ công |
| Biểu đồ trống | Kiểm tra hộp, khoảng thời gian và mẫu sensor_ok; chờ chu kỳ chart 10 giây |
| Không nhận email | Mặc định chỉ ghi outbox; cần cấu hình SMTP và chủ động chạy --send |
| Wokwi Terminal không nhập được | Chọn đúng terminal, build lại và Stop/Start simulator |

## 9. Cấu trúc và giới hạn

- `src/`, `include/`: firmware Scheduler, MQTT, NVS, cảm biến/điều khiển.
- `gateway/`: Flask, SQLite, phân quyền, phiên nạp/cảnh báo, CLI tài khoản và local simulator.
- `gateway/config.py`, `gateway/__main__.py`: đọc cấu hình `.env` và lệnh chạy chung; `.env.example`, `.env.local.example`, `.env.wokwi.example` là các mẫu cấu hình.
- `gateway/lab_routes.py`, `rule_engine.py`, `notifications.py`: API lịch sử/HTTP thử nghiệm, timeout ACK, phân mức cảnh báo và outbox/SMTP.
- `gateway/templates/`, `gateway/static/`: HTML/CSS/JS, favicon, ảnh tải sẵn.
- `gateway/data/`: DB và backup, được Git bỏ qua.
- `deploy/`: Docker, Mosquitto TLS/ACL, Caddy HTTPS, cấp khóa.
- `gateway/tests/`, `test/`: kiểm thử API, TLS, local simulator, firmware và giao diện.
- `docs/lab-integration.md`: đối chiếu từng lab, kịch bản API và giới hạn triển khai.

Queue firmware nằm trong RAM, có giới hạn; reset/mất điện có thể mất sự kiện chưa gửi. Chưa có application ACK bền vững cho event; ACK lệnh xử lý riêng. HX711, deep sleep, pin và triển khai VLAN cần nghiệm thu riêng. Cấu hình Docker/TLS sẵn không đồng nghĩa đã kiểm thử trên hạ tầng thật.

Outbox thông báo nằm trong SQLite, khác FIFO sự kiện của ESP32. Nếu tiến trình gửi chết ở trạng thái SENDING, cần kiểm tra log SMTP trước khi xử lý lại; chưa bảo đảm email được phát đúng một lần qua mọi tình huống lỗi.

Ảnh: [Anna Shvets](https://www.pexels.com/photo/photo-medication-pills-on-white-plastic-container-3683074/) và [Polina Tankilevitch](https://www.pexels.com/photo/photo-of-pills-on-container-3873162/) trên Pexels, chỉ dùng minh họa.
