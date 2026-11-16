# auto-game-subasa

Tool tự động chạy các nhiệm vụ trong game **Captain Tsubasa: Dream Team** trực tiếp trên **Samsung Galaxy Tab S8** thông qua **Termux + ADB Wireless**, hỗ trợ điều khiển từ xa qua `agy-cli` trên trình duyệt.

## Tài liệu kiến trúc
- Sơ đồ tương tác: [docs/architecture.html](docs/architecture.html)
- Tổng hợp ngữ cảnh & quyết định thiết kế từ cuộc trò chuyện: [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md)

## Cấu trúc thư mục
```text
auto-game-subasa/
├── docs/
│   ├── architecture.html   # Sơ đồ trực quan (mở bằng trình duyệt)
│   └── DESIGN_NOTES.md     # Toàn bộ thiết kế & yêu cầu đã thống nhất
├── src/                    # Mã nguồn Python (ADB, Vision, State Machine, Watchdog)
├── templates/              # Ảnh mẫu các nút bấm (ROI templates) theo Tab S8
├── logs/
│   └── stuck/              # Ảnh chụp tự động khi gặp màn hình lạ / bị kẹt
└── requirements.txt
```

## Môi trường mục tiêu (Galaxy Tab S8)
- **OS:** Android (không cần Root), độ phân giải mặc định `2560×1600` (Landscape).
- **Runtime:** Termux + Python 3 (`termux-wake-lock`, tắt tối ưu pin cho Termux).
- **Kết nối:** ADB Wireless (`localhost`), điều khiển từ xa qua `agy-cli` web remote control trong mạng LAN.
