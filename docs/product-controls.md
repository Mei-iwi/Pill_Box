# Hộp thuốc: điều khiển, màn hình và đầu đọc mã

## Phiên bản ngăn kéo và admin local

Tổng quan chỉ có hộp 3D với ba ngăn kéo phía trước. Màn hình, cửa đọc barcode và các nút SCAN / ADD / MUTE nằm trên mặt hộp. Bấm tay kéo để mở/đóng; các nút nhỏ phía dưới hỗ trợ bàn phím và điện thoại. Thông số gateway và hoạt động gần đây đã chuyển sang Thiết bị.

SCAN / ADD trong mô hình mở bảng thử thao tác. Mã bao bì điền sẵn lấy từ thuốc đã gán trong database để thử quy trình. Có thể nhập mã khác để thử nhận diện hoặc lỗi sai thuốc. “Đưa bao bì vào máy quét” minh họa chuyển bao bì đến cửa đọc, gọi API tra cứu danh mục và kiểm tra thuốc khớp ngăn. Mở ngăn và quét đúng mới thêm được 1–12 viên vào mô hình. Số viên thuộc bộ nhớ trình duyệt, bị xóa khi đổi hộp hoặc tải lại trang; không ghi tồn kho hay tự cấp phép nạp thiết bị. “Quét bằng camera” mở luồng camera thật ở mục Nạp thuốc. Nhắc thuốc, cảnh báo và MUTE trên mô hình chỉ đổi đèn/màn hình mô phỏng; điều khiển thiết bị thật ở mục Thiết bị.

`python -m gateway` ở local và bind loopback mặc định tự dùng ADMIN01, không cần nhập khóa API. Đặt `PILLBOX_LOCAL_LOGIN=1` trong `gateway/.env` để bật lại đăng nhập. Tự vào admin chỉ áp dụng cho yêu cầu từ loopback, không bật khi bind ra mạng hoặc deployment care. Chế độ MQTT dùng cấu hình xác thực hiện có.

Kiểm tra: 100 tests backend đạt, có kiểm tra admin local không khóa, yêu cầu khóa từ địa chỉ mạng và giữ role tài khoản mạng. `test/ui_product.mjs` kiểm tra click nút SCAN trực tiếp trong canvas, Tổng quan chỉ có sản phẩm, kéo ngăn, bắt buộc scan trước khi thêm viên, từ chối thuốc sai, cảnh báo/tắt báo và width 320/390/768/1024/1440. Browser smoke cho luồng nạp và phân trang cũng đạt sau khi chuyển dữ liệu sang Thiết bị. Các phần bên dưới mô tả bản thiết kế trước ngăn kéo; hành vi hiện tại theo mục này.

Design Taste gate mới nhất: `GATE: OPEN`, vòng 3, còn 20 findings và 16 warnings; đây không phải kết quả PASS. Không có waiver. Findings gồm shader-lint (2) trong Three.js, spill (3) của nút quanh canvas, overlap-text (1) của nhãn phủ canvas, button-styles (2), copy-headline (1), copy-actions (1), motion-layer (1), moment-none (1), section-height (1), one-section (1), container-edges (5) và container (1). Kiểm thử responsive của ứng dụng không phát hiện tràn ngang ở các width nêu trên. Các ảnh xác minh mới là `.pio/ui-drawer-closed.png`, `.pio/ui-drawer-filled.png`, `.pio/ui-drawer-alarm.png`, `.pio/ui-drawer-mobile.png`.

## Dashboard

- Kéo hộp để xoay, cuộn để phóng to. Bấm nắp để đóng/mở phần mô hình; nút số 1–3 trên thân chọn ngăn.
- SCAN mở luồng camera/nhập mã. REFILL mở nạp ngăn đang chọn. MUTE gửi CLEAR_ALERT tới thiết bị và chờ phản hồi.
- Đồng hồ ở bảng điều khiển lấy giờ Việt Nam của trình duyệt. OLED trên mạch lấy giờ RTC; khi dùng TIME trong Wokwi, hai đồng hồ có thể khác nhau.
- Đèn mô hình và bảng điều khiển là trạng thái suy ra từ gateway: xám khi offline, xanh khi chờ, vàng khi có lượt nhắc đang chờ, đỏ khi có cảnh báo của ngăn chưa giải quyết. Chúng không phải số đo điện áp LED trên mạch.
- Nạp thuốc vẫn cần xác minh, cấp phép, ACK và sự kiện mở đúng ngăn. Ở chế độ local, nút “Ghi nhận mở ngăn mô phỏng” gọi simulator thật của ứng dụng. Nó không tác động tới ESP32. Ở chế độ MQTT hãy thao tác nút ngăn trên Wokwi/mạch để gửi sự kiện.
- Viên thuốc trong mô hình chỉ thể hiện hình dạng. Không có cảm biến đếm viên; không suy ra tồn kho từ hình ảnh.

