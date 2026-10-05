"""Unit tests for detection policy (no GPU / model required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))

from detection_policy import (  # noqa: E402
    Decision,
    SessionTracker,
    decide,
    map_raw_to_category,
)


def test_coco_remote_not_ufm():
    assert map_raw_to_category("remote", model_mode="coco") is None
    d, cat = decide(raw_label="remote", confidence=0.99, model_mode="coco")
    assert d == Decision.IGNORE
    assert cat is None


def test_coco_cell_phone_maps():
    assert map_raw_to_category("cell phone", model_mode="coco") == "mobile_phone"


def test_generic_watch_not_smart_under_coco():
    assert map_raw_to_category("watch", model_mode="coco") is None
    assert map_raw_to_category("wristwatch", model_mode="coco") is None


def test_normal_watch_allowed():
    assert map_raw_to_category("normal_watch", model_mode="custom") is None
    d, _ = decide(raw_label="normal_watch", confidence=0.99, model_mode="custom")
    assert d == Decision.IGNORE


def test_phone_confidence_bands():
    d_low, _ = decide(raw_label="cell phone", confidence=0.25, model_mode="coco")
    d_mid, _ = decide(raw_label="cell phone", confidence=0.40, model_mode="coco")
    d_hi, _ = decide(raw_label="cell phone", confidence=0.70, model_mode="coco")
    assert d_low == Decision.IGNORE
    assert d_mid == Decision.REVIEW
    assert d_hi == Decision.CONFIRM


def test_book_never_electronic_gadget():
    assert map_raw_to_category("book", model_mode="coco") == "notes_paper"
    d, cat = decide(raw_label="book", confidence=0.99, model_mode="coco")
    assert cat == "notes_paper"
    assert d == Decision.REVIEW  # COCO books are review-only, not auto-confirm


def test_unknown_label_not_gadget():
    assert map_raw_to_category("banana", model_mode="coco") is None
    d, cat = decide(raw_label="foobar_unknown", confidence=0.99, model_mode="coco")
    assert d == Decision.IGNORE
    assert cat is None


def test_large_box_phone_reclassified_as_notes():
    # Low/mid-confidence large desk-area box should not confirm as phone
    d, cat = decide(
        raw_label="cell phone",
        confidence=0.45,
        model_mode="coco",
        xyxy=(10, 10, 800, 600),
        frame_wh=(1000, 700),
    )
    assert cat == "notes_paper"
    assert d == Decision.REVIEW


def test_high_conf_closeup_phone_stays_phone():
    d, cat = decide(
        raw_label="cell phone",
        confidence=0.90,
        model_mode="coco",
        xyxy=(10, 10, 800, 600),
        frame_wh=(1000, 700),
    )
    assert cat == "mobile_phone"
    assert d == Decision.CONFIRM


def test_session_tracker_confirm_streak():
    tr = SessionTracker(confirm_frames=3, review_frames=2, cooldown_sec=0.0, stale_sec=10)
    assert (
        tr.observe(
            category="mobile_phone",
            decision=Decision.CONFIRM,
            confidence=0.9,
            bin_id="1_1",
            now=1.0,
        )
        is None
    )
    assert (
        tr.observe(
            category="mobile_phone",
            decision=Decision.CONFIRM,
            confidence=0.9,
            bin_id="1_1",
            now=1.1,
        )
        is None
    )
    assert (
        tr.observe(
            category="mobile_phone",
            decision=Decision.CONFIRM,
            confidence=0.9,
            bin_id="1_1",
            now=1.2,
        )
        == Decision.CONFIRM
    )


def test_session_tracker_cooldown_suppresses_duplicate():
    tr = SessionTracker(confirm_frames=2, review_frames=2, cooldown_sec=30.0, stale_sec=10)
    assert (
        tr.observe(
            category="mobile_phone",
            decision=Decision.CONFIRM,
            confidence=0.9,
            bin_id="2_2",
            now=10.0,
        )
        is None
    )
    assert (
        tr.observe(
            category="mobile_phone",
            decision=Decision.CONFIRM,
            confidence=0.9,
            bin_id="2_2",
            now=10.1,
        )
        == Decision.CONFIRM
    )
    # Immediate repeat must not re-emit during cooldown
    assert (
        tr.observe(
            category="mobile_phone",
            decision=Decision.CONFIRM,
            confidence=0.95,
            bin_id="2_2",
            now=10.2,
        )
        is None
    )
    assert (
        tr.observe(
            category="mobile_phone",
            decision=Decision.CONFIRM,
            confidence=0.95,
            bin_id="2_2",
            now=10.3,
        )
        is None
    )


def test_session_tracker_stale_resets_streak():
    tr = SessionTracker(confirm_frames=3, review_frames=2, cooldown_sec=0.0, stale_sec=1.0)
    assert (
        tr.observe(
            category="smart_watch",
            decision=Decision.CONFIRM,
            confidence=0.8,
            bin_id="3_3",
            now=1.0,
        )
        is None
    )
    assert (
        tr.observe(
            category="smart_watch",
            decision=Decision.CONFIRM,
            confidence=0.8,
            bin_id="3_3",
            now=1.1,
        )
        is None
    )
    # Gap > stale_sec resets — need full streak again
    assert (
        tr.observe(
            category="smart_watch",
            decision=Decision.CONFIRM,
            confidence=0.8,
            bin_id="3_3",
            now=3.0,
        )
        is None
    )
    assert (
        tr.observe(
            category="smart_watch",
            decision=Decision.CONFIRM,
            confidence=0.8,
            bin_id="3_3",
            now=3.1,
        )
        is None
    )
    assert (
        tr.observe(
            category="smart_watch",
            decision=Decision.CONFIRM,
            confidence=0.8,
            bin_id="3_3",
            now=3.2,
        )
        == Decision.CONFIRM
    )
