"""Phase 26 live lifecycle driver against Docker API + Postgres.

Run inside the API container:
  python scripts/phase26_live_lifecycle.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from sqlalchemy import select

from database import SessionLocal
from models.audit_log import AuditLog
from models.case_review import CaseReview
from models.notification import Notification
from models.result_control import ResultControl
from models.ufm_case import UfmCase
from models.user import User
from security import create_access_token

BASE = "http://127.0.0.1:8000"
CASE9 = "UFM-20260929-0009"
CASE7 = "UFM-20260929-0007"
report: dict = {"steps": [], "security": [], "email_checks": []}


def tok(u: User) -> str:
    return create_access_token(user_id=u.id, email=u.email, role=u.role)


def req(method: str, path: str, token: str | None = None, body=None):
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        BASE + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"raw": raw}
        return e.code, payload


def step(name: str, ok: bool, detail: str = "") -> None:
    report["steps"].append({"name": name, "ok": bool(ok), "detail": detail})
    print(("OK" if ok else "FAIL"), name, detail)


def main() -> int:
    db = SessionLocal()
    users: dict[str, User] = {}
    for email, key in [
        ("alonekingabdullah110@gmail.com", "hod"),
        ("decuni70@gmail.com", "dec"),
        ("examdept@demo.com", "exam"),
        ("ufm@demo.com", "ufm"),
        ("232514abdullah@gmail.com", "inv"),
        ("232514@students.au.edu.pk", "stu"),
        ("m69121848@gmail.com", "admin"),
    ]:
        u = db.scalar(select(User).where(User.email == email))
        assert u and u.is_active, f"missing/inactive {email}"
        users[key] = u
        print("USER", key, u.id, u.role, u.email)

    case9 = db.scalar(select(UfmCase).where(UfmCase.case_number == CASE9))
    case7 = db.scalar(select(UfmCase).where(UfmCase.case_number == CASE7))
    assert case9 is not None and case9.status in {
        "PENDING",
        "UNDER_REVIEW",
    }, getattr(case9, "status", None)
    assert case7 is not None and case7.status in {
        "PENDING",
        "UNDER_REVIEW",
    }, getattr(case7, "status", None)
    print("CASE9", case9.id, case9.status)
    print("CASE7", case7.id, case7.status)

    # --- Security matrix ---
    sec_tests = [
        ("stu", "GET", "/admin/users", 403, None),
        (
            "stu",
            "POST",
            f"/ufm-cases/{case9.id}/reviews",
            403,
            {
                "action": "FORWARD",
                "signer_name": "X",
                "signature_ack": True,
                "remarks": "x",
            },
        ),
        ("stu", "GET", f"/ufm-cases/{case9.id}", 403, None),
        (
            "inv",
            "POST",
            f"/ufm-cases/{case9.id}/reviews",
            403,
            {
                "action": "APPROVE",
                "signer_name": "Inv",
                "signature_ack": True,
                "remarks": "x",
            },
        ),
        ("inv", "GET", "/admin/users", 403, None),
        ("hod", "GET", "/admin/users", 403, None),
        ("dec", "GET", "/admin/users", 403, None),
        ("ufm", "GET", "/admin/users", 403, None),
        ("admin", "GET", f"/ufm-cases/{case9.id}", 403, None),
        (
            "admin",
            "POST",
            f"/ufm-cases/{case9.id}/reviews",
            403,
            {
                "action": "FORWARD",
                "signer_name": "Adm",
                "signature_ack": True,
                "remarks": "x",
            },
        ),
        (
            "hod",
            "POST",
            f"/ufm-cases/{case9.id}/reviews",
            400,
            {
                "action": "APPROVE",
                "signer_name": "HOD Test",
                "signature_ack": True,
                "remarks": "committee only",
            },
        ),
    ]
    for role, method, path, expect, body in sec_tests:
        code, payload = req(method, path, tok(users[role]), body)
        ok = code == expect
        report["security"].append(
            {
                "role": role,
                "method": method,
                "path": path,
                "expect": expect,
                "got": code,
                "ok": ok,
            }
        )
        detail = payload.get("detail") if isinstance(payload, dict) else ""
        print(
            ("OK" if ok else "FAIL"),
            "SEC",
            role,
            method,
            path,
            "expect",
            expect,
            "got",
            code,
            detail,
        )

    forged = create_access_token(
        user_id=users["stu"].id, email=users["stu"].email, role="HOD"
    )
    code, payload = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        forged,
        {
            "action": "FORWARD",
            "signer_name": "Forge",
            "signature_ack": True,
            "remarks": "x",
        },
    )
    ok = code == 403
    report["security"].append(
        {
            "role": "forged_jwt_student_as_hod",
            "method": "POST",
            "path": "/reviews",
            "expect": 403,
            "got": code,
            "ok": ok,
        }
    )
    print(
        ("OK" if ok else "FAIL"),
        "SEC forged JWT",
        code,
        payload.get("detail") if isinstance(payload, dict) else "",
    )

    # --- Clarification on case 7 ---
    code, _ = req(
        "POST",
        "/clarifications",
        tok(users["stu"]),
        {"case_id": case7.id, "statement": "   "},
    )
    step("clarify_empty_rejected", code in (400, 422), f"code={code}")

    code, _ = req(
        "POST",
        "/clarifications",
        tok(users["stu"]),
        {"case_id": case9.id, "statement": "Not my case"},
    )
    step("clarify_other_case_blocked", code == 403, f"code={code}")

    code, clar = req(
        "POST",
        "/clarifications",
        tok(users["stu"]),
        {
            "case_id": case7.id,
            "statement": (
                "Phase 26 clarification: I dispute the allegation and "
                "request fair review of my materials."
            ),
        },
    )
    step("clarify_submitted", code == 201, f"code={code} id={clar.get('id')}")

    code, _ = req(
        "POST",
        "/clarifications",
        tok(users["stu"]),
        {"case_id": case7.id, "statement": "Second attempt should fail"},
    )
    step("clarify_duplicate_blocked", code == 400, f"code={code}")

    code, _ = req(
        "POST",
        "/clarifications",
        tok(users["inv"]),
        {"case_id": case7.id, "statement": "invig try"},
    )
    step("clarify_invig_blocked", code == 403, f"code={code}")

    db.expire_all()
    hod_clar_notes = db.scalars(
        select(Notification).where(
            Notification.user_id == users["hod"].id,
            Notification.type == "CLARIFICATION",
            Notification.case_id == case7.id,
        )
    ).all()
    step(
        "clarify_hod_portal_notify",
        len(hod_clar_notes) >= 1,
        f"count={len(hod_clar_notes)}",
    )

    # --- Drive case 9 ---
    code, opened = req("GET", f"/ufm-cases/{case9.id}", tok(users["hod"]))
    step(
        "hod_open_case",
        code == 200
        and opened.get("status") in ("UNDER_REVIEW", "PENDING", "DEC_REVIEW"),
        f"status={opened.get('status')} code={code}",
    )

    code, rev = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        tok(users["hod"]),
        {
            "action": "FORWARD",
            "remarks": "Phase 26 HOD forward to DEC",
            "signer_name": "Abdullah HOD",
            "signature_ack": True,
        },
    )
    step("hod_forward", code == 201, f"code={code} action={rev.get('action')}")
    db.expire_all()
    case9 = db.get(UfmCase, case9.id)
    step("hod_forward_status", case9.status == "DEC_REVIEW", case9.status)

    code, _ = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        tok(users["dec"]),
        {
            "action": "APPROVE",
            "remarks": "no",
            "signer_name": "DEC User",
            "signature_ack": True,
        },
    )
    step("dec_approve_blocked", code == 400, f"code={code}")

    code, rev = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        tok(users["dec"]),
        {
            "action": "FORWARD",
            "remarks": "Phase 26 DEC forward to Exam Department",
            "signer_name": "DEC Officer",
            "signature_ack": True,
        },
    )
    step("dec_forward", code == 201, f"code={code}")
    db.expire_all()
    case9 = db.get(UfmCase, case9.id)
    step(
        "dec_forward_status",
        case9.status == "EXAM_DEPARTMENT_REVIEW",
        case9.status,
    )

    code, rev = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        tok(users["exam"]),
        {
            "action": "FORWARD",
            "remarks": "Phase 26 Exam Dept forward to UFM Committee",
            "signer_name": "Exam Department Officer",
            "signature_ack": True,
        },
    )
    step("exam_forward", code == 201, f"code={code}")
    db.expire_all()
    case9 = db.get(UfmCase, case9.id)
    step(
        "exam_forward_status",
        case9.status == "UFM_COMMITTEE_REVIEW",
        case9.status,
    )

    code, _ = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        tok(users["hod"]),
        {
            "action": "FORWARD",
            "remarks": "skip",
            "signer_name": "HOD",
            "signature_ack": True,
        },
    )
    step("hod_skip_committee_blocked", code == 400, f"code={code}")

    code, rev = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        tok(users["ufm"]),
        {
            "action": "APPROVE",
            "remarks": "Phase 26 UFM Committee decision: allegation sustained",
            "signer_name": "UFM Committee Chair",
            "signature_ack": True,
        },
    )
    step("ufm_approve", code == 201, f"code={code}")
    db.expire_all()
    case9 = db.get(UfmCase, case9.id)
    step("ufm_approve_status", case9.status == "APPROVED", case9.status)

    code, _ = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        tok(users["ufm"]),
        {
            "action": "APPROVE",
            "remarks": "again",
            "signer_name": "UFM Committee Chair",
            "signature_ack": True,
        },
    )
    step("ufm_duplicate_approve_blocked", code == 400, f"code={code}")

    hold = db.scalar(
        select(ResultControl).where(ResultControl.case_id == case9.id)
    )
    step(
        "auto_result_hold",
        hold is not None and hold.result_status == "HELD",
        f"hold={None if not hold else (hold.id, hold.result_status, hold.transcript_status)}",
    )

    code, _ = req(
        "PATCH", f"/result-controls/{hold.id}/release", tok(users["hod"])
    )
    step("hod_release_blocked", code == 403, f"code={code}")
    code, _ = req(
        "PATCH", f"/result-controls/{hold.id}/release", tok(users["stu"])
    )
    step("stu_release_blocked", code == 403, f"code={code}")
    code, _ = req(
        "PATCH", f"/result-controls/{hold.id}/release", tok(users["inv"])
    )
    step("inv_release_blocked", code == 403, f"code={code}")

    code, released = req(
        "PATCH", f"/result-controls/{hold.id}/release", tok(users["exam"])
    )
    step(
        "exam_release",
        code == 200 and released.get("result_status") == "RELEASED",
        f"code={code} status={released.get('result_status')}",
    )
    code, _ = req(
        "PATCH", f"/result-controls/{hold.id}/release", tok(users["exam"])
    )
    step("exam_release_duplicate_blocked", code == 400, f"code={code}")

    code, reviews = req(
        "GET", f"/ufm-cases/{case9.id}/reviews", tok(users["ufm"])
    )
    step(
        "committee_sees_reviews",
        code == 200 and isinstance(reviews, list) and len(reviews) >= 4,
        f"code={code} n={len(reviews) if isinstance(reviews, list) else None}",
    )
    code, _ = req(
        "GET", f"/ufm-cases/{case7.id}/reviews", tok(users["stu"])
    )
    step("student_reviews_forbidden", code == 403, f"code={code}")

    code, own = req("GET", f"/ufm-cases/{case7.id}", tok(users["stu"]))
    step(
        "student_own_case",
        code == 200,
        f"code={code} status={own.get('status')}",
    )

    db.expire_all()
    notes = db.scalars(
        select(Notification)
        .where(Notification.case_id == case9.id)
        .order_by(Notification.id)
    ).all()
    print("CASE9_NOTIFICATIONS", len(notes))
    for n in notes:
        print(
            "  N",
            n.id,
            n.user_id,
            n.type,
            n.title,
            getattr(n, "email_status", None),
            getattr(n, "email_to", None),
        )
        report["email_checks"].append(
            {
                "id": n.id,
                "user_id": n.user_id,
                "type": n.type,
                "email_status": getattr(n, "email_status", None),
                "email_to": getattr(n, "email_to", None),
            }
        )

    audits = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "ufm_case")
        .order_by(AuditLog.id)
    ).all()
    audits = [
        a
        for a in audits
        if str(a.entity_id) == str(case9.id)
        or (a.description or "").find(CASE9) >= 0
    ]
    print("CASE9_AUDITS", len(audits))
    for a in audits:
        print("  A", a.id, a.action, a.user_id, (a.description or "")[:90])
    step("audit_trail_present", len(audits) >= 4, f"n={len(audits)}")

    revs = db.scalars(
        select(CaseReview)
        .where(CaseReview.case_id == case9.id)
        .order_by(CaseReview.id)
    ).all()
    step(
        "four_reviews",
        len(revs) == 4,
        f"n={len(revs)} actions={[r.action for r in revs]}",
    )

    code, _ = req(
        "POST",
        f"/ufm-cases/{case9.id}/reviews",
        tok(users["inv"]),
        {
            "action": "REJECT",
            "remarks": "no",
            "signer_name": "Inv",
            "signature_ack": True,
        },
    )
    step("inv_cannot_alter_decision", code == 403, f"code={code}")

    fails = [s for s in report["steps"] if not s["ok"]] + [
        s for s in report["security"] if not s["ok"]
    ]
    print("SUMMARY_FAILS", len(fails))
    for f in fails:
        print("  FAIL_DETAIL", f)
    print("PHASE26_LIVE_DONE", "PASS" if not fails else "FAIL")
    db.close()
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
