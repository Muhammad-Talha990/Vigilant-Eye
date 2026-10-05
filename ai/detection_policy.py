"""
Detection decision policy for VigilantEye live / offline pipelines.

Separates:
  - raw model labels (what YOLO actually predicted)
  - app categories (mobile_phone, smart_watch, …)
  - decision (IGNORE / REVIEW / CONFIRM)

COCO yolov8n has "cell phone" but NO normal_watch / smartwatch /
electronic_gadget classes. Mapping must not invent classes the model
cannot recognize. Ordinary watches falsely classified as cell phone /
remote are a known COCO limitation — thresholds + temporal confirmation
are mitigations only; a custom detector with normal_watch is required
for a real fix.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    IGNORE = "IGNORE"  # allowed / not actionable
    REVIEW = "REVIEW"  # ambiguous — store as unconfirmed candidate
    CONFIRM = "CONFIRM"  # high-confidence prohibited → alert + persist confirmed


# App categories (not necessarily COCO names)
PROHIBITED_CATEGORIES = frozenset(
    {
        "mobile_phone",
        "smart_watch",
        "notes_paper",
        "electronic_gadget",
        "suspicious_object",
    }
)

# Explicitly allowed future / custom classes (never UFM)
ALLOWED_CATEGORIES = frozenset(
    {
        "normal_watch",
        "non_cheating",
        "hand_normal",
        "person",
    }
)

# COCO / raw labels that must NEVER auto-map to prohibited gadgets.
# COCO has no "watch"; "remote" is a frequent false hit on watch-like shapes.
# Paper-like / stationery must never become electronic_gadget via unknown defaults.
COCO_EXCLUDE_FROM_UFM = frozenset(
    {
        "remote",
        "clock",  # wall clocks if ever present in other models
        "tv",
        "microwave",
        "oven",
        "toaster",
        "sink",
        "refrigerator",
        # Desk clutter / stationery that is NOT an electronic gadget
        "scissors",
        "toothbrush",
        "hair drier",
        "hair dryer",
        "vase",
        "cup",
        "bottle",
        "wine glass",
        "fork",
        "knife",
        "spoon",
        "bowl",
        "banana",
        "apple",
        "sandwich",
        "orange",
        "broccoli",
        "carrot",
        "hot dog",
        "pizza",
        "donut",
        "cake",
        "chair",
        "couch",
        "bed",
        "dining table",
        "toilet",
    }
)

# Per-category confidence gates (mitigations — tune on your footage).
# confirm_min: confirmed AI event → Invigilator alert (not guilt / UFM decision)
# review_min: persist as is_confirmed=False candidate
DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    # (review_min, confirm_min) — live labeling; retune on your footage
    "mobile_phone": (0.32, 0.55),
    "smart_watch": (0.35, 0.58),
    "notes_paper": (0.35, 0.62),
    "electronic_gadget": (0.40, 0.65),
    "suspicious_object": (0.45, 0.70),
}

# Consecutive frames before emit (lower = faster alerts; still filters one-frame noise)
DEFAULT_CONFIRM_FRAMES = int(os.getenv("UFM_CONFIRM_FRAMES", "3"))
DEFAULT_REVIEW_FRAMES = int(os.getenv("UFM_REVIEW_FRAMES", "2"))
DEFAULT_STALE_SEC = float(os.getenv("UFM_STREAK_STALE_SEC", "1.8"))
DEFAULT_COOLDOWN_SEC = float(os.getenv("UFM_PERSIST_COOLDOWN_SEC", "45"))


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def thresholds_for(category: str) -> tuple[float, float]:
    review_min, confirm_min = DEFAULT_THRESHOLDS.get(category, (0.55, 0.80))
    # Optional global overrides: UFM_CONF_MOBILE_PHONE_CONFIRM=0.75
    key = category.upper()
    review_min = _env_float(f"UFM_CONF_{key}_REVIEW", review_min)
    confirm_min = _env_float(f"UFM_CONF_{key}_CONFIRM", confirm_min)
    return review_min, confirm_min


def map_raw_to_category(raw_label: str, *, model_mode: str = "coco") -> str | None:
    """
    Map a raw model class name to an app category, or None if not actionable.

    Does not invent smartwatch/normal_watch under COCO — those only apply when
    the custom model actually emits those class names.
    """
    raw = (raw_label or "").strip().lower()
    if not raw:
        return None
    if raw in COCO_EXCLUDE_FROM_UFM:
        return None
    if raw in ALLOWED_CATEGORIES:
        return None  # allowed — no UFM category

    # Custom / trained names
    if raw in PROHIBITED_CATEGORIES:
        return raw
    if raw == "normal_watch":
        return None

    # COCO aliases that are intentionally prohibited in exams
    coco_phone = {"cell phone", "cellphone", "mobile phone", "phone", "handphone"}
    if raw in coco_phone:
        return "mobile_phone"

    coco_gadget = {"laptop", "keyboard", "mouse"}  # remote excluded
    if raw in coco_gadget:
        return "electronic_gadget"

    coco_notes = {"book"}
    if raw in coco_notes:
        # Books are common on desks — review-only bias via higher thresholds
        return "notes_paper"

    # Custom aliases that ONLY make sense if the model was trained for them
    if model_mode != "coco":
        smart_aliases = {
            "smartwatch",
            "smart watch",
            "smart-watch",
            "smart_watch",
        }
        if raw in smart_aliases:
            return "smart_watch"
        # Do NOT map generic "watch" / "wristwatch" → smart_watch.
        # Ordinary watches must be labeled normal_watch in a custom dataset.

    return None


def decide(
    *,
    raw_label: str,
    confidence: float,
    model_mode: str = "coco",
    xyxy: tuple[float, float, float, float] | None = None,
    frame_wh: tuple[int, int] | None = None,
) -> tuple[Decision, str | None]:
    """Return (decision, app_category|None)."""
    category = map_raw_to_category(raw_label, model_mode=model_mode)
    if category is None:
        return Decision.IGNORE, None

    # Soft geometry gate: huge desk-area "phones" are often paper sheets misread by COCO.
    # Never reclassify a strong phone prediction (close-ups fill the frame legitimately).
    if (
        category == "mobile_phone"
        and confidence < 0.55
        and xyxy is not None
        and frame_wh is not None
        and looks_like_large_paper_sheet(xyxy, frame_wh)
    ):
        # Reclassify as notes_paper review candidate, never gadget
        category = "notes_paper"

    review_min, confirm_min = thresholds_for(category)

    # Under COCO, "book" → notes_paper must not auto-CONFIRM (answer sheets / QPs).
    if model_mode == "coco" and category == "notes_paper":
        if confidence >= confirm_min:
            return Decision.REVIEW, category  # escalate only to human review
        if confidence >= review_min:
            return Decision.REVIEW, category
        return Decision.IGNORE, category

    if confidence >= confirm_min:
        return Decision.CONFIRM, category
    if confidence >= review_min:
        return Decision.REVIEW, category
    return Decision.IGNORE, category


def looks_like_large_paper_sheet(
    xyxy: tuple[float, float, float, float],
    frame_wh: tuple[int, int],
) -> bool:
    """
    Heuristic: very large, relatively flat boxes covering much of the desk area
    are more often papers than phones. Never use this alone as proof of paper.
    """
    x1, y1, x2, y2 = xyxy
    fw, fh = frame_wh
    if fw <= 1 or fh <= 1:
        return False
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    area_frac = (bw * bh) / float(fw * fh)
    aspect = bw / bh
    # Phone boxes are usually small; A4-ish sheets dominate frame area
    if area_frac >= 0.22 and 0.60 <= aspect <= 1.70:
        return True
    if area_frac >= 0.15 and bh >= fh * 0.35 and bw >= fw * 0.25:
        return True
    return False


def spatial_bin(xyxy: tuple[float, float, float, float], grid: int = 8) -> str:
    """Coarse location key so streaks don't merge unrelated boxes."""
    x1, y1, x2, y2 = xyxy
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    # Assume normalized or pixel — use relative bins via clamping after scale-free hash
    # Use absolute pixel bins in 100px steps when large, else fraction bins
    if x2 > 2 or y2 > 2:  # pixel coords
        return f"{int(cx) // 80}_{int(cy) // 80}"
    return f"{int(cx * grid)}_{int(cy * grid)}"


