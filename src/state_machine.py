"""State graph and main automation loop for Captain Tsubasa: Dream Team."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.adb_client import ADBConnectionError
from src.config import BotConfig
from src.vision import ROI, MatchResult, VisionEngine, save_debug_frame
from src.watchdog import StuckLevel, Watchdog

logger = logging.getLogger(__name__)


class GameState(Enum):
    UNKNOWN = auto()
    TITLE = auto()
    HOME = auto()
    QUEST_SELECT = auto()
    TEAM_CONFIRM = auto()
    IN_MATCH_AUTO = auto()
    MATCH_RESULT = auto()
    POPUP_REWARD = auto()
    POPUP_ERROR = auto()


@dataclass(frozen=True)
class StateRule:
    state: GameState
    template_name: str
    roi: Optional[ROI] = None  # Defined in VisionConfig reference resolution (1920x1080)
    tap_offset: Tuple[int, int] = (0, 0)
    is_passive: bool = False  # True when waiting (e.g. IN_MATCH_AUTO)


# Default rules in 1920x1080 reference coordinates; automatically scaled to actual emulator size.
DEFAULT_RULES: Dict[GameState, StateRule] = {
    GameState.TITLE: StateRule(
        state=GameState.TITLE,
        template_name="title_tap_start",
        roi=(600, 750, 1320, 1020),
    ),
    GameState.HOME: StateRule(
        state=GameState.HOME,
        template_name="home_story_btn",
        roi=(1200, 600, 1900, 1050),
    ),
    GameState.QUEST_SELECT: StateRule(
        state=GameState.QUEST_SELECT,
        template_name="quest_start_btn",
        roi=(1300, 750, 1900, 1060),
    ),
    GameState.TEAM_CONFIRM: StateRule(
        state=GameState.TEAM_CONFIRM,
        template_name="team_kickoff_btn",
        roi=(1300, 780, 1900, 1060),
    ),
    GameState.IN_MATCH_AUTO: StateRule(
        state=GameState.IN_MATCH_AUTO,
        template_name="match_auto_active",
        roi=(1550, 20, 1900, 200),
        is_passive=True,
    ),
    GameState.MATCH_RESULT: StateRule(
        state=GameState.MATCH_RESULT,
        template_name="result_next_btn",
        roi=(700, 800, 1900, 1060),
    ),
    GameState.POPUP_REWARD: StateRule(
        state=GameState.POPUP_REWARD,
        template_name="btn_ok",
        roi=(550, 550, 1370, 950),
    ),
    GameState.POPUP_ERROR: StateRule(
        state=GameState.POPUP_ERROR,
        template_name="btn_retry",
        roi=(550, 550, 1370, 950),
    ),
}

# Allowed next states from each state (+ global popups checked every tick)
GLOBAL_POPUP_STATES: Tuple[GameState, ...] = (
    GameState.POPUP_ERROR,
    GameState.POPUP_REWARD,
)

STATE_GRAPH: Dict[GameState, Tuple[GameState, ...]] = {
    GameState.UNKNOWN: tuple(DEFAULT_RULES.keys()),
    GameState.TITLE: (GameState.HOME, GameState.TITLE),
    GameState.HOME: (GameState.QUEST_SELECT, GameState.HOME),
    GameState.QUEST_SELECT: (GameState.TEAM_CONFIRM, GameState.QUEST_SELECT),
    GameState.TEAM_CONFIRM: (GameState.IN_MATCH_AUTO, GameState.TEAM_CONFIRM),
    GameState.IN_MATCH_AUTO: (GameState.MATCH_RESULT, GameState.IN_MATCH_AUTO),
    GameState.MATCH_RESULT: (
        GameState.QUEST_SELECT,
        GameState.HOME,
        GameState.MATCH_RESULT,
    ),
    GameState.POPUP_REWARD: tuple(DEFAULT_RULES.keys()),
    GameState.POPUP_ERROR: tuple(DEFAULT_RULES.keys()),
}


class GameBot:
    """State-graph driven automation bot with Frame Diff & Watchdog."""

    def __init__(
        self,
        config: BotConfig,
        adb_client,
        vision: VisionEngine,
        watchdog: Watchdog,
        rules: Optional[Dict[GameState, StateRule]] = None,
    ) -> None:
        self.config = config
        self.adb = adb_client
        self.vision = vision
        self.watchdog = watchdog
        self.rules = rules or DEFAULT_RULES
        self.current_state: GameState = GameState.UNKNOWN
        self.prev_diff_gray: Optional[np.ndarray] = None
        self._unknown_saved: bool = False

    def detect_state(
        self, frame_bgr: np.ndarray, full_scan: bool = False
    ) -> Tuple[GameState, Optional[MatchResult]]:
        """Detect current state using State Graph + global popups."""
        candidates: List[GameState] = []
        if full_scan or self.current_state == GameState.UNKNOWN:
            candidates = list(self.rules.keys())
        else:
            for s in STATE_GRAPH.get(self.current_state, ()):
                if s not in candidates:
                    candidates.append(s)
            for p in GLOBAL_POPUP_STATES:
                if p not in candidates:
                    candidates.append(p)

        for state in candidates:
            rule = self.rules.get(state)
            if rule is None:
                continue
            match = self.vision.match_template(
                frame_bgr,
                rule.template_name,
                roi=rule.roi,
            )
            if match is not None:
                return state, match

        return GameState.UNKNOWN, None

    def step(self) -> float:
        """Execute one bot iteration and return recommended sleep duration."""
        frame = self.adb.screencap_bgr()
        diff, curr_small = self.vision.compute_frame_diff(self.prev_diff_gray, frame)

        # Optimization: if in-match auto and screen is barely changing, skip CV
        if (
            self.current_state == GameState.IN_MATCH_AUTO
            and diff < self.config.vision.frame_diff_idle_threshold
        ):
            self.prev_diff_gray = curr_small
            stuck = self.watchdog.evaluate(in_match=True)
            if stuck != StuckLevel.NONE:
                self.watchdog.recover(
                    stuck,
                    frame,
                    self.adb,
                    self.vision,
                    (self.config.vision.ref_width, self.config.vision.ref_height),
                    dry_run=self.config.dry_run,
                )
            return self.config.timing.match_sleep_sec

        self.prev_diff_gray = curr_small
        detected_state, match = self.detect_state(frame)

        if detected_state == GameState.UNKNOWN:
            if not self._unknown_saved:
                save_debug_frame(frame, self.config.stuck_logs_dir, "unknown_state")
                self._unknown_saved = True
            stuck = self.watchdog.evaluate(in_match=False)
            if stuck != StuckLevel.NONE:
                action = self.watchdog.recover(
                    stuck,
                    frame,
                    self.adb,
                    self.vision,
                    (self.config.vision.ref_width, self.config.vision.ref_height),
                    dry_run=self.config.dry_run,
                )
                logger.info("Watchdog recovery executed: %s", action)
            return self.config.timing.menu_sleep_sec

        self._unknown_saved = False
        if detected_state != self.current_state:
            logger.info(
                "State transition: %s -> %s",
                self.current_state.name,
                detected_state.name,
            )
            self.current_state = detected_state
            self.watchdog.reset()

        rule = self.rules[detected_state]
        if rule.is_passive or match is None:
            return self.config.timing.match_sleep_sec

        tap_x = match.center_x + rule.tap_offset[0]
        tap_y = match.center_y + rule.tap_offset[1]
        logger.info(
            "[%s] Matched %s (%.2f) -> tap(%d, %d)",
            detected_state.name,
            match.name,
            match.score,
            tap_x,
            tap_y,
        )

        if self.config.dry_run:
            return self.config.timing.menu_sleep_sec

        self.adb.tap(tap_x, tap_y)
        time.sleep(self.config.timing.action_verify_wait_sec)

        after_frame = self.adb.screencap_bgr()
        verify_diff, after_small = self.vision.compute_frame_diff(curr_small, after_frame)
        self.prev_diff_gray = after_small
        changed = verify_diff >= self.config.vision.action_verify_diff_threshold
        self.watchdog.record_tap_outcome(changed)

        return self.config.timing.menu_sleep_sec

    def run_forever(self) -> None:
        logger.info("Starting GameBot loop (dry_run=%s)...", self.config.dry_run)
        try:
            while True:
                try:
                    sleep_sec = self.step()
                    time.sleep(sleep_sec)
                except ADBConnectionError as exc:
                    logger.warning(
                        "ADB connection interrupted (%s). Waiting 5s before reconnect...",
                        exc,
                    )
                    time.sleep(5.0)
                    try:
                        self.adb.reconnect()
                    except ADBConnectionError as rec_exc:
                        logger.warning("Reconnect still failing: %s", rec_exc)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (Ctrl+C).")
