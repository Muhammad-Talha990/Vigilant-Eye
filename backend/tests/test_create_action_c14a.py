"""
C14-ACTION-ADD — Invigilator-only Create UFM Case dashboard action.

Run from backend/:
  pytest -q tests/test_create_action_c14a.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"


def _read(rel: str) -> str:
    return (FE / rel).read_text(encoding="utf-8")


def _quick_actions_src() -> str:
    return _read("config/dashboardByRole.js").split(
        "export function quickActionsForRole"
    )[1]


def _invigilator_actions_block() -> str:
    src = _quick_actions_src()
    return src.split('if (role === "INVIGILATOR")')[1].split(
        'if (role === "HOD")'
    )[0]


def _other_role_action_blocks() -> dict[str, str]:
    src = _quick_actions_src()
    return {
        "ADMINISTRATOR": src.split('if (role === "ADMINISTRATOR")')[1].split(
            'if (role === "INVIGILATOR")'
        )[0],
        "HOD": src.split('if (role === "HOD")')[1].split('if (role === "DEC")')[0],
        "DEC": src.split('if (role === "DEC")')[1].split(
            'if (role === "EXAM_DEPARTMENT")'
        )[0],
        "EXAM_DEPARTMENT": src.split('if (role === "EXAM_DEPARTMENT")')[1].split(
            'if (role === "UFM_COMMITTEE")'
        )[0],
        "UFM_COMMITTEE": src.split('if (role === "UFM_COMMITTEE")')[1].split(
            "return ["
        )[0],
        "STUDENT": src[src.rindex("return [") :],
    }


def test_invigilator_has_create_ufm_case_action_to_existing_route():
    block = _invigilator_actions_block()
    assert 'to: "/app/cases/new"' in block
    assert 'label: "Create UFM Case"' in block
    first = block.split("return [")[1].split("},")[0]
    assert "/app/cases/new" in first
    assert "Create UFM Case" in first


def test_create_ufm_case_not_on_other_role_dashboards():
    for role, block in _other_role_action_blocks().items():
        assert "Create UFM Case" not in block, role
        assert "/app/cases/new" not in block, role


def test_dashboard_primary_action_targets_create_for_invigilator():
    home = _read("pages/DashboardHome.jsx")
    assert 'role === "INVIGILATOR"' in home
    assert 'a.to === "/app/cases/new"' in home
    assert "Report a new UFM incident →" in home
    assert "Create UFM Case" not in home  # label comes from config
    # PrimaryActions selects create; no extra Link CTA to create-case on the home page
    assert 'to="/app/cases/new"' not in home
    assert home.count('"/app/cases/new"') == 2  # hint guard + primary find


def test_create_action_uses_action_nav_card_and_create_icon():
    card = _read("components/ActionNavCard.jsx")
    assert "resolveActionIcon" in card
    assert 'return "create"' in card
    assert "cases/new" in card
    assert "create ufm" in card
    assert "tile-chevron" in card
    assert 'data-affordance="interactive"' in card


def test_sidebar_still_uses_existing_report_incident_route():
    nav = _read("config/navByRole.js")
    inv = nav.split("INVIGILATOR: [")[1].split("HOD: [")[0]
    assert '{ to: "/app/cases/new", label: "Report UFM Incident" }' in inv
    assert "Create UFM Case" not in inv  # keep sidebar terminology
