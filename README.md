# Hộp đựng thuốc thông minh — Smart Pill Box

Smart Pill Box là hệ thống IoT dùng ESP32-S2 để nhắc lịch lấy thuốc, ghi nhận thao tác mở ngăn và theo dõi nhiệt độ/độ ẩm. Dữ liệu được gửi qua MQTT đến Gateway Python, lưu bằng SQLite và hiển thị trên Dashboard tiếng Việt. Người chăm sóc có thể xem trạng thái hộp, lịch sử và xác minh mã thuốc trước khi nạp.

Hệ thống có ba ngăn, hỗ trợ nhiều lịch cho một ngăn và tiếp tục nhắc cục bộ khi mất mạng. Đây là đồ án học tập: mở ngăn không chứng minh thuốc đã được uống; tên thuốc và lịch khởi tạo là cấu hình tham khảo, không phải đơn thuốc.

## 1. Chọn cách chạy

| Cách chạy | Cần có | Kết quả |
|---|---|---|
| Chỉ Gateway/Dashboard | Git, Python, trình duyệt | Xem web và cấu hình; chưa có số đo nếu không kết nối thiết bị |
| Đầy đủ bằng Wokwi | Các công cụ trên + VS Code, PlatformIO, Wokwi license cá nhân | Mô phỏng thiết bị và kết nối Dashboard |
| Board thật | Các công cụ trên + Feather ESP32-S2 và linh kiện | Chạy firmware trên phần cứng với cùng Gateway |

Nếu chưa có board, thực hiện **bước 2 → 7** để chạy Wokwi. Nếu chỉ cần xem web, làm đến **bước 5**.

Luồng dữ liệu: **ESP32-S2 → Wi-Fi/MQTT → Gateway Flask → SQLite → Dashboard**.

Luồng điều khiển: **Dashboard/API → Gateway → MQTT → ESP32-S2 → phản hồi trạng thái**.

## 2. Cài công cụ trên máy mới

| Công cụ | Mục đích | Bắt buộc? |
|---|---|---|
| Git | Clone/cập nhật source | Có |
| Python 3.11–3.13 | Chạy Gateway; máy phát triển đã kiểm tra với Python 3.13 | Có |
| Trình duyệt | Xem Dashboard | Có |
| VS Code | Mở project và chạy extension | Khi dùng Wokwi |
| Extension PlatformIO IDE | Build/upload firmware | Khi chạy firmware |
| Extension Wokwi Simulator | Mô phỏng trong VS Code | Khi dùng Wokwi |
| Node.js 22+ và Edge/Chromium | Kiểm thử giao diện tự động | Tùy chọn |
| MSYS2 UCRT64/compiler C++ | Kiểm thử native/host trên Windows | Tùy chọn |

Kiểm tra trong terminal:

~~~text
git --version
python --version
~~~

Nếu Windows không nhận python, thử **py -3 --version** và dùng **py -3** thay python khi tạo môi trường ảo. Linux/macOS thường dùng **python3**.

Không cần SQLite server; Python sử dụng SQLite qua thư viện chuẩn. Không cần Node.js để chạy web thông thường.

Các khối **PowerShell**, **Git Bash Windows** và **Linux/macOS** là các lựa chọn thay thế nhau. Không trộn cú pháp hoặc gõ thêm ký hiệu dấu nhắc terminal.

## 3. Clone đúng nhánh và mở project

Chạy tại thư mục muốn lưu source:

~~~bash
git clone --branch feat/iot-pillbox-care-workflows --single-branch https://github.com/Mei-iwi/Pill_Box.git
cd Pill_Box
git branch --show-current
code .
~~~

Nhánh phải là **feat/iot-pillbox-care-workflows**. Nếu máy chưa nhận lệnh code, mở VS Code → **File → Open Folder** → chọn thư mục Pill_Box vừa clone.

Nếu đã clone từ trước:

~~~bash
cd Pill_Box
git fetch origin
git switch feat/iot-pillbox-care-workflows
git pull --ff-only
~~~

Lưu/commit thay đổi cá nhân trước khi chuyển nhánh hoặc pull. Không clone thêm một Pill_Box bên trong thư mục project đang có.

Mở terminal trong VS Code. Thư mục gốc phải chứa:

