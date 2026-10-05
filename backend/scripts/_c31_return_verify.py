"""C31 return-to-PENDING reappears in HOD active queue (live DB)."""
from __future__ import annotations

import sys

import httpx
from sqlalchemy import select

from database import SessionLocal
from models.ufm_case import UfmCase
from models.user import User
from security import create_access_token

BASE = "http://127.0.0.1:8000"


def token_for(db, role: str) -> str:
    u = db.scalars(
        select(User).where(User.role == role, User.is_active.is_(True)).order_by(User.id)
    ).first()
    assert u is not None, role
    return create_access_token(user_id=u.id, email=u.email, role=u.role)


def main() -> int:
    db = SessionLocal()
    try:
        hod = token_for(db, "HOD")
        dec = token_for(db, "DEC")
        # Use an UNDER_REVIEW case if present; else open a PENDING one.
        case = db.scalars(
            select(UfmCase)
            .where(UfmCase.status == "UNDER_REVIEW")
            .order_by(UfmCase.id.desc())
        ).first()
        if case is None:
            case = db.scalars(
                select(UfmCase)
                .where(UfmCase.status == "PENDING")
                .order_by(UfmCase.id.desc())
            ).first()
        assert case is not None, "no HOD-owned case to forward/return"
        case_id = case.id
        print(f"using case id={case_id} status={case.status} number={case.case_number}")

        def h(tok):
            return {"Authorization": f"Bearer {tok}"}

        # Ensure UNDER_REVIEW via HOD open if still PENDING
        r = httpx.get(f"{BASE}/ufm-cases/{case_id}", headers=h(hod), timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "UNDER_REVIEW"

        # Forward to DEC
        r = httpx.post(
            f"{BASE}/ufm-cases/{case_id}/reviews",
            headers=h(hod),
            json={
                "action": "FORWARD",
                "remarks": "C31 live return check forward",
                "signer_name": "C31 HOD",
                "signature_ack": True,
            },
            timeout=30,
        )
        assert r.status_code == 201, r.text
        print("forwarded → DEC_REVIEW")

        hod_active = {
            int(x["id"])
            for x in httpx.get(
                f"{BASE}/ufm-cases?scope=active", headers=h(hod), timeout=30
            ).json()
        }
        assert case_id not in hod_active
        dec_active = {
            int(x["id"])
            for x in httpx.get(
                f"{BASE}/ufm-cases?scope=active", headers=h(dec), timeout=30
            ).json()
        }
        assert case_id in dec_active

        # DEC return → PENDING (do not HOD-GET yet — that promotes to UNDER_REVIEW)
        r = httpx.post(
            f"{BASE}/ufm-cases/{case_id}/reviews",
            headers=h(dec),
            json={
                "action": "RETURN",
                "remarks": "C31 live return check return",
                "signer_name": "C31 DEC",
                "signature_ack": True,
            },
            timeout=30,
        )
        assert r.status_code == 201, r.text

        pending_check = httpx.get(
            f"{BASE}/ufm-cases?scope=dashboard&status=PENDING",
            headers=h(hod),
            timeout=30,
        ).json()
        assert case_id in {int(x["id"]) for x in pending_check}
        hod_active = {
            int(x["id"])
            for x in httpx.get(
                f"{BASE}/ufm-cases?scope=active", headers=h(hod), timeout=30
            ).json()
        }
        assert case_id in hod_active, "returned PENDING missing from HOD active"
        dec_active = {
            int(x["id"])
            for x in httpx.get(
                f"{BASE}/ufm-cases?scope=active", headers=h(dec), timeout=30
            ).json()
        }
        assert case_id not in dec_active
        print("C31 RETURN LIVE VERIFY: PASS")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
