"""
VigilantEye custom UFM detector classes + weight resolution.

Maps YOLO labels (custom or limited COCO aliases) -> portal categories.
Ordinary watches are NOT mapped to smart_watch (COCO cannot tell them apart).
"""

from __future__ import annotations

from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent

# Target custom-detector vocabulary (train for these — do not invent under COCO)
UFM_CLASS_NAMES = [
    "mobile_phone",
    "smart_watch",
    "normal_watch",  # ALLOWED — required to stop watch↔phone confusion
    "notes_paper",
    "electronic_gadget",
    "suspicious_object",
]

# Custom YOLO class name -> backend violation_type (normal_watch has none)
CLASS_TO_VIOLATION = {
    "mobile_phone": "MOBILE_PHONE",
    "smart_watch": "SMART_WATCH",
    "notes_paper": "NOTES_PAPER",
    "electronic_gadget": "ELECTRONIC_GADGET",
    "suspicious_object": "SUSPICIOUS_OBJECT",
}

# Allowed custom classes (never violation)
ALLOWED_CLASS_NAMES = {
    "normal_watch",
    "non_cheating",
    "hand_normal",
}

# COCO aliases that are safe to treat as prohibited exam items.
# Intentionally OMITTED: remote, watch, wristwatch, clock — false-positive sources.
COCO_ALIASES_TO_CLASS = {
    "cell phone": "mobile_phone",
    "cellphone": "mobile_phone",
    "mobile phone": "mobile_phone",
    "phone": "mobile_phone",
    "handphone": "mobile_phone",
    "laptop": "electronic_gadget",
    "keyboard": "electronic_gadget",
    "mouse": "electronic_gadget",
    "book": "notes_paper",
}

# Custom-model-only aliases (ignored under COCO mode by detection_policy)
CUSTOM_ALIASES_TO_CLASS = {
    "smartwatch": "smart_watch",
    "smart watch": "smart_watch",
    "smart-watch": "smart_watch",
}

VIOLATION_TO_CLASS = {v: k for k, v in CLASS_TO_VIOLATION.items()}

UFM_WATCHLIST_LABELS = set(CLASS_TO_VIOLATION.keys()) | set(
    COCO_ALIASES_TO_CLASS.keys()
)


def normalize_label(raw: str, *, model_mode: str = "coco") -> str:
    """
    Map raw YOLO name -> app class name when possible; otherwise return raw.
    Does not map generic 'watch' to smart_watch.
    """
    key = (raw or "").strip().lower()
    if key in CLASS_TO_VIOLATION or key in ALLOWED_CLASS_NAMES:
        return key
    if key in COCO_ALIASES_TO_CLASS:
        return COCO_ALIASES_TO_CLASS[key]
    if model_mode != "coco" and key in CUSTOM_ALIASES_TO_CLASS:
        return CUSTOM_ALIASES_TO_CLASS[key]
    return key


def to_violation_type(raw_label: str, *, model_mode: str = "coco") -> str | None:
    normalized = normalize_label(raw_label, model_mode=model_mode)
    if normalized in ALLOWED_CLASS_NAMES:
        return None
    if normalized in CLASS_TO_VIOLATION:
        return CLASS_TO_VIOLATION[normalized]
    upper = (raw_label or "").strip().upper()
    if upper in VIOLATION_TO_CLASS:
        return upper
    return None


def is_ufm_watchlist(raw_label: str, *, model_mode: str = "coco") -> bool:
    """True if label can become a UFM candidate (still subject to policy thresholds)."""
    from detection_policy import decide, Decision

    decision, _ = decide(raw_label=raw_label, confidence=1.0, model_mode=model_mode)
    return decision != Decision.IGNORE


def default_custom_weights() -> Path:
    return AI_ROOT / "runs" / "train" / "ufm_custom" / "weights" / "best.pt"


def default_coco_weights() -> Path:
    return AI_ROOT / "weights" / "yolov8n.pt"


def resolve_weights(explicit: str | None = None) -> tuple[Path, str]:
    """
    Pick weights for live / offline inference.

    Default: COCO yolov8n (reliable phone / book / laptop on exam footage).
    Custom best.pt is only used when YOLO_USE_CUSTOM=1 — the current
    ufm_custom checkpoint often returns empty predictions on real samples.

    Returns (path, mode) where mode is 'explicit' | 'custom' | 'coco'.
    """
    import os

    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path.resolve(), "explicit"
        raise FileNotFoundError(f"Weights not found: {path}")

    flag = os.getenv("YOLO_USE_CUSTOM", "").strip().lower()
    prefer_custom = flag in {"1", "true", "yes"}

    custom = default_custom_weights()
    coco = default_coco_weights()

    if prefer_custom and custom.is_file():
        return custom.resolve(), "custom"
    if coco.is_file():
        return coco.resolve(), "coco"
    if custom.is_file():
        return custom.resolve(), "custom"
    return coco.resolve(), "coco"
