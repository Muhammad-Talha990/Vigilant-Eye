"""Source-level accessibility regression markers (acceptance gate)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"


def _read(rel: str) -> str:
    return (FE / rel).read_text(encoding="utf-8")


def test_confirm_dialog_focus_management():
    src = _read("components/ConfirmDialog.jsx")
    assert 'role="alertdialog"' in src
    assert "aria-modal" in src
    assert "Escape" in src
    assert "Tab" in src
    assert "previouslyFocused" in src or "previouslyFocused" in src
    assert ".focus()" in src


def test_sidebar_inert_when_mobile_drawer_closed():
    src = _read("components/Sidebar.jsx")
    assert "inert=" in src or "inert={" in src
    assert "aria-hidden" in src
    assert 'id="portal-sidebar"' in src


def test_header_sidebar_toggle_expanded():
    src = _read("components/Header.jsx")
    assert "aria-expanded" in src
    assert "aria-controls" in src
    assert "Open sidebar" in src
    assert "Close sidebar" in src


def test_reduced_motion_media_query_present():
    css = _read("index.css")
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


def test_case_detail_confirm_dialogs_focus_management():
    src = _read("pages/CaseDetailPage.jsx")
    assert 'role="dialog"' in src
    assert "aria-modal" in src
    assert "previouslyFocused" in src
    assert "reviewDialogRef" in src
    assert "releaseDialogRef" in src
    assert "Escape" in src
    assert "Tab" in src


def test_case_detail_signoff_input_labelled():
    src = _read("pages/CaseDetailPage.jsx")
    assert "Full name for digital sign-off" in src
    assert 'placeholder="Type your full name"' in src
    # Placeholder alone is insufficient — visible label text must wrap the input.
    idx = src.index('placeholder="Type your full name"')
    window = src[max(0, idx - 500) : idx + 40]
    assert "<label" in window
    assert "Full name for digital sign-off" in window
