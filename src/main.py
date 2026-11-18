"""CLI entry point for running auto-game-subasa on a macOS Android emulator."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple

import cv2

from src.adb_client import ADBConnectionError, EmulatorADBClient
from src.config import ADBConfig, BotConfig, EMULATOR_ADB_PORTS
from src.state_machine import GameBot
from src.vision import TemplateStore, VisionEngine
from src.watchdog import Watchdog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Captain Tsubasa: Dream Team automation for macOS Android emulators"
    )
    parser.add_argument(
        "--emulator",
        choices=sorted(EMULATOR_ADB_PORTS.keys()),
        default="mumu",
        help="macOS Android emulator preset (default: mumu)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override emulator ADB port (e.g. 16384 for MuMu, 5555 for BlueStacks)",
    )
    parser.add_argument(
        "--serial",
        type=str,
        default=None,
        help="Explicit ADB device serial (e.g. 127.0.0.1:16384 or emulator-5554)",
    )
    parser.add_argument(
        "--package",
        type=str,
        default="jp.klab.captain283.global",
        help="Android package name of the game",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Test ADB connection, print emulator resolution, and save a test screenshot",
    )
    parser.add_argument(
        "--capture",
        type=str,
        default=None,
        metavar="NAME",
        help="Capture current emulator screen (or --roi crop) into templates/NAME.png",
    )
    parser.add_argument(
        "--roi",
        type=int,
        nargs=4,
        default=None,
        metavar=("X1", "Y1", "X2", "Y2"),
        help="Optional crop region (in actual emulator pixels) when using --capture",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect states and log actions without sending taps",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def capture_template(
    adb: EmulatorADBClient,
    templates_dir: Path,
    name: str,
    roi: Optional[Tuple[int, int, int, int]] = None,
) -> Path:
    frame = adb.screencap_bgr()
    if roi is not None:
        x1, y1, x2, y2 = roi
        frame = frame[y1:y2, x1:x2]
    templates_dir.mkdir(parents=True, exist_ok=True)
    out_path = templates_dir / f"{name}.png"
    cv2.imwrite(str(out_path), frame)
    return out_path


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = BotConfig(
        adb=ADBConfig(
            emulator_type=args.emulator,
            emulator_port=args.port,
            serial=args.serial,
            package_name=args.package,
        ),
        dry_run=args.dry_run,
    )

    adb = EmulatorADBClient(config.adb)
    try:
        adb.connect()
    except ADBConnectionError as exc:
        logging.error("%s", exc)
        return 1

    if args.check:
        frame = adb.screencap_bgr()
        out_dir = Path("logs")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "test_screencap.png"
        cv2.imwrite(str(out_path), frame)
        logging.info("Connection OK! Saved test screenshot to %s", out_path)
        return 0

    if args.capture:
        roi = tuple(args.roi) if args.roi else None
        out_path = capture_template(adb, config.templates_dir, args.capture, roi=roi)
        logging.info("Captured template to %s", out_path)
        return 0

    templates = TemplateStore(
        config.templates_dir, downscale_factor=config.vision.downscale_factor
    )
    available = templates.available_names()
    if not available:
        logging.warning(
            "No templates found in %s/. Use --capture NAME --roi X1 Y1 X2 Y2 to add templates.",
            config.templates_dir,
        )
    else:
        logging.info("Loaded %d template(s): %s", len(available), ", ".join(available))

    vision = VisionEngine(config.vision, templates)
    watchdog = Watchdog(config.timing, config.stuck_logs_dir)
    bot = GameBot(config, adb, vision, watchdog)
    bot.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
