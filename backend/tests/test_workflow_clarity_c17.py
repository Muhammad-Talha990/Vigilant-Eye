"""C17 — Workflow presentation mirrors backend; Return/Forward destinations."""

from __future__ import annotations

from pathlib import Path

from workflow import WORKFLOW, next_status


FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_frontend_workflow_rules_match_backend():
    """Static mirror in workflowPresentation.js must match workflow.py."""
    text = (FRONTEND / "config" / "workflowPresentation.js").read_text(
        encoding="utf-8"
    )
    for role, actions in WORKFLOW.items():
        assert role in text
        for action, (statuses, new_status) in actions.items():
            assert action in text
            assert new_status in text
            for st in statuses:
                assert st in text


def test_return_always_goes_to_pending():
    assert next_status(role="HOD", action="RETURN", current_status="DEC_REVIEW") == "PENDING"
    assert next_status(role="DEC", action="RETURN", current_status="DEC_REVIEW") == "PENDING"
    assert (
        next_status(
            role="DEC",
            action="RETURN",
            current_status="EXAM_DEPARTMENT_REVIEW",
        )
        == "PENDING"
    )
    assert (
        next_status(
            role="EXAM_DEPARTMENT",
            action="RETURN",
            current_status="UFM_COMMITTEE_REVIEW",
        )
        == "PENDING"
    )


def test_forward_destinations():
    assert next_status(role="HOD", action="FORWARD", current_status="PENDING") == "DEC_REVIEW"
    assert (
        next_status(role="DEC", action="FORWARD", current_status="DEC_REVIEW")
        == "EXAM_DEPARTMENT_REVIEW"
    )
    assert (
        next_status(
            role="EXAM_DEPARTMENT",
            action="FORWARD",
            current_status="EXAM_DEPARTMENT_REVIEW",
        )
        == "UFM_COMMITTEE_REVIEW"
    )


def test_final_decisions():
    assert (
        next_status(
            role="UFM_COMMITTEE",
            action="APPROVE",
            current_status="UFM_COMMITTEE_REVIEW",
        )
        == "APPROVED"
    )
    assert (
        next_status(
            role="UFM_COMMITTEE",
            action="REJECT",
            current_status="UFM_COMMITTEE_REVIEW",
        )
        == "REJECTED"
    )


def test_case_detail_has_what_happens_next_panel():
    detail = (FRONTEND / "pages" / "CaseDetailPage.jsx").read_text(encoding="utf-8")
    assert "What happens next?" in detail
    assert "resolveReviewOutcome" in detail
    assert "workflowPresentation" in detail
    assert "Return always sets status to Pending" in detail
    assert "After this action" in detail
    assert "Result control:" in detail
    # Must not invent previous-reviewer-only return
    assert "previous reviewer" in detail.lower()


def test_workflow_presentation_explains_return_and_approve():
    wp = (FRONTEND / "config" / "workflowPresentation.js").read_text(
        encoding="utf-8"
    )
    assert "Pending" in wp
    assert "result hold" in wp.lower() or "On Hold" in wp
    assert "RETURN" in wp
    assert "APPROVE" in wp
    assert "does not create or release" in wp.lower() or "Does not create" in wp
