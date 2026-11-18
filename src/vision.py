"""Computer vision utilities: Frame Diff, Pixel Fingerprint, and ROI Template Matching."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np

from src.config import VisionConfig

logger = logging.getLogger(__name__)

# Normalized or reference-resolution ROI: (x1, y1, x2, y2)
ROI = Tuple[int, int, int, int]
Point = Tuple[int, int]
RGBColor = Tuple[int, int, int]
PixelCheck = Tuple[int, int, RGBColor]


@dataclass(frozen=True)
class MatchResult:
    name: str
    score: float
    center_x: int
    center_y: int


def scale_point(
    x: int,
    y: int,
    src_size: Tuple[int, int],
    dst_size: Tuple[int, int],
) -> Point:
    """Scale a coordinate from reference resolution to actual emulator resolution."""
    if src_size == dst_size:
        return int(x), int(y)
    sx = dst_size[0] / src_size[0]
    sy = dst_size[1] / src_size[1]
    return int(round(x * sx)), int(round(y * sy))


def scale_roi(
    roi: ROI,
    src_size: Tuple[int, int],
    dst_size: Tuple[int, int],
) -> ROI:
    """Scale an (x1, y1, x2, y2) ROI from reference to actual emulator resolution."""
    if src_size == dst_size:
        return roi
    x1, y1 = scale_point(roi[0], roi[1], src_size, dst_size)
    x2, y2 = scale_point(roi[2], roi[3], src_size, dst_size)
    x1 = max(0, min(x1, dst_size[0] - 1))
    y1 = max(0, min(y1, dst_size[1] - 1))
    x2 = max(x1 + 1, min(x2, dst_size[0]))
    y2 = max(y1 + 1, min(y2, dst_size[1]))
    return x1, y1, x2, y2


class TemplateStore:
    """Loads and caches downscaled grayscale templates from disk."""

    def __init__(self, templates_dir: Path, downscale_factor: float = 0.5) -> None:
        self.templates_dir = templates_dir
        self.downscale_factor = downscale_factor
        self._cache: Dict[str, np.ndarray] = {}

    def get(self, name: str) -> Optional[np.ndarray]:
        if name in self._cache:
            return self._cache[name]

        path = self.templates_dir / f"{name}.png"
        if not path.exists():
            return None

        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            logger.warning("Failed to read template image: %s", path)
            return None

        if self.downscale_factor != 1.0:
            img = cv2.resize(
                img,
                (0, 0),
                fx=self.downscale_factor,
                fy=self.downscale_factor,
                interpolation=cv2.INTER_AREA,
            )

        self._cache[name] = img
        return img

    def available_names(self) -> List[str]:
        if not self.templates_dir.exists():
            return []
        return sorted(p.stem for p in self.templates_dir.glob("*.png"))


class VisionEngine:
    """Fast CV pipeline designed for game-engine UIs on Android emulators."""

    def __init__(self, config: VisionConfig, templates: TemplateStore) -> None:
        self.config = config
        self.templates = templates

    def to_diff_gray(self, frame_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, self.config.diff_size, interpolation=cv2.INTER_AREA)

    def compute_frame_diff(
        self,
        prev_diff_gray: Optional[np.ndarray],
        curr_bgr: np.ndarray,
    ) -> Tuple[float, np.ndarray]:
        curr_small = self.to_diff_gray(curr_bgr)
        if prev_diff_gray is None or prev_diff_gray.shape != curr_small.shape:
            return 255.0, curr_small
        diff = float(np.mean(cv2.absdiff(prev_diff_gray, curr_small)))
        return diff, curr_small

    def check_pixel_fingerprint(
        self,
        frame_bgr: np.ndarray,
        checks: Iterable[PixelCheck],
        tolerance: Optional[int] = None,
    ) -> bool:
        tol = tolerance if tolerance is not None else self.config.pixel_tolerance
        h, w = frame_bgr.shape[:2]
        ref_size = (self.config.ref_width, self.config.ref_height)

        for rx, ry, expected_rgb in checks:
            x, y = scale_point(rx, ry, ref_size, (w, h))
            if not (0 <= x < w and 0 <= y < h):
                return False
            b, g, r = frame_bgr[y, x]
            if (
                abs(int(r) - expected_rgb[0]) > tol
                or abs(int(g) - expected_rgb[1]) > tol
                or abs(int(b) - expected_rgb[2]) > tol
            ):
                return False
        return True

    def match_template(
        self,
        frame_bgr: np.ndarray,
        template_name: str,
        roi: Optional[ROI] = None,
        threshold: Optional[float] = None,
    ) -> Optional[MatchResult]:
        tmpl = self.templates.get(template_name)
        if tmpl is None:
            return None

        h, w = frame_bgr.shape[:2]
        ref_size = (self.config.ref_width, self.config.ref_height)
        if roi is not None:
            x1, y1, x2, y2 = scale_roi(roi, ref_size, (w, h))
        else:
            x1, y1, x2, y2 = 0, 0, w, h

        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        scale = self.config.downscale_factor
        if scale != 1.0:
            crop_gray = cv2.resize(
                crop_gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA
            )

        if crop_gray.shape[0] < tmpl.shape[0] or crop_gray.shape[1] < tmpl.shape[1]:
            return None

        res = cv2.matchTemplate(crop_gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        min_score = threshold if threshold is not None else self.config.template_threshold
        if max_val < min_score:
            return None

        tmpl_h, tmpl_w = tmpl.shape[:2]
        cx_scaled = max_loc[0] + tmpl_w / 2.0
        cy_scaled = max_loc[1] + tmpl_h / 2.0
        cx = int(round(x1 + cx_scaled / scale))
        cy = int(round(y1 + cy_scaled / scale))

        return MatchResult(
            name=template_name,
            score=float(max_val),
            center_x=cx,
            center_y=cy,
        )


def save_debug_frame(frame_bgr: np.ndarray, output_dir: Path, prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    import time

    ts = time.strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{prefix}_{ts}.png"
    cv2.imwrite(str(path), frame_bgr)
    logger.info("Saved debug screenshot: %s", path)
    return path
