"""Unit tests for suspicion score engine (no GPU)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))

from suspicion_score import SuspicionEngine, level_for  # noqa: E402


def test_levels():
    assert level_for(0) == "NORMAL"
    assert level_for(30) == "OBSERVE"
    assert level_for(60) == "REVIEW_REQUIRED"


def test_low_quality_face_does_not_raise_score():
    eng = SuspicionEngine()
    s0 = eng.update_head(
        track_id="t1", yaw_deg=40.0, pitch_deg=0.0, quality="low", now=1.0
    )
    assert s0["score"] == 0.0


def test_missing_yaw_no_add():
    eng = SuspicionEngine()
    s0 = eng.update_head(
        track_id="t1", yaw_deg=None, pitch_deg=None, quality="unavailable", now=1.0
    )
    assert s0["score"] == 0.0


def test_object_confirm_adds():
    eng = SuspicionEngine()
    s = eng.apply_object_event(
        track_id="t1", decision="CONFIRM", category="mobile_phone", now=1.0
    )
    assert s["score"] >= 30