~~~text
platformio.ini
wokwi.toml
diagram.json
gateway/
src/
include/
~~~

**Tất cả lệnh bên dưới chạy tại thư mục gốc này**, không chạy từ bên trong gateway/.

## 4. Tạo môi trường Python và cài dependencies

### Windows — PowerShell

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r gateway/requirements.txt
~~~

Không cần kích hoạt .venv. Gọi trực tiếp executable như trên tránh lỗi ExecutionPolicy khi chạy Activate.ps1.

### Windows — Git Bash

~~~bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r gateway/requirements.txt
~~~

### Linux/macOS

~~~bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r gateway/requirements.txt
~~~

Nếu Linux báo thiếu venv, cài gói hỗ trợ venv của bản phân phối rồi chạy lại.

Gateway dùng Flask và paho-mqtt trong [requirements.txt](gateway/requirements.txt). Thư viện firmware do PlatformIO tải riêng khi build.

## 5. Chạy Gateway và mở Dashboard

Mở **terminal 1** tại thư mục gốc, dùng một trong các khối sau.

### Windows — PowerShell

~~~powershell
$env:PILLBOX_DB="gateway/data/pillbox.db"
$env:MQTT_HOST="test.mosquitto.org"
$env:MQTT_PORT="1883"
$env:PILLBOX_MQTT_AUTOSTART="1"
$env:PILLBOX_BIND="127.0.0.1"
$env:PORT="5000"

.\.venv\Scripts\python.exe -m gateway.app
~~~

### Windows — Git Bash

~~~bash
export PILLBOX_DB="gateway/data/pillbox.db"
export MQTT_HOST="test.mosquitto.org"
export MQTT_PORT="1883"
export PILLBOX_MQTT_AUTOSTART="1"
export PILLBOX_BIND="127.0.0.1"
export PORT="5000"

./.venv/Scripts/python.exe -m gateway.app
~~~

### Linux/macOS

~~~bash
export PILLBOX_DB="gateway/data/pillbox.db"
export MQTT_HOST="test.mosquitto.org"
export MQTT_PORT="1883"
export PILLBOX_MQTT_AUTOSTART="1"
export PILLBOX_BIND="127.0.0.1"
export PORT="5000"

./.venv/bin/python -m gateway.app
~~~

Khi thấy **Running on http://127.0.0.1:5000**, mở:

**http://127.0.0.1:5000**

Giữ terminal 1 đang chạy. Nhấn **Ctrl+C** để dừng Gateway.

Lần đầu, Gateway tự tạo thư mục dữ liệu, database, migration và cấu hình hộp/lịch. Nếu chưa chạy Wokwi/board, thiết bị có thể hiện ngoại tuyến; lịch sử hoặc số đo trống là bình thường.

**Chương trình không tự đọc .env.** [gateway/.env.example](gateway/.env.example) chỉ là mẫu tham khảo; đặt biến trong terminal như trên mới có hiệu lực. Hướng dẫn này dùng database pillbox.db. Mỗi terminal mới cần đặt lại biến môi trường.

Nếu bỏ PILLBOX_MQTT_AUTOSTART=1, web vẫn mở nhưng MQTT listener không chạy. Gateway và firmware phải sử dụng cùng broker.

Broker test.mosquitto.org:1883 công khai, không mã hóa. Chỉ dùng mã hồ sơ ẩn danh/dữ liệu thử nghiệm, không gửi thông tin người bệnh thật lên broker.

### Kiểm tra API ở terminal 2

Giữ terminal 1 chạy, mở **terminal 2**.

PowerShell:

~~~powershell
curl.exe http://127.0.0.1:5000/api/devices
curl.exe "http://127.0.0.1:5000/api/devices/PB01/events?page=1&page_size=8"
~~~

Git Bash/Linux/macOS:

~~~bash
curl http://127.0.0.1:5000/api/devices
curl "http://127.0.0.1:5000/api/devices/PB01/events?page=1&page_size=8"
~~~

API đầu trả danh sách hộp. API thứ hai trả items, total, page, page_size và pages. items trống khi chưa có thao tác. API danh sách không có tham số phân trang vẫn trả mảng để giữ tương thích.

## 6. Build firmware cho Wokwi

