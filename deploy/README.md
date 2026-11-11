# Triển khai hộp thuốc theo định hướng mẫu

Mẫu trong **Hướng dẫn - đề tài IoT.pdf** mô tả hệ thống giám sát cửa kho. Phần này áp dụng sáu nhóm nội dung của mẫu cho **hộp thuốc trong cơ sở chăm sóc**, giữ Wokwi làm môi trường kiểm thử. Camera, LoRa và NVR của ví dụ logistics không được coi là linh kiện đã có của hộp thuốc.

## 1. Bài toán cụ thể

Mỗi hộp thuộc một hồ sơ, có ba ngăn và nhiều lịch. Người chăm sóc cần xem các lần chưa lấy, mở sai ngăn và lỗi bảo quản tập trung. Phải phân biệt thao tác lấy thuốc với thao tác mở để nạp; việc nạp không được hoàn tất nhầm một lần nhắc. Danh sách hộp và cảnh báo bị giới hạn theo phân công family/nurse/admin.

Các trạng thái nghiệp vụ vẫn là **lấy đúng giờ, lấy trễ, chưa ghi nhận lấy**. Nút mở ngăn chưa chứng minh đã uống hoặc lấy đủ số viên. Chưa có đánh giá tải 10–50 hộp hoặc chứng nhận dùng lâm sàng.

## 2. Thiết bị và phương án lắp thật

| Thành phần | Wokwi hiện tại | Khi lắp thật |
|---|---|---|
| ESP32-S2 | Board mô phỏng, ID PB01 | ID và tài khoản riêng cho mỗi board |
| Mở ngăn | Ba pushbutton, chống dội 35 ms | Công tắc nắp hoặc reed switch phù hợp cơ khí; kiểm mức tác động trước nối |
| Thời gian | DS1307 cho lịch; SNTP UTC cho cấp phép/TLS | DS3231 giữ lịch khi mất mạng; NTP tin cậy cho thời hạn cấp phép |
| Môi trường | DHT22, ba mẫu mới và hysteresis | Kiểm sai số và đối chiếu điều kiện của thuốc cụ thể |
| Báo tại chỗ | Ba LED và piezo | Điện trở/driver tải, nguồn lọc, bảo vệ và vỏ hộp phù hợp |
| Khối lượng | Chưa triển khai | Loadcell/HX711 cần cơ khí và hiệu chuẩn riêng |

Giữ GPIO trong **include/config/Pins.h**. UART mô phỏng TX43/RX44 nối chéo Serial Monitor. Nút hiện tạo sự kiện mở, chưa đo liên tục trạng thái nắp đang đóng hay mở. Các yêu cầu nguồn dự phòng, chống nhiễu điện và độ bền cơ khí phải kiểm chứng trên phần cứng, không thể kết luận bằng Wokwi.

## 3. Kiến trúc mạng và bảo mật

~~~text
Edge: ESP32-S2 + RTC + nút + DHT22 + LED/buzzer
                | Wi-Fi / MQTT có TLS ở profile care
                v
Gateway/Network: broker Mosquitto, ACL riêng từng hộp
                |
Server/Application: Flask/Waitress + SQLite + Dashboard qua HTTPS
~~~

Ba vùng triển khai trên tương ứng bốn tầng logic: cảm nhận, truyền thông, xử lý dữ liệu và ứng dụng. Gateway và ứng dụng có thể cùng máy. Hai Docker network chỉ phân đoạn container; **không tự tạo VLAN trên mạng cơ sở**.

Phương án mạng để quản trị viên áp dụng trên router/switch:

| Vùng | Ví dụ mạng | Luồng cho phép |
|---|---|---|
| Thiết bị IoT | VLAN 10, 10.32.10.0/24 | Tới broker TCP 8883, DNS và NTP được chỉ định |
| Người chăm sóc | VLAN 20, 10.32.20.0/24 | Tới máy chủ HTTPS |
| Máy chủ | VLAN 30, 10.32.30.0/24 | Broker và Gateway trao đổi nội bộ, DB lưu trên máy chủ |

Chặn thiết bị truy cập ngang vào máy nhân viên; không mở cổng SQLite qua mạng. Đây là bản thiết kế firewall/VLAN, chưa được script áp dụng lên router của người dùng.

Trong profile **care**, Gateway yêu cầu auth và MQTT có TLS/tài khoản; bản tin từ hộp chưa đăng ký bị từ chối. Firmware dùng CA và kiểm tên máy chủ, không gọi setInsecure. Hộp chỉ ghi các topic của chính mình và chỉ đọc command của chính mình. Gateway chỉ đọc telemetry và ghi command. Các event vẫn publish QoS 0; cấu hình TLS không biến FIFO RAM thành lưu trữ bền vững.

## 4. Cài đặt và cấu hình

### Chạy Wokwi như hiện tại

