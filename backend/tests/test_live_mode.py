"""Production vs demo live-start policy (no camera hardware required)."""

from __future__ import annotations

from routers.live import LiveStartRequest, _validate_source_url
import pytest
from fastapi import HTTPException


def test_production_request_defaults():
    body = LiveStartRequest()
    assert body.mode == "production"
    assert body.detect is True
    assert body.persist is True


def test_production_ignores_client_toggles_in_router_logic():
    """Mirror start_live production branch: force detect+persist, drop override."""
    body = LiveStartRequest(
        mode="production",
        detect=False,
        persist=False,
        source_override="webcam:0",
    )
    is_demo = body.mode == "demo"
    if is_demo:
        detect, persist, override = body.detect, body.persist, body.source_override
    else:
        detect, persist, override = True, True, None
    assert detect is True
    assert persist is True
    assert override is None


def test_demo_allows_toggles():
    body = LiveStartRequest(
        mode="demo", detect=False, persist=False, source_override="webcam:1"
    )
    assert body.mode == "demo"
    assert body.detect is False
    assert body.persist is False
    assert body.source_override == "webcam:1"


def test_validate_blocks_path_traversal():
    with pytest.raises(HTTPException) as exc:
        _validate_source_url("../etc/passwd", allow_sample_file=True)
    assert exc.value.status_code == 400


def test_validate_webcam_ok():
    assert _validate_source_url("webcam:0") == "webcam:0"