Cài **PlatformIO IDE** trong VS Code, chờ hoàn tất thiết lập rồi mở lại cửa sổ nếu được yêu cầu. Mở đúng thư mục có [platformio.ini](platformio.ini).

Build trong **terminal 2**, để Gateway ở terminal 1 tiếp tục chạy.

Trong **PlatformIO Core CLI terminal**, hoặc khi pio đã có trong PATH:

~~~bash
pio run -e esp32s2_wokwi
~~~

Nếu terminal không nhận pio, dùng executable do PlatformIO IDE cài:

PowerShell Windows:

~~~powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e esp32s2_wokwi
~~~

Git Bash Windows:

~~~bash
"$HOME/.platformio/penv/Scripts/platformio.exe" run -e esp32s2_wokwi
~~~

Linux/macOS, nếu extension dùng vị trí mặc định:

~~~bash
"$HOME/.platformio/penv/bin/platformio" run -e esp32s2_wokwi
~~~

Lần đầu cần Internet để tải platform, toolchain và thư viện. Build thành công kết thúc bằng **SUCCESS** và tạo:

~~~text
.pio/build/esp32s2_wokwi/firmware.bin
.pio/build/esp32s2_wokwi/firmware.elf
~~~

[wokwi.toml](wokwi.toml) đã trỏ đúng hai file này. .pio không được commit, nên người clone mới phải tự build.

| Environment | Board | Mục đích |
|---|---|---|
| esp32s2_wokwi | ESP32-S2 Saola | Mô phỏng Wokwi |
| adafruit_feather_esp32s2 | Adafruit Feather ESP32-S2 | Board thật |
| native | Máy tính | Kiểm thử Scheduler |

Không thay board production để xử lý lỗi của environment mô phỏng.

## 7. Kích hoạt Wokwi và chạy toàn hệ thống

### 7.1. Tự nhập license sau khi clone

1. Cài extension **Wokwi Simulator**.
2. **F1 → Wokwi: Request a New License**.
3. Đăng nhập/kích hoạt trên trang Wokwi; đồng ý mở lại VS Code khi được hỏi.
4. Nếu extension chưa nhận key: **F1 → Wokwi: Manually Enter License Key**, tự dán key được cấp.
5. Nếu báo hết hạn, yêu cầu license mới, nhập lại rồi dùng **Developer: Reload Window** nếu cần.

License là cấu hình cá nhân, không nằm trong source. Không dán key vào README, diagram.json hoặc wokwi.toml.

**Wokwi VS Code license khác WOKWI_CLI_TOKEN.** Chạy bằng extension như dưới đây không yêu cầu cài CLI hoặc đặt CLI token.

### 7.2. Start Simulator

1. Kiểm tra Gateway ở terminal 1 vẫn chạy.
2. Kiểm tra build esp32s2_wokwi đã SUCCESS.
3. **F1 → Wokwi: Start Simulator**.
4. Chờ thiết bị kết nối Wi-Fi/MQTT và gửi heartbeat.
5. Trên Dashboard chọn **PB01**; trạng thái cập nhật khi Gateway nhận bản tin.

Simulation dùng **Wokwi-GUEST**, mật khẩu trống và broker **test.mosquitto.org:1883**. Không cần Secrets.h để chạy cấu hình Wokwi mặc định.

Heartbeat khoảng 20 giây/lần, môi trường khoảng 60 giây/lần, Dashboard tải lại dữ liệu mỗi 4 giây. Web mở được chưa có nghĩa thiết bị đã kết nối.

### 7.3. Kiểm tra các chức năng

RTC trong [diagram.json](diagram.json) bắt đầu **07:59:50 ngày 10/11/2026**, theo giờ mô phỏng.

| Thao tác | Kết quả cần quan sát |
|---|---|
| Chờ tới 08:00 | LED1/buzzer nhắc, có sự kiện bắt đầu nhắc |
| Bấm ngăn 2 khi đang nhắc ngăn 1 | Mở sai ngăn; ngăn 1 vẫn nhắc |
| Bấm đúng ngăn 1 trong cửa sổ đúng giờ | Xác nhận lấy đúng giờ |
| Thay giá trị DHT22 | Số đo lên Dashboard sau chu kỳ publish tiếp theo |
| Thiết bị → Cập nhật trạng thái | Chờ phản hồi rồi đã áp dụng khi nhận ACK |
| Thiết bị → Tắt âm & đèn nhắc | Tắt cảnh báo hiện tại; không hoàn tất lịch |

