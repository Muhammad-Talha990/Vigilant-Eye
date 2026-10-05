"""Phase 19 runtime regression — nav/home must not fall back to INVIGILATOR."""

from __future__ import annotations

from pathlib import Path

import pytest


def _read_nav_file() -> str | None:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "frontend" / "src" / "config" / "navByRole.js",
        here.parents[3] / "Vigilant Eye" / "frontend" / "src" / "config" / "navByRole.js",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


def test_administrator_nav_block_excludes_operational_links():
    text = _read_nav_file()
    if text is None:
        pytest.skip("frontend navByRole.js not available in this environment")
    start = text.index("ADMINISTRATOR: [")
    end = text.index("INVIGILATOR: [", start)
    block = text[start:end]
    for forbidden in (
        "Live Monitoring",
        "Detections & Alerts",
        "My Cases",
        "Report UFM Incident",
        "Evidence Library",
        "Exam Setup",
        "/app/monitoring",
        "/app/detections",
        "/app/cases",
        "/app/evidence",
        "/app/master-data",
        "/app/reports",
    ):
        assert forbidden not in block, forbidden
    assert "/app/admin/dashboard" in block
    assert "/app/admin/users" in block
    assert "Audit Log" in block


def test_get_nav_for_role_no_invigilator_fallback():
    text = _read_nav_file()
    if text is None:
        pytest.skip("frontend navByRole.js not available in this environment")
    assert "NAV_BY_ROLE.INVIGILATOR" not in text.split("export function getNavForRole")[-1]
    assert "return [];" in text.split("export function getNavForRole")[-1]


def test_role_home_administrator():
    path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "config" / "roleHome.js"
    if not path.is_file():
        pytest.skip("roleHome.js not available")
    text = path.read_text(encoding="utf-8")
    assert 'role === "ADMINISTRATOR"' in text
    assert "/app/admin/dashboard" in text


def test_other_roles_still_have_dedicated_nav():
    text = _read_nav_file()
    if text is None:
        pytest.skip("frontend navByRole.js not available")
    for role, marker in (
        ("HOD", "Cases for Review"),
        ("INVIGILATOR", "Live Monitoring"),
        ("STUDENT", "Help and Guidance"),
    ):
        start = text.index(f"{role}: [")
        # end at next top-level role key or closing of NAV_BY_ROLE
        nxt = None
        for other in ("INVIGILATOR", "HOD", "DEC", "EXAM_DEPARTMENT", "UFM_COMMITTEE", "STUDENT"):
            if other == role:
                continue
            try:
                idx = text.index(f"{other}: [", start + 1)
            except ValueError:
                continue
            if nxt is None or idx < nxt:
                nxt = idx
        block = text[start : nxt or len(text)]
        assert marker in block
