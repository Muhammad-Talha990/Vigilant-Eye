"""C31 live API verification against the running DB (minted JWT; Google auth bypass)."""
from __future__ import annotations

import json
import sys

import httpx
from sqlalchemy import func, select

from database import SessionLocal
from models.student import Student
from models.exam import Exam
from models.ufm_case import UfmCase
from models.user import User
from security import create_access_token

BASE = "http://127.0.0.1:8000"


def main() -> int:
    db = SessionLocal()
    try:
        print("=== USERS BY ROLE ===")
        users: dict[str, User] = {}
        for role in [
            "INVIGILATOR",
            "HOD",
            "DEC",
            "EXAM_DEPARTMENT",
            "UFM_COMMITTEE",
            "STUDENT",
        ]:
            rows = db.scalars(
                select(User).where(User.role == role, User.is_active.is_(True)).order_by(User.id)
            ).all()
            if not rows:
                print(f"{role}\t(none)")
                continue
            users[role] = rows[0]
            for u in rows[:3]:
                print(f"{role}\tid={u.id}\temail={u.email}")

        print("\n=== CASE STATUS COUNTS ===")
        counts = db.execute(
            select(UfmCase.status, func.count()).group_by(UfmCase.status)
        ).all()
        for s, c in sorted(counts, key=lambda x: x[0] or ""):
            print(f"{s}: {c}")

        print("\n=== SAMPLE CASES (by status) ===")
        for status in [
            "PENDING",
            "UNDER_REVIEW",
            "DEC_REVIEW",
            "EXAM_DEPARTMENT_REVIEW",
            "UFM_COMMITTEE_REVIEW",
            "APPROVED",
            "REJECTED",
        ]:
            rows = db.scalars(
                select(UfmCase)
                .where(UfmCase.status == status)
                .order_by(UfmCase.updated_at.desc())
                .limit(3)
            ).all()
            if not rows:
                print(f"{status}: (none)")
                continue
            for c in rows:
                print(
                    f"{status}\t{c.case_number}\tid={c.id}\t"
                    f"created={c.created_at}\tupdated={c.updated_at}\t"
                    f"reported_by={c.reported_by}"
                )

        if "HOD" not in users or "INVIGILATOR" not in users:
            print("FAIL: missing HOD or INVIGILATOR user")
            return 1

        tokens = {
            role: create_access_token(
                user_id=u.id, email=u.email, role=u.role
            )
            for role, u in users.items()
        }

        def get(role: str, path: str):
            r = httpx.get(
                f"{BASE}{path}",
                headers={"Authorization": f"Bearer {tokens[role]}"},
                timeout=30.0,
            )
            return r

        print("\n=== HOD API QUEUES (before create) ===")
        for label, path in [
            ("active", "/ufm-cases?scope=active"),
            ("dashboard", "/ufm-cases?scope=dashboard"),
            ("status=PENDING", "/ufm-cases?scope=dashboard&status=PENDING"),
            ("status=UNDER_REVIEW", "/ufm-cases?scope=dashboard&status=UNDER_REVIEW"),
        ]:
            r = get("HOD", path)
            body = r.json() if r.status_code == 200 else r.text
            n = len(body) if isinstance(body, list) else "?"
            print(f"HOD {label}: HTTP {r.status_code} count={n}")
            if isinstance(body, list):
                for row in body[:8]:
                    print(
                        f"  {row.get('case_number')}\t{row.get('status')}\t"
                        f"id={row.get('id')}"
                    )

        hod_active_before = get("HOD", "/ufm-cases?scope=active").json()
        before_ids = {int(x["id"]) for x in hod_active_before}
        before_n = len(hod_active_before)

        # Create new PENDING case as invigilator
        student = db.scalars(select(Student).order_by(Student.id)).first()
        exam = db.scalars(select(Exam).order_by(Exam.id)).first()
        if student is None or exam is None:
            print("FAIL: no student/exam fixtures in DB")
            return 1

        print("\n=== CREATE PENDING AS INVIGILATOR ===")
        cr = httpx.post(
            f"{BASE}/ufm-cases",
            headers={"Authorization": f"Bearer {tokens['INVIGILATOR']}"},
            json={
                "student_id": student.id,
                "exam_id": exam.id,
                "violation_type": "MOBILE_PHONE",
                "description": "C31 live verification pending case",
                "recovered_materials": ["MOBILE_PHONE"],
                "signer_name": "C31 Live Invigilator",
                "signature_ack": True,
            },
            timeout=30.0,
        )
        print(f"create HTTP {cr.status_code}")
        if cr.status_code != 201:
            print(cr.text)
            return 1
        created = cr.json()
        print(
            json.dumps(
                {
                    "id": created["id"],
                    "case_number": created["case_number"],
                    "status": created["status"],
                    "created_at": created["created_at"],
                },
                indent=2,
            )
        )
        assert created["status"] == "PENDING"
        new_id = int(created["id"])

        print("\n=== HOD SEES NEW CASE IN ACTIVE QUEUE ===")
        hod_active = get("HOD", "/ufm-cases?scope=active").json()
        after_ids = {int(x["id"]) for x in hod_active}
        print(f"active count before={before_n} after={len(hod_active)}")
        assert new_id in after_ids, "new PENDING missing from HOD active"
        assert len(hod_active) == before_n + 1
        # Existing HOD-owned cases still present
        assert before_ids.issubset(after_ids)

        pending_only = get(
            "HOD", "/ufm-cases?scope=dashboard&status=PENDING"
        ).json()
        assert new_id in {int(x["id"]) for x in pending_only}

        print("\n=== OTHER ROLES MUST NOT SEE PENDING IN ACTIVE ===")
        for role in ["DEC", "EXAM_DEPARTMENT", "UFM_COMMITTEE"]:
            if role not in tokens:
                print(f"{role}: skipped (no user)")
                continue
            rows = get(role, "/ufm-cases?scope=active").json()
            ids = {int(x["id"]) for x in rows}
            statuses = {x["status"] for x in rows}
            print(f"{role} active count={len(rows)} statuses={sorted(statuses)}")
            assert new_id not in ids, f"{role} incorrectly sees new PENDING"

        print("\n=== OPEN PROMOTES TO UNDER_REVIEW; STILL IN ACTIVE ===")
        opened = get("HOD", f"/ufm-cases/{new_id}")
        assert opened.status_code == 200
        assert opened.json()["status"] == "UNDER_REVIEW"
        still = get("HOD", "/ufm-cases?scope=active").json()
        assert new_id in {int(x["id"]) for x in still}
        pending_only2 = get(
            "HOD", "/ufm-cases?scope=dashboard&status=PENDING"
        ).json()
        assert new_id not in {int(x["id"]) for x in pending_only2}

        print("\n=== DASHBOARD COUNT ALIGNMENT ===")
        dash = get("HOD", "/ufm-cases?scope=dashboard").json()
        hod_owned = [
            x for x in dash if x["status"] in {"PENDING", "UNDER_REVIEW"}
        ]
        active = get("HOD", "/ufm-cases?scope=active").json()
        print(
            f"dashboard HOD-owned={len(hod_owned)} active={len(active)}"
        )
        assert {int(x["id"]) for x in hod_owned} == {
            int(x["id"]) for x in active
        }

        print("\nC31 LIVE VERIFY: PASS")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
