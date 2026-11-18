"""Configuration for Captain Tsubasa: Dream Team automation on macOS Android emulators."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple


EMULATOR_ADB_PORTS: Dict[str, int] = {
    "mumu": 16384,       # MuMuPlayer Pro (macOS Apple Silicon) default ADB port
    "bluestacks": 5555,  # BlueStacks Air (macOS) default ADB port
    "nox": 62001,        # NoxPlayer default ADB port
    "avd": 5554,         # Android Studio AVD (usually appears as emulator-5554)
}


@dataclass
class ADBConfig:
    host: str = "127.0.0.1"
    server_port: int = 5037
    emulator_type: str = "mumu"
    emulator_port: int | None = None
    serial: str | None = None
    package_name: str = "jp.klab.captain283.global"

    def resolved_target(self) -> str | None:
        if self.serial:
            return self.serial
        if self.emulator_type == "avd":
            return "emulator-5554"
        port = self.emulator_port or EMULATOR_ADB_PORTS.get(self.emulator_type)
        if port:
            return f"127.0.0.1:{port}"
        return None


@dataclass
class VisionConfig:
    # Reference resolution used when defining ROIs and capturing templates.
    ref_width: int = 1920
    ref_height: int = 1080
    diff_size: Tuple[int, int] = (64, 40)
    frame_diff_idle_threshold: float = 1.5
    action_verify_diff_threshold: float = 2.0
    template_threshold: float = 0.82
    downscale_factor: float = 0.5
    pixel_tolerance: int = 25


@dataclass
class TimingConfig:
    menu_sleep_sec: float = 0.5
    match_sleep_sec: float = 3.5
    action_verify_wait_sec: float = 1.2
    soft_stuck_menu_sec: float = 18.0
    soft_stuck_match_sec: float = 240.0
    hard_stuck_sec: float = 50.0
    max_failed_taps: int = 3


@dataclass
class BotConfig:
    adb: ADBConfig = field(default_factory=ADBConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    templates_dir: Path = Path("templates")
    stuck_logs_dir: Path = Path("logs/stuck")
    dry_run: bool = False
