"""Persistent ADB client tailored for Android emulators on macOS."""

from __future__ import annotations

import logging
import re
import struct
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from src.config import ADBConfig

logger = logging.getLogger(__name__)


class ADBConnectionError(RuntimeError):
    """Raised when the macOS ADB server or target emulator cannot be reached."""


class EmulatorADBClient:
    """Persistent ADB wrapper using adbutils over 127.0.0.1:5037."""

    def __init__(self, config: ADBConfig) -> None:
        self.config = config
        self._client = None
        self._device = None
        self._screen_size: Optional[Tuple[int, int]] = None

    def connect(self) -> None:
        """Connect to the local macOS ADB server and bind to the target emulator."""
        try:
            import adbutils
        except ImportError as exc:
            raise ADBConnectionError(
                "adbutils is not installed. Run: pip install -r requirements.txt"
            ) from exc

        self._client = adbutils.AdbClient(
            host=self.config.host,
            port=self.config.server_port,
        )

        target = self.config.resolved_target()
        if target and ":" in target:
            try:
                out = self._client.connect(target, timeout=5.0)
                logger.info("ADB connect(%s): %s", target, out)
            except Exception as exc:
                logger.warning("ADB connect(%s) failed: %s", target, exc)

        devices = self._client.device_list()
        if not devices:
            raise ADBConnectionError(
                "No Android emulator detected via ADB. "
                "Make sure your macOS emulator (MuMuPlayer Pro / BlueStacks Air / AVD) "
                "is running with ADB debugging enabled."
            )

        if target:
            for dev in devices:
                if dev.serial == target:
                    self._device = dev
                    break

        if self._device is None:
            self._device = devices[0]
            logger.info(
                "Target %s not matched directly; using first available device: %s",
                target,
                self._device.serial,
            )
        else:
            logger.info("Connected to emulator: %s", self._device.serial)

        self._screen_size = self.get_screen_size()
        logger.info("Emulator resolution: %dx%d", *self._screen_size)

    @property
    def device(self):
        if self._device is None:
            raise ADBConnectionError("ADB client is not connected. Call connect() first.")
        return self._device

    def get_screen_size(self) -> Tuple[int, int]:
        """Return (width, height) of the emulator display."""
        output = self.device.shell("wm size")
        # Matches lines like "Physical size: 1920x1080" or "Override size: 1280x720"
        matches = re.findall(r"(\d+)x(\d+)", output)
        if not matches:
            raise ADBConnectionError(f"Could not parse screen size from: {output!r}")
        width, height = map(int, matches[-1])
        self._screen_size = (width, height)
        return self._screen_size

    def screencap_bgr(self) -> np.ndarray:
        """Capture the current frame as a BGR numpy array.

        Tries raw `screencap` first (avoids PNG compression overhead), and falls
        back to `screencap -p` if the emulator returns an unexpected raw header.
        """
        raw = self._read_raw_screencap()
        if raw is not None:
            return raw

        png_bytes = self._read_shell_bytes("screencap -p")
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ADBConnectionError("Failed to decode PNG screenshot from emulator.")
        return img

    def _read_raw_screencap(self) -> Optional[np.ndarray]:
        try:
            data = self._read_shell_bytes("screencap")
            if len(data) < 12:
                return None
            width, height, pixel_format = struct.unpack("<III", data[:12])
            # pixel_format == 1 is RGBA_8888 (4 bytes per pixel)
            expected_size = 12 + width * height * 4
            if width <= 0 or height <= 0 or pixel_format != 1 or len(data) < expected_size:
                return None
            rgba = np.frombuffer(
                data[12:expected_size], dtype=np.uint8
            ).reshape((height, width, 4))
            return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
        except Exception as exc:
            logger.debug("Raw screencap failed, falling back to PNG: %s", exc)
            return None

    def _read_shell_bytes(self, cmd: str) -> bytes:
        stream = self.device.shell(cmd, stream=True)
        try:
            return stream.read_bytes()
        finally:
            stream.close()

    def tap(self, x: int, y: int) -> None:
        logger.debug("ADB tap(%d, %d)", x, y)
        self.device.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        logger.debug("ADB swipe(%d,%d -> %d,%d, %dms)", x1, y1, x2, y2, duration_ms)
        self.device.shell(
            f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}"
        )

    def keyevent(self, keycode: int) -> None:
        logger.debug("ADB keyevent(%d)", keycode)
        self.device.shell(f"input keyevent {int(keycode)}")

    def back(self) -> None:
        self.keyevent(4)

    def force_stop(self, package_name: Optional[str] = None) -> None:
        pkg = package_name or self.config.package_name
        logger.warning("Force stopping package: %s", pkg)
        self.device.shell(f"am force-stop {pkg}")

    def launch_app(self, package_name: Optional[str] = None, wait_sec: float = 2.0) -> None:
        pkg = package_name or self.config.package_name
        logger.info("Launching package: %s", pkg)
        self.device.shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        if wait_sec > 0:
            time.sleep(wait_sec)