Để thử lấy muộn, bắt đầu phiên chưa hoàn tất S1 và không bấm ngăn 1 đúng giờ. Gửi **từng dòng có Enter/newline** trong Serial Monitor:

~~~text
TIME 08:15
TIME 10:00
~~~

- 08:15: S1 có cảnh báo MISSED.
- Sau TIME 10:00, bấm ngăn 1: xác nhận lấy trễ 120 phút.
- Gửi tiếp **TIME 14:00**: S2 vẫn đến lịch đã cài.
- Lịch sử giữ MISSED, nhưng kết quả tổng kết S1 là lấy trễ.
- S3 có lịch 09:00; khi nhảy tới 10:00, ngăn 2 có thể quá hạn độc lập, cần xử lý riêng.

TIME chỉ có trong simulation. Nếu thử lại occurrence đã hoàn tất cùng ngày, dùng phiên mô phỏng sạch hoặc đổi ngày initTime trong diagram.json sang ngày mới. Ledger ngăn ghi nhận lặp; không xóa DB/NVS tùy tiện.

DHT mặc định trong sơ đồ 31,5 °C / 72% RH. Ngưỡng phần mềm 30 °C / 70% cần 3 mẫu gửi liên tiếp; hồi phục cần cả hai dưới 28 °C / 68% đủ3 mẫu. Đây là ngưỡng minh họa, không phải tiêu chuẩn bảo quản chung.

## 8. Sử dụng Dashboard và dữ liệu khởi tạo

- **Tổng quan:** hộp đang chọn, lần nhắc tiếp theo, ba ngăn và môi trường.
- **Lịch nhắc:** lịch đã cấu hình và kết quả từng lần nhắc.
- **Lịch sử:** mở ngăn, cảnh báo và số đo gần đây.
- **Nạp thuốc:** xác minh mã, xác nhận và xem lịch sử nạp.
- **Thiết bị:** trạng thái, hàng đợi và các nút điều khiển.
- **Tài khoản:** nhập khóa truy cập khi máy chủ bật xác thực.

Chọn hộp tại submenu. Các danh sách dài có phân trang; header/submenu cố định khi cuộn.

| Hộp | Hồ sơ | Ngăn | Mã | Tên hiển thị | Lịch |
|---|---|---:|---|---|---|
| PB01 | P001 — Hồ sơ 01 | 1 | MED001 | Vitamin C | S1 08:00, S2 14:00 |
| PB01 | P001 — Hồ sơ 01 | 2 | MED002 | Vitamin D3 | S3 09:00 |
| PB01 | P001 — Hồ sơ 01 | 3 | MED003 | Canxi | S4 20:00 |
| PB02 | P002 — Hồ sơ 02 | 1 | MED004 | Vitamin B12 | S5 07:30 |

Đây là cấu hình khởi tạo, không phải hồ sơ người bệnh/chỉ định dùng thuốc. Không tạo sẵn lịch sử lấy hoặc số đo giả. **Firmware/mạch hiện tại là PB01; PB02 chỉ có cấu hình phía Gateway**, không tự phát bản tin.

Lịch tiếp theo trên web tính theo thời gian hiện tại tại Việt Nam; khi dùng TIME để nhảy giờ mô phỏng, đối chiếu event/occurrence của thiết bị để kiểm thử.

### Nạp thuốc hai bước

1. Chọn **PB01**, vào **Nạp thuốc**.
2. Nhập mã người chăm sóc, hồ sơ **P001**, ngăn **1**.
3. Nhập/quét **MED001** ở ô mã trên bao bì.
4. **Xác minh mã**; khi phù hợp, nút Xác nhận nạp được mở.
5. **Xác nhận nạp** để hoàn tất và ghi lịch sử.

MED002 ở ngăn 1 PB01 bị từ chối vì sai mã. PB02 nhưng dùng P001 bị từ chối vì sai hồ sơ/hộp. Token có hạn 5 phút, dùng một lần; đổi form, hết hạn hoặc thay assignment thì phải xác minh lại.

