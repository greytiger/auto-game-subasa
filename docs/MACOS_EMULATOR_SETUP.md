# Hướng dẫn chạy trên Giả lập Android (macOS)

Nhánh `feat/macos-emulator` chuyển đổi tool để chạy trực tiếp từ **macOS** điều khiển giả lập Android qua **ADB** (`127.0.0.1:5037`), hỗ trợ tự động scale tọa độ theo độ phân giải giả lập.

## 1. Cài đặt ADB & Python trên macOS

```bash
# Cài Android Platform Tools (ADB)
brew install android-platform-tools

# Khởi động ADB server
adb start-server
```

Tạo môi trường ảo Python và cài thư viện:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Bật ADB trên giả lập Android (macOS)

- **MuMuPlayer Pro (Apple Silicon):** Bật *ADB Debugging* trong Settings → mặc định cổng `16384` (hoặc `7555`).
- **BlueStacks Air (macOS):** Settings → Advanced → bật *Android Debug Bridge (ADB)* → mặc định cổng `5555`.
- **Android Studio AVD:** Tự động hiển thị dưới dạng `emulator-5554`.

Khuyến nghị đặt độ phân giải giả lập ở **1920×1080 (Landscape)** để khớp 1:1 với tọa độ tham chiếu, hoặc bất kỳ tỷ lệ 16:9 nào (hệ thống tự scale ROI).

## 3. Kiểm tra kết nối & Chụp ảnh mẫu (Templates)

```bash
# Kiểm tra kết nối ADB với MuMuPlayer Pro
python -m src.main --emulator mumu --check

# Hoặc với BlueStacks Air / cổng tùy chỉnh
python -m src.main --emulator bluestacks --check
python -m src.main --port 7555 --check
```

Chụp ảnh mẫu nút bấm vào `templates/` (ví dụ nút `home_story_btn`):

```bash
python -m src.main --emulator mumu --capture home_story_btn --roi 1350 700 1750 920
```

## 4. Chạy Bot

```bash
# Chạy thử không bấm thật (Dry-run)
python -m src.main --emulator mumu --dry-run --verbose

# Chạy tự động thật
python -m src.main --emulator mumu
```
