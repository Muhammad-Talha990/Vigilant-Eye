"""C32 live download header + byte verification against running API/DB."""
from __future__ import annotations

import sys

import httpx
from sqlalchemy import select

from database import SessionLocal
from models.evidence import Evidence
from models.user import User
from security import create_access_token

BASE = "http://127.0.0.1:8000"


def main() -> int:
    db = SessionLocal()
    try:
        hod = db.scalars(
            select(User).where(User.role == "HOD", User.is_active.is_(True)).order_by(User.id)
        ).first()
        assert hod is not None
        tok = create_access_token(user_id=hod.id, email=hod.email, role=hod.role)
        h = {"Authorization": f"Bearer {tok}", "Origin": "http://127.0.0.1:5173"}

        rows = db.scalars(select(Evidence).order_by(Evidence.id)).all()
        assert rows, "no evidence rows"
        print(f"checking {len(rows)} evidence rows")

        checked = {"image": False, "webp": False, "txt": False}
        for row in rows:
            r = httpx.get(f"{BASE}/evidence/{row.id}/file", headers=h, timeout=60)
            assert r.status_code == 200, (row.id, r.status_code, r.text[:200])
            ctype = (r.headers.get("content-type") or "").split(";")[0].strip()
            disp = r.headers.get("content-disposition") or ""
            expose = r.headers.get("access-control-expose-headers") or ""
            assert "attachment" in disp.lower(), (row.id, disp)
            assert "content-disposition" in expose.lower(), expose
            # Must not be generic .bin when we know the type
            assert "filename" in disp.lower()
            if ctype.startswith("image/jpeg"):
                assert r.content[:3] == b"\xff\xd8\xff"
                assert ".jpg" in disp.lower() or ".jpeg" in disp.lower()
                assert not disp.lower().endswith('.bin"')
                checked["image"] = True
            elif ctype.startswith("image/png"):
                assert r.content[:4] == b"\x89PNG"
                assert ".png" in disp.lower()
                checked["image"] = True
            elif ctype.startswith("image/webp"):
                assert r.content[8:12] == b"WEBP"
                assert ".webp" in disp.lower()
                checked["webp"] = True
            elif ctype.startswith("text/plain"):
                assert ".txt" in disp.lower()
                assert ".bin" not in disp.lower()
                checked["txt"] = True
            print(
                f"id={row.id} type={row.evidence_type} ctype={ctype} "
                f"disp={disp[:90]} bytes={len(r.content)}"
            )

        # Unauthorized
        bad = httpx.get(f"{BASE}/evidence/{rows[0].id}/file", timeout=30)
        assert bad.status_code in {401, 403}

        assert checked["image"], "no image verified"
        assert checked["webp"] or checked["txt"], "need clip or document sample"
        print("C32 LIVE VERIFY: PASS")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