Khi bật auth, mã người chăm sóc lấy từ tài khoản phía máy chủ. Xác minh mã bao bì không nhận diện từng viên thuốc trong ngăn.

## 9. Chạy trên Adafruit Feather ESP32-S2 thật

Bỏ qua mục này nếu dùng Wokwi.

### 9.1. Tạo cấu hình cá nhân

PowerShell:

~~~powershell
Copy-Item include/config/Secrets.example.h include/config/Secrets.h
~~~

Git Bash/Linux/macOS:

~~~bash
cp include/config/Secrets.example.h include/config/Secrets.h
~~~

Nếu đã có Secrets.h, chỉnh file hiện có, không sao chép đè. Tự điền:

~~~cpp
#pragma once
#define PILLBOX_WIFI_SSID "TEN_WIFI_CUA_BAN"
#define PILLBOX_WIFI_PASSWORD "MAT_KHAU_WIFI_CUA_BAN"
#define PILLBOX_MQTT_HOST "test.mosquitto.org"
#define PILLBOX_MQTT_PORT 1883
#define PILLBOX_MQTT_USER ""
#define PILLBOX_MQTT_PASSWORD ""
~~~

Firmware và Gateway phải cùng broker. Theo hướng dẫn này, giữ credential trống và chỉ dùng dữ liệu ẩn danh. Gateway hiện chưa cấu hình tài khoản/TLS MQTT qua biến môi trường.

### 9.2. Đấu nối và đặt RTC

GPIO phần mềm ở [include/config/Pins.h](include/config/Pins.h):

| Linh kiện | GPIO/giao tiếp |
|---|---|
| RTC DS3231 | SDA 3, SCL 4 |
| Nút/reed switch ngăn 1/2/3 | GPIO 5/6/7 về GND, INPUT_PULLUP |
| LED ngăn 1/2/3 | GPIO 8/9/10, điện trở nối tiếp phù hợp |
| Buzzer active | GPIO 11 qua driver phù hợp tải |
| DHT22 | GPIO 12 |

Đối chiếu chân header đúng revision board trước đấu dây. GPIO là 3.3 V; không đưa trực tiếp tín hiệu 5 V vào GPIO. Buzzer tải 5 V cần mạch điều khiển phù hợp.

Đặt **DS3231 đúng giờ Việt Nam** bằng công cụ/sketch thiết lập RTC trước khi chạy. Firmware chưa có API chỉnh RTC thật; RTC mất nguồn/chưa hợp lệ sẽ dùng fallback thời gian chưa đồng bộ. DS1307 của Wokwi không thay thế DS3231 trong cấu hình production.

### 9.3. Upload và Serial

Dùng cáp USB có truyền dữ liệu. Trong PlatformIO CLI terminal:

~~~bash
pio run -e adafruit_feather_esp32s2 -t upload
pio device monitor -e adafruit_feather_esp32s2
~~~

Nếu thiếu pio, dùng executable ở bước 6 và thay tên environment. Serial 115200. Chạy Gateway theo bước 5, chờ PB01 online rồi kiểm tra thiết bị. Board thật không có lệnh TIME của simulation.

## 10. Xác thực và phân quyền — tùy chọn

Mặc định Gateway chỉ bind localhost, chưa yêu cầu khóa. Để dùng tài khoản riêng:

1. Sao chép [gateway/auth.example.json](gateway/auth.example.json) thành **gateway/auth.local.json**.
2. Tạo khóa ngẫu nhiên khác nhau cho từng tài khoản.
3. Thay toàn bộ tên key REPLACE_WITH... trong file local.
4. Chỉnh actor_id, role và devices theo phạm vi sử dụng.

PowerShell:

~~~powershell
Copy-Item gateway/auth.example.json gateway/auth.local.json
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
~~~

Git Bash Windows:

~~~bash
cp gateway/auth.example.json gateway/auth.local.json
./.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
~~~

Linux/macOS dùng **./.venv/bin/python** để tạo khóa. Tự chép khóa vào file local và lưu riêng. Máy chủ từ chối placeholder chưa thay.

| Role | Quyền |
|---|---|
| family | Xem hộp được gán; yêu cầu trạng thái/tắt nhắc |
| nurse | Xem hộp được phân công; verify/confirm và xem lịch sử nạp |
| admin | Tất cả hộp; gửi cập nhật lịch |