## Sơ đồ Wokwi và firmware

`diagram.json` thêm OLED SSD1306 (I²C 0x3C) dùng chung SDA GPIO3 / SCL GPIO4 với RTC, VCC 3V3 và GND. `ProductPanel` dùng Adafruit SSD1306/GFX và Keypad. OLED hiển thị HH:MM:SS, kết nối MQTT, trạng thái nhắc, mã thuốc từ lịch firmware và dữ liệu đang nhập.

Wokwi dùng bàn phím 4×4 làm **bộ giả lập đầu đọc mã**, không có phần tử quét quang học thật. Nhập số rồi nhấn `#` để gửi, `*` xóa một ký tự, `D` xóa toàn bộ; `A/B/C` chọn ngăn 1/2/3. Rows GPIO15/16/17/18; columns GPIO21/33/34/35. Đầu đọc UART thật dùng TX→GPIO13 (RX của ESP32), RX→GPIO14, GND chung, 9600 baud 8N1; cấu hình đầu đọc xuất chuỗi ASCII kết thúc CR/LF, tối đa 48 ký tự. Kiểm tra điện áp logic 3.3V; module 5V cần chuyển mức phù hợp.

Mã quét đi trong trường bổ sung `barcode`, `barcode_sequence` của heartbeat cùng `boot_id`. Gateway lưu lần quét mới theo hộp, không tạo verification hay tự mở phiên nạp. Người chăm sóc vào Nạp thuốc → “Tra cứu mã từ mạch” → kiểm tra → xác minh. Các topic MQTT hiện có giữ nguyên. Nếu danh mục chưa có ánh xạ barcode, giao diện báo không tìm thấy.

Mạch hiện có nút nhấn đại diện cho sự kiện mở ngăn. Chưa có servo/chốt điện hay cảm biến đóng nắp; việc đóng/mở 3D không điều khiển một động cơ. Muốn mở nắp vật lý cần bổ sung cơ cấu chấp hành, cảm biến và giao thức xác nhận riêng.

## Chạy

Git Bash:

```bash
./.venv/Scripts/python.exe -m gateway
```

Biên dịch firmware bằng PlatformIO: `pio run -e esp32s2_wokwi`, sau đó chạy Wokwi như README. Muốn thấy dữ liệu Wokwi trên web, chạy cấu hình MQTT với cùng device ID/broker. Chế độ local chỉ nối simulator phần mềm.

## Kiểm tra

Firmware Wokwi build thành công; backend 99 tests thành công, gồm capture barcode, chống ghi lặp heartbeat và kiểm tra rằng scan không tự tạo refill verification. Chưa kiểm chứng quét quang học với đầu đọc UART thật hoặc lắp mạch vật lý.

Browser smoke test đạt ở 320, 390, 768, 1024 và 1440px: đồng hồ chạy, chọn ngăn, đóng/mở nắp mô hình, nút nạp chọn đúng ngăn, tra cứu barcode không tự cấp phép nạp, phân trang và các bước xác minh/ACK/xác nhận qua fixture. Luồng refill trong smoke test dùng phản hồi POST giả lập; không phải thử mạch thật. Ảnh kiểm tra nằm trong `.pio/ui-desktop.png`, `.pio/ui-mobile.png`, `.pio/ui-lid-open.png` và `.pio/ui-refill.png`.

Design Taste gate vòng 2 còn 34 findings trước lần sửa màu chữ cuối: shader lint trên thư viện Three.js, canvas phủ nhãn màn hình ảo, thẻ chỉ chứa dữ liệu, số kiểu nút/chiều cao nút, category tiếng Anh không khớp tiêu đề tiếng Việt, số thao tác trong hero, kích thước đồng hồ, contrast dòng hướng dẫn (đã sửa), motion layer, quy tắc chiều cao từng section, căn container/grid, nav mobile, tỷ lệ vùng hình và thiếu `.wrap`. Giao diện chưa đạt gate cho website giới thiệu; không có waiver hay chỉnh thư viện để bỏ qua checker. Các kiểm thử ứng dụng và firmware nêu trên là kết quả riêng.
