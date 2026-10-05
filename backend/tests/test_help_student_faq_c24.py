"""
C24/C25 — Student Help FAQ + Profile sign-in method removal.

Run from backend/:
  pytest -q tests/test_help_student_faq_c24.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELP = (ROOT / "frontend" / "src" / "pages" / "HelpPage.jsx").read_text(
    encoding="utf-8"
)
PROFILE = (ROOT / "frontend" / "src" / "pages" / "ProfilePage.jsx").read_text(
    encoding="utf-8"
)

# C25 keeps only the first five C24 student FAQ questions.
REQUIRED_STUDENT_QUESTIONS = [
    "What can I see about my UFM case?",
    "How do I know the current status of my case?",
    "Can I submit a clarification for my case?",
    "Can I submit clarification more than once?",
    "What happens after I submit my clarification?",
]

REMOVED_C25_QUESTIONS = [
    "Why is my result/transcript showing a hold or restriction?",
    "Can I release my own result hold?",
    "Will I receive notifications about my case?",
    "Who can see my case?",
    "What should I do if I believe information in my case is incorrect?",
]


def test_student_quick_links_section_removed():
    # Entire Quick Links section is gated behind !isStudent
    assert "{!isStudent ? (" in HELP
    quick_start = HELP.index("{!isStudent ? (")
    quick_end = HELP.index(") : null}", quick_start)
    quick_block = HELP[quick_start:quick_end]
    assert "Quick links" in quick_block
    assert 'to="/app/cases"' in quick_block
    assert 'to="/app/admin/users"' in quick_block
    # Former student-only Clarification quick link is gone from the page
    assert 'to="/app/clarification"' not in HELP
    assert 'isStudent ? "My Cases"' not in HELP


def test_student_faq_keeps_first_five_only():
    faq_start = HELP.index("const STUDENT_FAQ")
    faq_end = HELP.index("const STAFF_GUIDELINES")
    faq_block = HELP[faq_start:faq_end]
    for q in REQUIRED_STUDENT_QUESTIONS:
        assert q in faq_block, f"missing FAQ: {q}"
    for q in REMOVED_C25_QUESTIONS:
        assert q not in faq_block, f"FAQ should be removed: {q}"
    assert faq_block.count("q:") == 5


def test_student_faq_remaining_answers_unchanged_markers():
    # Spot-check first-five answer content still present (not rewritten).
    assert "You cannot perform staff review actions" in HELP
    assert "Each case allows one clarification from you" in HELP
    assert "does not by itself finalize the case" in HELP
    assert "working days" not in HELP[HELP.index("const STUDENT_FAQ") : HELP.index("const STAFF_GUIDELINES")].lower()


def test_staff_and_admin_help_content_preserved():
    assert "What is digital sign-off?" in HELP
    assert "Can I open UFM cases or monitoring?" in HELP
    assert "Who can use Live Monitoring?" in HELP


def test_profile_sign_in_method_removed():
    assert "Sign-in method" not in PROFILE
    assert "Sign in Method" not in PROFILE
    # Other profile fields remain
    assert "Display name" in PROFILE
    assert "Email" in PROFILE
    assert "Portal role" in PROFILE
    assert "Account status" in PROFILE
