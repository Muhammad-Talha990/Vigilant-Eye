"""Weights resolution: COCO by default; custom only when YOLO_USE_CUSTOM=1."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))

from ufm_classes import default_custom_weights, default_coco_weights, resolve_weights  # noqa: E402


def test_default_prefers_coco(monkeypatch):
    monkeypatch.delenv("YOLO_USE_CUSTOM", raising=False)
    path, mode = resolve_weights(None)
    coco = default_coco_weights()
    if coco.is_file():
        assert mode == "coco"
        assert path == coco.resolve()
    else:
        assert mode in {"coco", "custom"}


def test_force_custom(monkeypatch):
    monkeypatch.setenv("YOLO_USE_CUSTOM", "1")
    path, mode = resolve_weights(None)
    custom = default_custom_weights()
    if custom.is_file():
        assert mode == "custom"
        assert path == custom.resolve()