Dừng Gateway bằng Ctrl+C. Tại terminal đã đặt biến ở bước 5, bổ sung:

PowerShell:

~~~powershell
$env:PILLBOX_AUTH_FILE="gateway/auth.local.json"
.\.venv\Scripts\python.exe -m gateway.app
~~~

Git Bash Windows:

~~~bash
export PILLBOX_AUTH_FILE="gateway/auth.local.json"
./.venv/Scripts/python.exe -m gateway.app
~~~

Linux/macOS dùng cùng export, rồi chạy **./.venv/bin/python -m gateway.app**.

Trên Dashboard: **Tài khoản → nhập khóa → Kết nối**. Gọi API trực tiếp cần header **Authorization: Bearer KHOA_CUA_BAN**.

Tắt auth cục bộ: dừng Gateway, bỏ biến rồi chạy lại.

~~~powershell
Remove-Item Env:PILLBOX_AUTH_FILE -ErrorAction SilentlyContinue
~~~

Bash:

~~~bash
unset PILLBOX_AUTH_FILE
~~~

Đây là bearer auth đơn giản, chưa có JWT/password login hoặc HTTPS. Không mở Gateway chưa xác thực ra Internet.

## 11. Dữ liệu, backup và cập nhật sau pull

### File cá nhân không có trong Git

| File/thông tin | Sau clone cần làm gì? |
|---|---|
| .venv/ | Tự tạo và cài Python dependencies |
| .pio/ | Tự build bằng PlatformIO |
| include/config/Secrets.h | Tự tạo nếu dùng board thật |
| Wokwi license/CLI token | Tự kích hoạt hoặc nhập trên máy |
| gateway/auth.local.json | Tự tạo nếu bật auth |
| gateway/data/pillbox.db | Gateway tự tạo lần đầu |
| gateway/data/backups/ | Chỉ có sau khi reset trên máy đó |

Không dùng git add -f để đưa key, mật khẩu, DB hoặc backup vào repository.

### Sau mỗi lần pull

1. Dừng Gateway và simulator.
2. **git pull --ff-only**.
3. Cài lại dependencies theo bước 4 nếu requirements thay đổi.
4. Build lại firmware.
5. Đặt biến môi trường, chạy Gateway rồi Start Simulator.
6. **Ctrl+Shift+R** trên Dashboard để tránh JS/CSS cũ.

Database cá nhân không được thay bằng DB từ Git. Migration giữ dữ liệu cũ; seed dùng INSERT OR IGNORE nên không tự ghi đè tên/lịch đã có.

### Tạo lại dữ liệu — thao tác có xóa bản ghi

Chỉ dùng khi chủ động muốn xóa dữ liệu cũ. **Dừng Gateway trước**. Lệnh tạo backup đầy đủ rồi reset lịch sử/cấu hình trong DB đã chọn.

PowerShell:

~~~powershell
.\.venv\Scripts\python.exe -m gateway.reset_data --db gateway/data/pillbox.db
~~~

Git Bash Windows:

~~~bash
./.venv/Scripts/python.exe -m gateway.reset_data --db gateway/data/pillbox.db
~~~

Linux/macOS thay executable bằng **./.venv/bin/python**.

Backup ở **gateway/data/backups/<thời điểm>/pillbox.db**. Khôi phục bằng cách dừng Gateway rồi chép file backup đúng tên đè lên DB tương ứng. Reset DB không xóa ledger NVS của ESP32.

## 12. Kiểm thử — tùy chọn

Không cần chạy các kiểm thử này để mở Dashboard.

### Gateway, phân trang, auth và reset

Mở terminal kiểm thử riêng. Không bật auth/MQTT autostart cho app factory trong unit tests.

PowerShell:

~~~powershell
$env:PILLBOX_MQTT_AUTOSTART="0"
Remove-Item Env:PILLBOX_AUTH_FILE -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m unittest discover -s gateway/tests -t . -v
~~~

Git Bash Windows:

~~~bash
export PILLBOX_MQTT_AUTOSTART="0"
unset PILLBOX_AUTH_FILE
./.venv/Scripts/python.exe -m unittest discover -s gateway/tests -t . -v
~~~

