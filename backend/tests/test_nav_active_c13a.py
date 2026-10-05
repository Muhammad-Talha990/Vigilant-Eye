"""
C13-ACTIVE-STATE-FIX — query-aware sidebar active matching.

Run from backend/:
  pytest -q tests/test_nav_active_c13a.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
NAV_ACTIVE = FE / "src" / "config" / "navActive.js"
SIDEBAR = FE / "src" / "components" / "Sidebar.jsx"
NAV_BY_ROLE = FE / "src" / "config" / "navByRole.js"


def _eval_matrix(cases: list[dict]) -> list[bool]:
    """Execute isSidebarNavActive via Node against the real module."""
    if shutil.which("node") is None:
        pytest.skip("node is required for navActive.js evaluation")
    payload = json.dumps(cases)
    # Relative import from frontend/ cwd (Windows-safe; avoid raw drive paths).
    script = f"""
import {{ isSidebarNavActive }} from './src/config/navActive.js';
const cases = {payload};
const out = cases.map((c) =>
  isSidebarNavActive({{ pathname: c.pathname, search: c.search || "" }}, c.to)
);
process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=str(FE),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout or "node failed")
    return json.loads(proc.stdout)


def test_sidebar_uses_query_aware_helper():
    src = SIDEBAR.read_text(encoding="utf-8")
    assert "isSidebarNavActive" in src
    assert "data-nav-active" in src
    assert "useLocation" in src
    assert "from \"react-router-dom\"" in src
    # Use Link (not NavLink) so aria-current is not overridden by pathname-only matching
    assert "NavLink" not in src
    assert "<Link" in src


def test_hod_cases_for_review_not_all_cases():
    results = _eval_matrix(
        [
            {
                "pathname": "/app/cases",
                "search": "?scope=active",
                "to": "/app/cases?scope=active",
            },
            {
                "pathname": "/app/cases",
                "search": "?scope=active",
                "to": "/app/cases",
            },
            {
                "pathname": "/app/cases",
                "search": "",
                "to": "/app/cases?scope=active",
            },
            {
                "pathname": "/app/cases",
                "search": "",
                "to": "/app/cases",
            },
        ]
    )
    assert results == [True, False, False, True]


def test_dec_exam_ufm_filtered_siblings():
    results = _eval_matrix(
        [
            # DEC
            {
                "pathname": "/app/cases",
                "search": "?status=DEC_REVIEW",
                "to": "/app/cases?status=DEC_REVIEW",
            },
            {
                "pathname": "/app/cases",
                "search": "?status=DEC_REVIEW",
                "to": "/app/cases",
            },
            # Exam Department — two filters
            {
                "pathname": "/app/cases",
                "search": "?status=EXAM_DEPARTMENT_REVIEW",
                "to": "/app/cases?status=EXAM_DEPARTMENT_REVIEW",
            },
            {
                "pathname": "/app/cases",
                "search": "?status=EXAM_DEPARTMENT_REVIEW",
                "to": "/app/cases?status=UFM_COMMITTEE_REVIEW",
            },
            {
                "pathname": "/app/cases",
                "search": "?status=EXAM_DEPARTMENT_REVIEW",
                "to": "/app/cases",
            },
            # UFM Committee
            {
                "pathname": "/app/cases",
                "search": "?status=APPROVED",
                "to": "/app/cases?status=APPROVED",
            },
            {
                "pathname": "/app/cases",
                "search": "?status=APPROVED",
                "to": "/app/cases?status=REJECTED",
            },
            {
                "pathname": "/app/cases",
                "search": "?status=APPROVED",
                "to": "/app/cases",
            },
            {
                "pathname": "/app/cases",
                "search": "",
                "to": "/app/cases",
            },
        ]
    )
    assert results == [
        True,
        False,
        True,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


def test_case_detail_does_not_activate_filtered_or_all_cases():
    """Preserve prior end= behavior: detail is not the list view."""
    results = _eval_matrix(
        [
            {
                "pathname": "/app/cases/42",
                "search": "",
                "to": "/app/cases",
            },
            {
                "pathname": "/app/cases/42",
                "search": "",
                "to": "/app/cases?scope=active",
            },
            {
                "pathname": "/app/cases/new",
                "search": "",
                "to": "/app/cases",
            },
        ]
    )
    assert results == [False, False, False]


def test_nav_by_role_still_uses_status_query_destinations():
    nav = NAV_BY_ROLE.read_text(encoding="utf-8")
    # HOD review queue uses C22 scope=active (PENDING + UNDER_REVIEW).
    assert "/app/cases?scope=active" in nav
    assert "/app/cases?status=PENDING" not in nav
    assert "/app/cases?status=DEC_REVIEW" in nav
    assert "/app/cases?status=EXAM_DEPARTMENT_REVIEW" in nav
    assert "/app/cases?status=UFM_COMMITTEE_REVIEW" in nav
    assert "/app/cases?status=APPROVED" in nav
    assert "/app/cases?status=REJECTED" in nav
