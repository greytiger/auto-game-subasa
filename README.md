# auto-game-subasa (macOS Android Emulator)

Tool tự động chạy các nhiệm vụ trong game **Captain Tsubasa: Dream Team** trên **giả lập Android trên macOS** (MuMuPlayer Pro, BlueStacks Air, Android Studio AVD) thông qua **ADB + Computer Vision (OpenCV)**.

## Tài liệu
- Hướng dẫn cài đặt trên macOS: [docs/MACOS_EMULATOR_SETUP.md](docs/MACOS_EMULATOR_SETUP.md)
- Sơ đồ tương tác: [docs/architecture.html](docs/architecture.html)
- Ghi chú thiết kế gốc: [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md)

## Cấu trúc thư mục
```text
auto-game-subasa/
├── docs/
│   ├── MACOS_EMULATOR_SETUP.md
│   ├── architecture.html
│   └── DESIGN_NOTES.md
├── src/
│   ├── config.py           # Cấu hình cổng ADB giả lập macOS, ROI & Watchdog
│   ├── adb_client.py       # Persistent ADB + Raw Screencap + Fallback PNG
│   ├── vision.py           # Frame Diff, Pixel Fingerprint, ROI Template Matching
│   ├── watchdog.py         # Tự phục hồi đa tầng (Soft/Hard Stuck)
│   ├── state_machine.py    # State Graph + Action Verification + Adaptive Sleep
│   └── main.py             # CLI (--check, --capture, --dry-run)
├── templates/              # Ảnh mẫu các nút bấm (.png)
├── tests/                  # Unit tests
├── logs/stuck/             # Ảnh chụp tự động khi gặp màn hình lạ / bị kẹt
└── requirements.txt
```

## Chạy nhanh trên macOS
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --emulator mumu --check
```