Linux/macOS dùng **./.venv/bin/python**. Hiện có 33 test, sử dụng DB tạm.

### MQTT hai chiều qua broker thật

Tại terminal kiểm thử chưa bật auth/autostart, PowerShell:

~~~powershell
.\.venv\Scripts\python.exe -m gateway.tests.mqtt_e2e
~~~

Git Bash dùng **./.venv/Scripts/python.exe**, Linux/macOS dùng **./.venv/bin/python**. Script dùng PBTEST ngẫu nhiên và DB tạm, không ghi vào Dashboard cá nhân. Đây là MQTT device tổng hợp, không chứng minh GPIO/queue firmware đã chạy trên Wokwi/board.

### Native và host C++

Trong PlatformIO CLI terminal:

~~~bash
pio test -e native
~~~

Nếu Windows đã cài MSYS2 UCRT64 nhưng compiler thiếu DLL:

~~~powershell
$env:PATH="C:\msys64\ucrt64\bin;" + $env:PATH
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" test -e native
~~~

Host harness bổ sung các ca lấy muộn/reboot/overlap/FIFO/môi trường. Chạy trong terminal có g++:

~~~powershell
New-Item -ItemType Directory -Force .pio | Out-Null
g++ -std=c++11 -Iinclude test/host_scheduler/main.cpp src/app/Scheduler.cpp -o .pio/host_scheduler.exe
if ($LASTEXITCODE -eq 0) { & .\.pio\host_scheduler.exe }
~~~

MSYS2/native không phải điều kiện chạy Gateway hoặc build firmware ESP32 bằng PlatformIO.

### Giao diện desktop/mobile

Cần Node.js 22+, Gateway localhost đang chạy **chưa bật auth**, cấu hình PB01/PB02 và Edge/Chromium với profile riêng.

PowerShell, với Edge tại vị trí mặc định:

~~~powershell
New-Item -ItemType Directory -Force .pio | Out-Null
$browserProfile=Join-Path (Get-Location).Path ".pio\ui-preview-profile"
$profileArgument='--user-data-dir="' + $browserProfile + '"'
$browserArguments=@(
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--remote-debugging-port=9334",
  $profileArgument,
  "about:blank"
)
Start-Process -FilePath "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList $browserArguments -WindowStyle Hidden
node test/ui_dashboard.mjs
~~~

Sửa đường dẫn Edge nếu cài ở nơi khác. Script kiểm menu cố định, ảnh/favicon, đổi hộp, phân trang và trạng thái form. POST refill/GET phân trang thử được mock riêng, không tạo audit giả vào DB đang chạy. Ảnh kết quả tại **.pio/ui-desktop.png** và **.pio/ui-mobile.png**.

Đóng riêng browser kiểm thử ở CDP9334 bằng lệnh sau; không dùng với profile trình duyệt cá nhân:

~~~powershell
node --input-type=module -e "const info=await(await fetch('http://127.0.0.1:9334/json/version')).json();const socket=new WebSocket(info.webSocketDebuggerUrl);socket.addEventListener('open',()=>socket.send(JSON.stringify({id:1,method:'Browser.close'})));"
~~~

Các kiểm tra đã thực thi trên máy phát triển: hai build PASS, Gateway 33/33 PASS, native 4/4 PASS, host harness PASS, synthetic broker và browser smoke PASS. Không dùng các kết quả này thay cho kiểm GPIO, NVS/mất nguồn, offline/reconnect và board thật trên máy mới.

