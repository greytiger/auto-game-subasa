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

- **BlueStacks Air (macOS — mặc định, miễn phí trên M4):** Settings → Advanced → bật *Android Debug Bridge (ADB)* → cổng mặc định `5555`.
- **Android Studio AVD:** Tự động hiển thị dưới dạng `emulator-5554`.
- **MuMuPlayer Pro (Apple Silicon):** Bật *ADB Debugging* trong Settings → mặc định cổng `16384` (hoặc `7555`).

Cấu hình khuyên dùng cho **MacBook Air M4**: độ phân giải `1280×720` hoặc `1920×1080` (Landscape), giới hạn **30 FPS**, `4 GB RAM`, tắt tiếng giả lập để máy mát khi treo lâu. Tool hỗ trợ **auto-reconnect ADB** nếu kết nối bị ngắt tạm thời.

## 3. Kiểm tra kết nối & Chụp ảnh mẫu (Templates)

```bash
# Kiểm tra kết nối ADB (mặc định là bluestacks cổng 5555)
python -m src.main --check

# Hoặc chỉ định giả lập / cổng tùy chỉnh
python -m src.main --emulator avd --check
python -m src.main --port 5555 --check
```

Chụp ảnh mẫu nút bấm vào `templates/` (ví dụ nút `home_story_btn`):

```bash
python -m src.main --capture home_story_btn --roi 1350 700 1750 920
```

## 4. Chạy Bot

```bash
# Chạy thử không bấm thật (Dry-run)
python -m src.main --dry-run --verbose

# Chạy tự động thật
python -m src.main
```
