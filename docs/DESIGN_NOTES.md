# Ghi chú thiết kế & Ngữ cảnh cuộc trò chuyện

Tài liệu này lưu lại toàn bộ yêu cầu, môi trường và kiến trúc đã thống nhất để dùng làm ngữ cảnh gốc cho project `auto-game-subasa`.

## 1. Môi trường & Hạ tầng của người dùng
- **Thiết bị chạy game & bot:** Samsung Galaxy Tab S8 (màn hình ngang 2560×1600, không root).
- **Môi trường chạy tool:** Cài `agy-cli` qua **Termux**, bật **ADB Wireless** ngay trên Tab S8.
- **Điều khiển từ xa:** Đã cấu hình xong `agy-cli` remote control qua mạng LAN, truy cập từ bất kỳ thiết bị nào qua trình duyệt để điều khiển `agy-cli` trên Tab S8.
- **Mục tiêu chính:** Viết tool tự động chạy các nhiệm vụ trong game *Captain Tsubasa: Dream Team*.

## 2. Kiến trúc tối ưu hiệu năng (Tab S8)
Do *Captain Tsubasa: Dream Team* render bằng game engine (không đọc được UI tree qua `uiautomator`), tool dùng Computer Vision kết hợp ADB với các tối ưu sau:

1. **Persistent ADB + Raw Screencap:**
   - Giữ kết nối socket ADB liên tục (qua `adbutils` hoặc TCP `localhost:5037`) thay vì spawn subprocess `adb` mỗi vòng lặp.
   - Dùng `screencap` dạng raw RGBA (bỏ cờ `-p`) để tránh tốn 300–600ms CPU nén PNG mỗi khung hình.
   - Giữ sẵn 1 luồng `adb shell` pipe để gửi `input tap` / `input keyevent` nhanh.
2. **Frame Diff (`64×40` Grayscale):**
   - So sánh khung hình hiện tại với khung hình trước; nếu màn hình đứng yên (hoặc đang Auto trong trận), bỏ qua OpenCV và ngủ tiếp.
3. **Pixel Fingerprint + State Graph:**
   - Kiểm tra 3–5 tọa độ RGB cố định (`< 0.01ms`) của **2–3 trạng thái kế tiếp hợp lệ + popup toàn cục** thay vì quét toàn bộ 20 màn hình.
4. **ROI + Downscale 0.5x Grayscale Template Matching:**
   - Chỉ cắt đúng vùng nút hay xuất hiện (ROI) và giảm 50% độ phân giải xám trước khi chạy `cv2.matchTemplate`.
5. **Adaptive Sleep:**
   - Đang trong trận Auto: ngủ dài (check mỗi 3–5s).
   - Đang thao tác menu: check mỗi 0.4–0.6s.

## 3. Cơ chế chống kẹt & Tự phục hồi (Self-Healing)
Để tránh tình trạng nhận diện sai màn hình hoặc đứng im quá lâu:

1. **Action Verification:** Sau khi tap nút chuyển màn, kiểm tra Frame Diff trong 1–2s. Nếu bấm 2–3 lần liên tiếp không có tác dụng → kích hoạt phục hồi ngay.
2. **Watchdog Timer:**
   - **Soft Stuck** (15–20s ở menu, hoặc > 4 phút trong trận).
   - **Hard Stuck** (45–60s vẫn không thoát được).
3. **Multi-tier Recovery Escalation:**
   - **Cấp 1:** Tạm bỏ State Graph, chạy Full-Scan + nhóm **Universal Escape Buttons** (`Close X`, `OK`, `Retry`, `Skip`, `Cancel`) + lưu ảnh vào `logs/stuck/`.
   - **Cấp 2:** Gửi phím Back Android (`input keyevent 4`) hoặc tap vùng trung tính (*Tap to continue*).
   - **Cấp 3 (Hard Stuck):** `am force-stop <package>` → đợi 2s → mở lại game → đi qua `Title` → `Home` → tiếp tục nhiệm vụ.
4. **Auto-Debug Snapshot:** Lưu ảnh chụp mỗi khi gặp `UNKNOWN` hoặc kích hoạt Cấp 2–3 để dễ bổ sung template mới.