Làm theo README gốc. Chưa cần Docker hoặc thay broker công khai để thử logic. Giữ ID PB01, không chạy hai simulator cùng ID. Bản mô phỏng không được dùng dữ liệu bệnh nhân thật trên broker công khai.

### Chuẩn bị broker riêng và Gateway

Cần **Docker Desktop đang chạy**, **OpenSSL trên PATH** và PowerShell. Từ thư mục repository:

~~~powershell
.\deploy\prepare.ps1 -BrokerHost localhost -DeviceIds PB01
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml up -d --build
docker compose -f deploy/compose.yaml logs -f gateway broker
~~~

prepare.ps1 tạo CA/chứng thư máy chủ, mật khẩu ngẫu nhiên và token theo vai trò trong **deploy/runtime/**. Mật khẩu broker được băm bằng mosquitto_passwd của image chính thức. Thư mục này bị gitignore; script từ chối ghi đè nếu đã tồn tại. Sao lưu/quản lý khóa trong vùng truy cập riêng; không gửi thư mục runtime hoặc CA private key cho người dùng web. Container broker chỉ nhận chứng thư công khai và khóa máy chủ, không nhận khóa ký CA.

Web tại **https://localhost:8443**, broker tại **localhost:8883**. Gateway không được publish trực tiếp cổng 5000 ra host. Caddy dùng CA nội bộ; xuất root để kiểm tra và cài vào kho tin cậy của máy sử dụng theo quy trình quản trị:

~~~powershell
docker compose -f deploy/compose.yaml cp web:/data/caddy/pki/authorities/local/root.crt deploy/runtime/web-root.crt
~~~

Đọc token của vai trò cần dùng từ **deploy/runtime/auth.local.json**, nhập vào mục **Tài khoản** trên web. Không đưa token vào URL. Khi triển khai nhiều máy, đổi tên miền/Caddyfile và chứng thư phù hợp; cấu hình bind cụ thể qua **PILLBOX_BROKER_BIND** và **PILLBOX_WEB_BIND**. Mặc định chỉ bind loopback, không tự mở firewall.

Chép **deploy/runtime/device-PB01.h** thành **include/config/Secrets.h**, điền Wi-Fi cho board thật rồi build. Header chứa CA công khai và mật khẩu riêng của hộp; không commit. Với Wokwi, cần **Private IoT Gateway** để truy cập broker trên máy/LAN hoặc dùng tên miền TLS có thể truy cập từ simulator. Nếu dùng host.wokwi.internal, đổi MQTT_HOST sang tên này; chứng thư do script tạo đã có SAN tương ứng. Chỉ thay host không làm broker localhost tự truy cập được từ Wokwi cloud. Tham khảo [mạng ESP32 của Wokwi](https://docs.wokwi.com/guides/esp32-wifi).

Nếu chạy Gateway ngoài Docker, tự đặt MQTT_HOST, MQTT_PORT=8883, MQTT_TLS=1, MQTT_CA_FILE, MQTT_USER, MQTT_PASSWORD, PILLBOX_AUTH_FILE và PILLBOX_DEPLOYMENT=care. Cặp MQTT_CERT_FILE/MQTT_KEY_FILE là tùy chọn khi broker yêu cầu chứng thư client. Không có chế độ bỏ kiểm CA/tên máy chủ. Đặt HTTPS trước Gateway khi truy cập từ xa.

### Đăng ký hộp mới

Ví dụ tạo **PB03** với lịch PB03_S1…PB03_S4, không sửa PB01 hoặc PB02:

~~~powershell
python -m gateway.provision --db gateway/data/pillbox.db --device PB03 --patient P003 --label "Ho so 03"
~~~

Với DB trong Docker:

~~~powershell
docker compose -f deploy/compose.yaml exec gateway python -m gateway.provision --db /data/pillbox.db --device PB03 --patient P003 --label "Ho so 03"
~~~

Provision chỉ tạo cấu hình, không tạo lịch sử hoặc số đo. ID đã tồn tại sẽ bị từ chối để giữ hồ sơ cũ. Lịch/thuốc khởi tạo cần được điều chỉnh theo phân công trước sử dụng thực tế. Thêm tài khoản/ACL PB03 trên broker và PB03 vào danh sách devices của tài khoản API; các bước này độc lập. Để chuẩn bị nhiều tài khoản từ đầu, truyền **-DeviceIds PB01,PB03** khi runtime chưa tồn tại.

Firmware hộp mới cần **PILLBOX_DEVICE_ID="PB03"** và **PILLBOX_SCHEDULE_PREFIX="PB03_"**, khớp DB. Không đổi ID qua UI hoặc cho hai board dùng cùng tài khoản. NVS của PB01 giữ namespace cũ; hộp có ID khác dùng namespace riêng. Mỗi hộp mới cần được build/nạp và kiểm thử riêng, không suy từ cấu hình DB rằng đã có board đang chạy.

## 5. Quy trình vận hành theo lịch chăm sóc

1. Đầu ca: đăng nhập đúng vai trò, kiểm hộp được phân công, kết nối và đồng bộ giờ UTC; đối chiếu lịch trên thiết bị với Gateway. Chỉ coi thay lịch thành công khi có ACK APPLIED.
2. Đến giờ: thiết bị nhắc theo RTC. Mở đúng ngăn phân loại ON_TIME/LATE; MISSED giữ trong lịch sử dù sau đó lấy muộn. Không dùng CLEAR_ALERT để xác nhận lấy thuốc.
3. Nạp: **Xác minh mã → Bắt đầu nạp → chờ ACK → mở đúng ngăn → Xác nhận nạp**. Phiên gắn người chăm sóc, hộp, ngăn, boot_id và hết hạn tối đa 5 phút theo UTC, độc lập lệnh TIME của mô phỏng. Chưa đồng bộ UTC thì không cấp phiên.
4. Mở trong phiên: firmware phát **REFILL_OPEN**, không gọi recordSlotOpen và không tạo TAKEN. Không phát thêm cảnh báo mở ngoài lịch. Lịch nhắc đang tồn tại và cảnh báo ngăn khác vẫn được giữ.
5. Kết thúc: xác nhận nạp gửi END_REFILL; có thể bấm **Kết thúc phiên** khi hủy. Nếu mất mạng, cửa sổ tự hết hạn. UI đổi thông tin sẽ yêu cầu kết thúc phiên cũ và xác minh lại; phải kiểm tra ACK hoặc đợi hết hạn nếu mạng lỗi.
6. Sự cố: mở sai/ngoài lịch phát cảnh báo tại hộp khoảng 10 giây và xuất hiện trong danh sách cảnh báo tập trung. **Đã kiểm tra** đóng cảnh báo thao tác; **Tiếp nhận** ghi người xử lý cho MISSED/môi trường. Lấy muộn hợp lệ hoặc môi trường hồi phục sẽ tự giải quyết điều kiện tương ứng. Tắt âm chỉ tác động thiết bị, không xóa dấu vết trên Gateway.

Trong profile care, API confirm bắt buộc có mở đúng ngăn đã được Gateway ghi nhận. Profile Wokwi/local giữ API xác minh–xác nhận cũ để tương thích; giao diện mới luôn đi qua phiên nạp. ACK phiên và event mở phải cùng boot_id; event nhận chậm được đối chiếu uptime với khoảng được cấp, tránh mất audit chỉ vì END tới trước event.

## 6. Kịch bản kiểm thử theo mẫu

| Ca | Thao tác | Kết quả cần đối chiếu |
|---|---|---|
| Lấy hợp lệ | Ngày mới, TIME 08:00, bấm Slot 1 | ON_TIME của S1, không cảnh báo mở sai |
| Mở bất thường | S1 đang nhắc, bấm Slot 2 | WRONG_SLOT, còi/LED ngắn hạn, cảnh báo có ID trên web |
| Nạp hợp lệ | Xác minh PB01/P001/1/MED001, bắt đầu nạp, chờ ACK, bấm Slot 1, xác nhận | REFILL_OPEN; occurrence lấy thuốc không đổi; audit CONFIRMED |
| Sai ngăn khi nạp | Được cấp ngăn 1 nhưng bấm ngăn 2 | Không được xem là nạp hợp lệ; cảnh báo theo lịch/ngăn thực tế |
| Hết hạn/đổi phiên | Dùng lại command/session sau thời hạn hoặc reboot | Không mở lại cửa sổ; cần xác minh/cấp phiên mới |
| Bảo quản | DHT22 32°C/75%, sau đó 25°C/50% | Ba mẫu mới cảnh báo/hồi phục; không nhấp nháy do mẫu cache |
| Phân quyền | Family gọi authorize/ack; nurse truy cập hộp khác | Từ chối, không lộ dữ liệu hộp ngoài phân công |
| TLS | CA/tên máy chủ sai hoặc thiếu chứng thư | Từ chối kết nối, không tự hạ xuống TCP |
| Mất mạng | Ngắt MQTT, thao tác, nối lại | Nhắc cục bộ, gửi FIFO trong giới hạn; không khẳng định giữ được FIFO sau mất điện |

Các unit test dùng DB tạm; TLS socket test dùng chứng thư tạm và endpoint cục bộ; mqtt_e2e dùng PBTEST tổng hợp qua broker. Các ca đó không thay cho kiểm thử GPIO Wokwi/board thật hoặc xác nhận Mosquitto ACL chạy trong Docker. Ghi lại event_id, command_id, session_id và ảnh/log khi thử simulator. Docker phải được chạy và kiểm quyền topic thực tế trước khi nghiệm thu profile care.

Tài liệu kỹ thuật: [Paho TLS](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html), [Mosquitto authentication/ACL/TLS](https://mosquitto.org/man/mosquitto-conf-5.html), [ESP32 WiFiClientSecure](https://github.com/espressif/arduino-esp32/tree/2.0.17/libraries/WiFiClientSecure).