@dataclass
class TrackState:
    frames_confirm_level: int = 0
    frames_review_level: int = 0
    last_seen: float = 0.0
    best_conf: float = 0.0
    last_decision: Decision = Decision.IGNORE


@dataclass
class SessionTracker:
    """Per-camera temporal confirmation state."""

    confirm_frames: int = DEFAULT_CONFIRM_FRAMES
    review_frames: int = DEFAULT_REVIEW_FRAMES
    stale_sec: float = DEFAULT_STALE_SEC
    cooldown_sec: float = DEFAULT_COOLDOWN_SEC
    tracks: dict[str, TrackState] = field(default_factory=dict)
    last_emit_at: dict[str, float] = field(default_factory=dict)

    def _key(self, category: str, bin_id: str) -> str:
        return f"{category}@{bin_id}"

    def observe(
        self,
        *,
        category: str,
        decision: Decision,
        confidence: float,
        bin_id: str,
        now: float | None = None,
    ) -> Decision | None:
        """
        Update streak for this track. Returns:
          CONFIRM — ready to emit confirmed alert
          REVIEW — ready to emit review candidate
          None — still accumulating / cooldown / ignore
        """
        if decision == Decision.IGNORE or not category:
            return None

        now = now if now is not None else time.monotonic()
        key = self._key(category, bin_id)
        track = self.tracks.get(key)
        if track is None or (now - track.last_seen) > self.stale_sec:
            track = TrackState()
            self.tracks[key] = track

        track.last_seen = now
        track.best_conf = max(track.best_conf, confidence)
        track.last_decision = decision

        if decision == Decision.CONFIRM:
            track.frames_confirm_level += 1
            track.frames_review_level += 1
        elif decision == Decision.REVIEW:
            track.frames_review_level += 1
            track.frames_confirm_level = 0

        last_emit = self.last_emit_at.get(key)
        # Missing key = never emitted (do not treat default 0.0 as an emit time).
        if last_emit is not None and (now - last_emit) < self.cooldown_sec:
            return None

        if (
            decision == Decision.CONFIRM
            and track.frames_confirm_level >= self.confirm_frames
        ):
            self.last_emit_at[key] = now
            track.frames_confirm_level = 0
            track.frames_review_level = 0
            return Decision.CONFIRM

        if (
            decision == Decision.REVIEW
            and track.frames_review_level >= self.review_frames
        ):
            self.last_emit_at[key] = now
            track.frames_review_level = 0
            return Decision.REVIEW

        return None

    def prune(self, now: float | None = None) -> None:
        now = now if now is not None else time.monotonic()
        dead = [
            k
            for k, t in self.tracks.items()
            if (now - t.last_seen) > self.stale_sec * 3
        ]
        for k in dead:
            self.tracks.pop(k, None)


def annotate_detection_dict(
    *,
    raw_label: str,
    confidence: float,
    model_mode: str,
    xyxy: tuple[float, float, float, float] | None = None,
    frame_wh: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """UI / overlay payload with raw vs category vs decision."""
    decision, category = decide(
        raw_label=raw_label,
        confidence=confidence,
        model_mode=model_mode,
        xyxy=xyxy,
        frame_wh=frame_wh,
    )
    return {
        "raw_label": raw_label,
        "label": category or raw_label,
        "category": category,
        "confidence": round(confidence, 3),
        "decision": decision.value,
        "watchlist": decision in {Decision.CONFIRM, Decision.REVIEW},
        "violation_type": category.upper() if category else None,
        "xyxy": list(xyxy) if xyxy else None,
    }
