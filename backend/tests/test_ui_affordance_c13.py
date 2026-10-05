"""
C13 — clickable vs view-only UI affordance regression (source-level).

Run from backend/:
  pytest -q tests/test_ui_affordance_c13.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"


def _read(rel: str) -> str:
    return (FE / rel).read_text(encoding="utf-8")


def test_kpi_card_is_static_not_link():
    src = _read("components/KpiCard.jsx")
    assert 'data-affordance="static"' in src
    assert "portal-kpi" in src
    assert "<Link" not in src
    assert "onClick" not in src
    assert "navigate(" not in src


def test_action_nav_card_is_interactive_link_with_chevron():
    src = _read("components/ActionNavCard.jsx")
    assert 'data-affordance="interactive"' in src
    assert "portal-action-tile" in src
    assert "<Link" in src
    assert "tile-chevron" in src
    assert "tile-icon" in src
    assert "resolveActionIcon" in src


def test_css_separates_kpi_and_action_affordance():
    css = _read("index.css")
    assert ".portal-kpi" in css
    assert ".portal-kpi-value" in css
    assert ".portal-action-tile" in css
    assert ".tile-icon" in css
    assert "cursor: pointer" in css
    assert "tr.portal-table-row-interactive:hover" in css
    assert ".portal-table tbody tr:hover {" not in css


def test_action_hints_are_action_oriented():
    dash = _read("pages/DashboardHome.jsx")
    assert "Open module" not in dash
    assert "Report a new UFM incident →" in dash
    assert "Review pending cases →" in dash
    assert "Review evidence →" in dash
    assert "View audit history →" in dash
    assert "portal-action-strip-label" in dash


def test_dashboard_uses_action_nav_and_static_kpis():
    dash = _read("pages/DashboardHome.jsx")
    assert "ActionNavCard" in dash
    assert "KpiCard" in dash
    assert "portal-info-row" in dash
    assert "portal-media-nav" in dash
    assert 'className="portal-action-tile primary"' not in dash


def test_admin_dashboard_quick_actions_use_action_nav():
    admin = _read("pages/AdminDashboardPage.jsx")
    assert "ActionNavCard" in admin
    assert "KpiCard" in admin
    assert "rounded-lg border px-4 py-2 text-sm font-medium" not in admin


def test_master_data_exam_uses_button_not_row_onclick():
    md = _read("pages/MasterDataPage.jsx")
    assert "openExamDetail(e.id)" in md
    assert "cursor-pointer hover:bg-slate-50" not in md
    assert 'type="button"' in md
    assert "Open exam detail" in md


def test_evidence_rows_do_not_fake_hover_select():
    ev = _read("pages/EvidencePage.jsx")
    assert "hover:bg-slate-50/70" not in ev


def test_role_dashboard_actions_still_present():
    """C11/C12 quick actions remain reachable via ActionNavCard destinations."""
    dash_cfg = _read("config/dashboardByRole.js")
    assert 'to: "/app/cases?scope=active"' in dash_cfg
    assert 'to: "/app/cases?status=DEC_REVIEW"' in dash_cfg
    assert 'to: "/app/result-controls"' in dash_cfg
    assert 'to: "/app/clarification"' in dash_cfg
    assert "Manage Users" in _read("pages/AdminDashboardPage.jsx")

    home = _read("pages/DashboardHome.jsx")
    assert "PrimaryActions" in home
    assert "quickActionsForRole" in home


def test_c11_role_nav_still_intact():
    """C13 must not regress C11/C12 navigation cleanup."""
    nav = _read("config/navByRole.js")
    assert "INVIGILATOR_NAV_DENY_PATHS" in nav
    inv_deny = nav.split("INVIGILATOR_NAV_DENY_PATHS")[1].split(
        "HOD_NAV_DENY_PATHS"
    )[0]
    assert '"/app/master-data"' in inv_deny
    assert '"/app/students"' in inv_deny
    # C27: Reports is allowed for Invigilator (own-case scope)
    assert '"/app/reports"' not in inv_deny
    assert "Communication" in nav
    assert 'section: "Account"' in nav
