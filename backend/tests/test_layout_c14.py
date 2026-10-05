"""
C14 — global layout / responsive table structure regression (source-level).

Run from backend/:
  pytest -q tests/test_layout_c14.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"


def _read(rel: str) -> str:
    return (FE / rel).read_text(encoding="utf-8")


def test_shared_portal_split_and_col_hide_tokens():
    css = _read("index.css")
    assert ".portal-split" in css
    assert ".portal-split-detail" in css
    assert ".portal-data-cards" in css
    assert ".portal-table-desktop" in css
    assert ".col-hide-sm" in css
    assert ".col-hide-md" in css
    assert ".col-hide-lg" in css
    assert ".cell-wrap" in css
    assert "minmax(14rem, 16.5rem)" in css
    assert "@media (min-width: 1440px)" in css
    # Tablet/desktop card↔table switch (acceptance gate): cards until 1280px
    assert "@media (min-width: 1280px)" in css
    assert (
        ".portal-table-desktop {\n  display: none;\n}" in css
        or ".portal-table-desktop {\r\n  display: none;\r\n}" in css
    )
    switch_block = css.split("Mobile/tablet data cards")[1].split(
        ".portal-case-card {"
    )[0]
    assert "@media (min-width: 1280px)" in switch_block
    assert "display: block" in switch_block


def test_page_shell_uses_consistent_max_width():
    shell = _read("components/PageShell.jsx")
    assert "max-w-7xl" in shell
    assert "max-w-3xl" in shell
    assert "mx-auto w-full" in shell


def test_evidence_page_uses_responsive_split_not_fixed_panel():
    src = _read("pages/EvidencePage.jsx")
    assert "portal-split" in src
    assert "portal-split-detail" in src
    assert "portal-data-cards" in src
    assert "portal-table-desktop" in src
    assert "lg:grid-cols-[minmax(0,1fr)_20rem]" not in src
    assert 'minWidth: "760px"' not in src
    assert "style={{ minWidth:" not in src
    assert "File name" in src
    assert "Evidence detail" in src


def test_evidence_default_table_keeps_priority_columns():
    src = _read("pages/EvidencePage.jsx")
    assert "<th>ID</th>" in src
    assert "<th>Case</th>" in src
    assert "<th>Type</th>" in src
    assert "<th>Source</th>" in src
    assert "<th>Actions</th>" in src
    # Secondary metadata lives in detail panel, not default wide table
    assert "<th>File</th>" not in src
    assert "<th>Uploaded by</th>" not in src


def test_case_tables_use_mobile_cards_and_col_hide():
    queue = _read("components/CaseQueueTable.jsx")
    cases = _read("pages/CasesPage.jsx")
    for src in (queue, cases):
        assert "portal-case-cards" in src or "portal-data-cards" in src
        assert "portal-table-desktop" in src
        assert "col-hide" in src
        assert "min-w-[640px]" not in src


def test_audit_and_holds_drop_hard_min_widths():
    audit = _read("pages/AuditTrailPage.jsx")
    holds = _read("pages/ResultControlsPage.jsx")
    assert 'minWidth: "860px"' not in audit
    assert 'minWidth: "900px"' not in holds
    assert "portal-data-cards" in audit
    assert "portal-data-cards" in holds
    assert "portal-table-desktop" in audit
    assert "portal-table-desktop" in holds
    assert "<details" in audit


def test_app_layout_hides_page_level_x_overflow():
    layout = _read("components/AppLayout.jsx")
    assert "overflow-x-hidden" in layout


def test_notifications_use_portal_split():
    src = _read("pages/NotificationsPage.jsx")
    assert "portal-split" in src
    assert "portal-split-detail" in src
    assert "minmax(280px,360px)" not in src


def test_detections_and_admin_users_responsive():
    det = _read("pages/DetectionsPage.jsx")
    users = _read("pages/AdminUsersPage.jsx")
    assert "portal-data-cards" in det
    assert "portal-table-desktop" in det
    assert "flex flex-wrap gap-x-2" in det
    assert "portal-data-cards" in users
    assert "portal-table-desktop" in users
    assert "col-hide-md" in users
