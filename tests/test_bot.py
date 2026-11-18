"""Unit tests for vision, config scaling, watchdog, and state machine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np

from src.config import ADBConfig, BotConfig, TimingConfig, VisionConfig
from src.state_machine import GameBot, GameState, StateRule
from src.vision import TemplateStore, VisionEngine, scale_point, scale_roi
from src.watchdog import StuckLevel, Watchdog


class TestConfigAndScaling(unittest.TestCase):
    def test_adb_target_resolution(self) -> None:
        self.assertEqual(ADBConfig(emulator_type="mumu").resolved_target(), "127.0.0.1:16384")
        self.assertEqual(ADBConfig(emulator_type="bluestacks").resolved_target(), "127.0.0.1:5555")
        self.assertEqual(ADBConfig(emulator_type="avd").resolved_target(), "emulator-5554")
        self.assertEqual(
            ADBConfig(emulator_type="mumu", emulator_port=7555).resolved_target(),
            "127.0.0.1:7555",
        )
        self.assertEqual(
            ADBConfig(serial="custom-123").resolved_target(),
            "custom-123",
        )

    def test_scale_point_and_roi(self) -> None:
        self.assertEqual(scale_point(960, 540, (1920, 1080), (1280, 720)), (640, 360))
        self.assertEqual(
            scale_roi((0, 0, 1920, 1080), (1920, 1080), (1280, 720)),
            (0, 0, 1280, 720),
        )


class TestVisionEngine(unittest.TestCase):
    def test_frame_diff_and_template_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpl_dir = Path(tmp)
            # Create synthetic 1080p frame with a distinct bright patch
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            cv2.rectangle(frame, (1400, 800), (1560, 880), (0, 220, 180), -1)
            cv2.circle(frame, (1480, 840), 20, (255, 255, 255), -1)

            # Save template crop
            crop = frame[800:880, 1400:1560]
            cv2.imwrite(str(tmpl_dir / "btn_test.png"), crop)

            store = TemplateStore(tmpl_dir, downscale_factor=0.5)
            vision = VisionEngine(VisionConfig(), store)

            diff_same, small1 = vision.compute_frame_diff(None, frame)
            self.assertEqual(diff_same, 255.0)
            diff_zero, _ = vision.compute_frame_diff(small1, frame)
            self.assertEqual(diff_zero, 0.0)

            match = vision.match_template(frame, "btn_test", roi=(1300, 750, 1700, 950))
            self.assertIsNotNone(match)
            assert match is not None
            self.assertGreater(match.score, 0.9)
            self.assertAlmostEqual(match.center_x, 1480, delta=3)
            self.assertAlmostEqual(match.center_y, 840, delta=3)

            # Pixel fingerprint check
            self.assertTrue(
                vision.check_pixel_fingerprint(frame, [(1480, 840, (255, 255, 255))])
            )
            self.assertFalse(
                vision.check_pixel_fingerprint(frame, [(1480, 840, (0, 0, 0))])
            )


class TestWatchdogAndStateMachine(unittest.TestCase):
    def test_watchdog_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            timing = TimingConfig(
                soft_stuck_menu_sec=10.0,
                hard_stuck_sec=30.0,
                max_failed_taps=2,
            )
            wd = Watchdog(timing, Path(tmp) / "stuck")
            base = wd.last_progress_ts

            self.assertEqual(wd.evaluate(in_match=False, now=base + 5.0), StuckLevel.NONE)
            self.assertEqual(wd.evaluate(in_match=False, now=base + 12.0), StuckLevel.SOFT_STUCK)
            self.assertEqual(wd.evaluate(in_match=False, now=base + 35.0), StuckLevel.HARD_STUCK)

            wd.record_tap_outcome(False, now=base + 1.0)
            wd.record_tap_outcome(False, now=base + 2.0)
            self.assertEqual(wd.evaluate(in_match=False, now=base + 2.5), StuckLevel.SOFT_STUCK)

    def test_game_bot_step_with_mock_adb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tmpl_dir = tmp_path / "templates"
            tmpl_dir.mkdir()

            frame1 = np.zeros((1080, 1920, 3), dtype=np.uint8)
            cv2.rectangle(frame1, (700, 800), (900, 900), (50, 200, 250), -1)
            cv2.circle(frame1, (800, 850), 22, (255, 255, 255), -1)
            cv2.imwrite(str(tmpl_dir / "title_tap_start.png"), frame1[800:900, 700:900])

            frame2 = np.full((1080, 1920, 3), 120, dtype=np.uint8)

            adb = MagicMock()
            adb.screencap_bgr.side_effect = [frame1, frame2]

            cfg = BotConfig(
                timing=TimingConfig(action_verify_wait_sec=0.0),
                templates_dir=tmpl_dir,
                stuck_logs_dir=tmp_path / "stuck",
            )
            store = TemplateStore(tmpl_dir, downscale_factor=cfg.vision.downscale_factor)
            vision = VisionEngine(cfg.vision, store)
            wd = Watchdog(cfg.timing, cfg.stuck_logs_dir)
            rules = {
                GameState.TITLE: StateRule(
                    state=GameState.TITLE,
                    template_name="title_tap_start",
                    roi=(600, 750, 1000, 950),
                )
            }
            bot = GameBot(cfg, adb, vision, wd, rules=rules)

            bot.step()
            self.assertEqual(bot.current_state, GameState.TITLE)
            adb.tap.assert_called_once()
            self.assertEqual(wd.consecutive_failed_taps, 0)


if __name__ == "__main__":
    unittest.main()
