"""Multi-tier self-healing watchdog for stuck detection and recovery."""

from __future__ import annotations

import logging
import time
from enum import Enum, auto
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from src.config import TimingConfig
from src.vision import VisionEngine, save_debug_frame, scale_point

logger = logging.getLogger(__name__)

UNIVERSAL_ESCAPE_TEMPLATES = (
    "btn_close_x",
    "btn_ok",
    "btn_retry",
    "btn_skip",
    "btn_cancel",
)


class StuckLevel(Enum):
    NONE = auto()
    SOFT_STUCK = auto()
    HARD_STUCK = auto()


class Watchdog:
    """Monitors bot progress and escalates recovery when stuck."""

    def __init__(self, timing: TimingConfig, stuck_logs_dir: Path) -> None:
        self.timing = timing
        self.stuck_logs_dir = stuck_logs_dir
        now = time.monotonic()
        self.last_progress_ts: float = now
        self.consecutive_failed_taps: int = 0
        self.tier1_attempts: int = 0

    def reset(self, now: Optional[float] = None) -> None:
        ts = now if now is not None else time.monotonic()
        self.last_progress_ts = ts
        self.consecutive_failed_taps = 0
        self.tier1_attempts = 0

    def record_tap_outcome(self, screen_changed: bool, now: Optional[float] = None) -> None:
        if screen_changed:
            self.reset(now)
        else:
            self.consecutive_failed_taps += 1
            logger.debug(
                "Tap did not change screen (%d/%d)",
                self.consecutive_failed_taps,
                self.timing.max_failed_taps,
            )

    def evaluate(self, in_match: bool = False, now: Optional[float] = None) -> StuckLevel:
        ts = now if now is not None else time.monotonic()
        elapsed = ts - self.last_progress_ts
        soft_limit = (
            self.timing.soft_stuck_match_sec
            if in_match
            else self.timing.soft_stuck_menu_sec
        )

        if elapsed >= self.timing.hard_stuck_sec and not in_match:
            return StuckLevel.HARD_STUCK
        if (
            elapsed >= soft_limit
            or self.consecutive_failed_taps >= self.timing.max_failed_taps
        ):
            return StuckLevel.SOFT_STUCK
        return StuckLevel.NONE

    def recover(
        self,
        level: StuckLevel,
        frame_bgr: np.ndarray,
        adb_client,
        vision: VisionEngine,
        ref_size: tuple[int, int],
        escape_templates: Iterable[str] = UNIVERSAL_ESCAPE_TEMPLATES,
        dry_run: bool = False,
    ) -> str:
        """Execute multi-tier recovery and return a short action description."""
        if level == StuckLevel.NONE:
            return "none"

        if level == StuckLevel.HARD_STUCK:
            save_debug_frame(frame_bgr, self.stuck_logs_dir, "hard_stuck")
            if dry_run:
                self.reset()
                return "dry_run:tier3_force_stop_relaunch"
            adb_client.force_stop()
            time.sleep(2.0)
            adb_client.launch_app()
            self.reset()
            return "tier3_force_stop_relaunch"

        # Tier 1: Full-scan Universal Escape Buttons
        if self.tier1_attempts == 0:
            self.tier1_attempts += 1
            save_debug_frame(frame_bgr, self.stuck_logs_dir, "soft_stuck_tier1")
            for tmpl_name in escape_templates:
                match = vision.match_template(frame_bgr, tmpl_name, roi=None)
                if match is not None:
                    logger.info(
                        "Tier 1 recovery matched %s (score=%.2f) at (%d, %d)",
                        tmpl_name,
                        match.score,
                        match.center_x,
                        match.center_y,
                    )
                    if not dry_run:
                        adb_client.tap(match.center_x, match.center_y)
                    self.consecutive_failed_taps = 0
                    return f"tier1_tap_{tmpl_name}"

        # Tier 2: Android Back key + neutral tap
        save_debug_frame(frame_bgr, self.stuck_logs_dir, "soft_stuck_tier2")
        self.tier1_attempts = 0
        self.consecutive_failed_taps = 0
        if dry_run:
            return "dry_run:tier2_back_and_neutral_tap"

        adb_client.back()
        time.sleep(0.5)
        h, w = frame_bgr.shape[:2]
        nx, ny = scale_point(ref_size[0] // 2, int(ref_size[1] * 0.85), ref_size, (w, h))
        adb_client.tap(nx, ny)
        return "tier2_back_and_neutral_tap"