## 13. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| No module named flask/paho | Cài requirements bằng đúng Python trong .venv, chạy Gateway bằng executable đó |
| No module named gateway | Quay về thư mục gốc chứa platformio.ini, không chạy từ gateway/ |
| PowerShell chặn Activate.ps1 | Không cần đổi ExecutionPolicy; gọi trực tiếp .venv/Scripts/python.exe |
| Git Bash báo syntax near & | Dùng nhầm cú pháp PowerShell; chuyển sang khối Git Bash |
| Không nhận pio | Dùng PlatformIO CLI terminal hoặc executable ở bước 6; chờ extension cài xong |
| Wokwi báo firmware.bin not found | Mở đúng workspace và build esp32s2_wokwi trước Start Simulator |
| Wokwi license expired | Yêu cầu license mới, nhập thủ công rồi reload VS Code |
| Web mở nhưng PB01 offline | Kiểm tra thiết bị, mạng, MQTT_AUTOSTART và cùng broker; chờ heartbeat |
| PB01 chập chờn khi nhiều người chạy | Firmware dùng cùng client ID/topic PB01 trên public broker; dừng bản trùng hoặc dùng broker riêng đã cấu hình đồng bộ |
| Sửa Secrets.h nhưng broker simulation không đổi | Simulation lấy host ở nhánh PILLBOX_SIMULATION của AppConfig.h; nếu đổi phải sửa đúng nhánh và build lại |
| Chưa có DHT | Chờ chu kỳ publish khoảng 60s; kiểm tra DHT và topic environment |
| Giao diện cũ sau pull | Ctrl+Shift+R; nếu thay HTML, dừng/chạy lại Gateway |
| API 401/403 | Kiểm tra khóa trong Tài khoản, role và devices trong auth.local.json |
| Verify mismatch | Đối chiếu hộp/hồ sơ/ngăn/mã bao bì; không sửa mã dự kiến để ép confirm |
| HTTP 503 khi gửi command | Gateway chưa kết nối broker; kiểm tra mạng và MQTT_AUTOSTART |
| Cổng5000 đã bị dùng | Dừng đúng Gateway cũ hoặc đặt PORT=5001 rồi mở URL cổng mới |
| RTC thật sai/mất nguồn | Đặt lại DS3231; firmware không tự đồng bộ RTC từ mạng |

Không dùng git reset --hard, xóa project hoặc xóa DB để xử lý lỗi cài đặt thông thường.

## 14. Cấu trúc và giới hạn

~~~text
Pill_Box/
├── README.md
├── platformio.ini
├── diagram.json
├── wokwi.toml
├── include/
│   ├── app/                 Scheduler, AppController
│   ├── communication/       MQTT, Wi-Fi
│   ├── config/              Pins, AppConfig, Secrets.example.h
│   ├── domain/              EventBuffer, StorageMonitor, model
│   ├── drivers/             RTC, nút, LED, buzzer, DHT
│   └── storage/             NVS
├── src/                     Triển khai firmware và main.cpp
├── gateway/
│   ├── app.py               Flask API và trang web
│   ├── mqtt_service.py      MQTT/payload
│   ├── db.py, schema.py     Migration, seed, SQLite
│   ├── auth.py              Bearer identity/scope
│   ├── reset_data.py        Backup/reset DB
│   ├── requirements.txt
│   ├── auth.example.json
│   ├── templates/           HTML
│   ├── static/              CSS, JS, favicon, ảnh
│   └── tests/               Gateway/broker tests
└── test/                    Native, host, browser tests
~~~

- Event có identity theo boot/seq; Gateway chống trùng, tách log cảnh báo khỏi kết quả occurrence.
- Queue RAM giữ 16 sự kiện chờ và tối đa 1 bản đang gửi; đầy sẽ bỏ bản chờ cũ nhất và tăng bộ đếm. Reset/mất điện có thể mất dữ liệu RAM.
- Publish thành công chưa chứng minh SQLite đã commit; chưa có application ACK cho event. Command có ACK riêng.
- Ledger NVS hạn chế completion lặp, không phải durable event outbox.
- Chưa hỗ trợ lấy trễ xuyên ngày địa phương; firmware PB01 có 4 lịch cấu hình sẵn.
- HX711 mới có interface, chưa có driver đọc/cân/hiệu chuẩn. Deep Sleep và thời lượng pin chưa được kiểm chứng.
- HTTP/MQTT 1883 dùng cho môi trường thử nghiệm cục bộ; chưa có TLS/ACL production.

Ảnh giao diện đã tải sẵn, không cần tải lại khi chạy: [Anna Shvets — Pexels](https://www.pexels.com/photo/photo-medication-pills-on-white-plastic-container-3683074/) và [Polina Tankilevitch — Pexels](https://www.pexels.com/photo/photo-of-pills-on-container-3873162/), theo [Pexels License](https://www.pexels.com/license/). Ảnh minh họa không nhận diện viên thuốc trong từng ngăn.
