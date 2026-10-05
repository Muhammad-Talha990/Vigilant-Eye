"""
C32 — Evidence download MIME types, filenames, and authorization.

  pytest -q tests/test_evidence_download_c32.py
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from evidence_download import (
    preferred_download_filename,
    resolve_evidence_media_type,
    sanitize_download_basename,
    sniff_mime_from_bytes,
)
from main import app
from models.base import Base
from models.exam import Exam
from models.exam_room import ExamRoom
from models.evidence import Evidence
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User
from security import create_access_token, hash_password

ROOT = Path(__file__).resolve().parents[2]
FE_API = ROOT / "frontend" / "src" / "services" / "api.js"


JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xd9"
)
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x00IEND\xaeB`\x82"
)
# Minimal RIFF/WEBP header (enough for sniff + non-empty file)
WEBP_BYTES = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00" + b"\x00" * 14
PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
# ISO BMFF ftyp box
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 32
TXT_BYTES = b"phase3 evidence sample\n"


@pytest.fixture()
def client_db(tmp_path):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    inv = User(
        name="C32 Inv",
        email="c32-inv@test.local",
        password_hash=hash_password("Demo@12345"),
        role="INVIGILATOR",
        is_active=True,
    )
    hod = User(
        name="C32 HOD",
        email="c32-hod@test.local",
        password_hash=hash_password("Demo@12345"),
        role="HOD",
        is_active=True,
    )
    stu = User(
        name="C32 Student",
        email="c32-stu@test.local",
        password_hash=hash_password("Demo@12345"),
        role="STUDENT",
        is_active=True,
    )
    db.add_all([inv, hod, stu])
    db.flush()

    room = ExamRoom(room_number="C32-R1", building="A", capacity=40)
    db.add(room)
    db.flush()
    student = Student(
        student_id="C32-ROLL",
        name="C32 Student",
        department="CS",
        program="BSCS",
        user_id=stu.id,
    )
    other_student = Student(
        student_id="C32-OTHER",
        name="Other",
        department="CS",
        program="BSCS",
    )
    exam = Exam(
        course_code="C32EX",
        course_name="C32 Exam",
        semester="Fall",
        exam_date=datetime(2026, 10, 5).date(),
        start_time=datetime(2026, 10, 5, 9, 0).time(),
        end_time=datetime(2026, 10, 5, 12, 0).time(),
        room_id=room.id,
    )
    db.add_all([student, other_student, exam])
    db.flush()

    case = UfmCase(
        case_number="UFM-C32-0001",
        student_id=student.id,
        exam_id=exam.id,
        reported_by=inv.id,
        violation_type="MOBILE_PHONE",
        description="C32 case",
        status="PENDING",
        created_at=datetime(2026, 10, 5, 10, 0, 0),
        updated_at=datetime(2026, 10, 5, 10, 0, 0),
        signer_name="C32 Inv",
        signed_at=datetime(2026, 10, 5, 10, 0, 0),
        signature_ack=True,
    )
    other_case = UfmCase(
        case_number="UFM-C32-0002",
        student_id=other_student.id,
        exam_id=exam.id,
        reported_by=inv.id,
        violation_type="CHEATING",
        description="other",
        status="PENDING",
        created_at=datetime(2026, 10, 5, 10, 0, 0),
        updated_at=datetime(2026, 10, 5, 10, 0, 0),
        signer_name="C32 Inv",
        signed_at=datetime(2026, 10, 5, 10, 0, 0),
        signature_ack=True,
    )
    db.add_all([case, other_case])
    db.flush()

    evidence_dir = tmp_path / "uploads" / "evidence"
    evidence_dir.mkdir(parents=True)

    def add_file(name: str, data: bytes, evidence_type: str, case_id: int) -> Evidence:
        dest = evidence_dir / name
        dest.write_bytes(data)
        # Store path relative to backend root style; patch resolver via absolute path
        row = Evidence(
            case_id=case_id,
            detection_id=None,
            evidence_type=evidence_type,
            file_path=str(dest),  # absolute — _resolve_evidence_path accepts it
            uploaded_by=inv.id,
            timestamp=datetime(2026, 10, 5, 10, 0, 0),
            created_at=datetime(2026, 10, 5, 10, 0, 0),
        )
        db.add(row)
        db.flush()
        return row

    fixtures = {
        "jpeg": add_file(
            "det1_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg", JPEG_BYTES, "SNAPSHOT", case.id
        ),
        "png": add_file(
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb_room-shot.png",
            PNG_BYTES,
            "SNAPSHOT",
            case.id,
        ),
        "webp": add_file(
            "det2_cccccccccccccccccccccccccccccccc.webp", WEBP_BYTES, "CLIP", case.id
        ),
        "pdf": add_file(
            "dddddddddddddddddddddddddddddddd_report.pdf",
            PDF_BYTES,
            "DOCUMENT",
            case.id,
        ),
        "mp4": add_file(
            "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee_clip.mp4", MP4_BYTES, "CLIP", case.id
        ),
        "txt": add_file(
            "ffffffffffffffffffffffffffffffff_phase3-verify.txt",
            TXT_BYTES,
            "DOCUMENT",
            case.id,
        ),
        "nosuffix": add_file("rawblob", JPEG_BYTES, "SNAPSHOT", case.id),
        "other": add_file(
            "gggggggggggggggggggggggggggggggg_secret.jpg",
            JPEG_BYTES,
            "SNAPSHOT",
            other_case.id,
        ),
    }
    db.commit()

    def _get_db():
        s = TestingSessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)

    def token(user: User) -> str:
        return create_access_token(
            user_id=user.id, email=user.email, role=user.role
        )

    yield {
        "client": client,
        "db": db,
        "inv": inv,
        "hod": hod,
        "stu": stu,
        "token": token,
        "fixtures": fixtures,
        "evidence_dir": evidence_dir,
    }
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _disposition_filename(header: str) -> str:
    star = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", header or "", re.I)
    if star:
        from urllib.parse import unquote

        return unquote(star.group(1).strip().strip('"'))
    quoted = re.search(r'filename\s*=\s*"([^"]+)"', header or "", re.I)
    if quoted:
        return quoted.group(1)
    plain = re.search(r"filename\s*=\s*([^;]+)", header or "", re.I)
    if plain:
        return plain.group(1).strip().strip('"')
    return ""


def test_helpers_mime_and_safe_names():
    assert sniff_mime_from_bytes(JPEG_BYTES) == "image/jpeg"
    assert sniff_mime_from_bytes(PNG_BYTES) == "image/png"
    assert sniff_mime_from_bytes(PDF_BYTES) == "application/pdf"
    assert sniff_mime_from_bytes(MP4_BYTES) == "video/mp4"
    assert sniff_mime_from_bytes(TXT_BYTES) == "text/plain"
    assert sanitize_download_basename("../etc/passwd") == "passwd"
    assert ".." not in sanitize_download_basename("../../x.jpg")
    name = preferred_download_filename(
        evidence_id=9,
        stored_path=Path("uploads/evidence/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_exam.jpg"),
        media_type="image/jpeg",
    )
    assert name == "exam.jpg"
    det = preferred_download_filename(
        evidence_id=2,
        stored_path=Path("uploads/evidence/det1_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg"),
        media_type="image/jpeg",
    )
    assert det == "evidence-2.jpg"


def test_jpeg_download_headers_and_bytes(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["jpeg"]
    r = c.get(
        f"/evidence/{fx.id}/file",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    disp = r.headers.get("content-disposition", "")
    assert "attachment" in disp.lower()
    fname = _disposition_filename(disp)
    assert fname.lower().endswith((".jpg", ".jpeg"))
    assert r.content == JPEG_BYTES
    assert r.content[:3] == b"\xff\xd8\xff"


def test_png_download(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["png"]
    r = c.get(
        f"/evidence/{fx.id}/file",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert _disposition_filename(r.headers.get("content-disposition", "")).endswith(
        ".png"
    )
    assert r.content.startswith(b"\x89PNG")


def test_webp_clip_download(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["webp"]
    r = c.get(
        f"/evidence/{fx.id}/file",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/webp")
    assert _disposition_filename(r.headers.get("content-disposition", "")).endswith(
        ".webp"
    )


def test_mp4_download(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["mp4"]
    r = c.get(
        f"/evidence/{fx.id}/file",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("video/mp4")
    assert _disposition_filename(r.headers.get("content-disposition", "")).endswith(
        ".mp4"
    )
    assert r.content[4:8] == b"ftyp"


def test_pdf_download(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["pdf"]
    r = c.get(
        f"/evidence/{fx.id}/file",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert _disposition_filename(r.headers.get("content-disposition", "")).endswith(
        ".pdf"
    )
    assert r.content.startswith(b"%PDF")


def test_txt_document_not_bin(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["txt"]
    r = c.get(
        f"/evidence/{fx.id}/file",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    fname = _disposition_filename(r.headers.get("content-disposition", ""))
    assert fname.endswith(".txt")
    assert not fname.endswith(".bin")
    assert r.content == TXT_BYTES


def test_extensionless_file_sniffed_as_jpeg(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["nosuffix"]
    r = c.get(
        f"/evidence/{fx.id}/file",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    fname = _disposition_filename(r.headers.get("content-disposition", ""))
    assert fname.endswith(".jpg")
    assert not fname.endswith(".bin")
    assert resolve_evidence_media_type(Path(fx.file_path)) == "image/jpeg"


def test_student_cannot_download_other_case_evidence(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["other"]
    r = c.get(
        f"/evidence/{fx.id}/file",
        headers=_h(client_db["token"](client_db["stu"])),
    )
    assert r.status_code == 403


def test_unauthenticated_download_rejected(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["jpeg"]
    r = c.get(f"/evidence/{fx.id}/file")
    assert r.status_code in {401, 403}


def test_malicious_filename_sanitized():
    bad = preferred_download_filename(
        evidence_id=1,
        stored_path=Path("uploads/evidence/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_../../x.jpg"),
        media_type="image/jpeg",
    )
    assert ".." not in bad
    assert "/" not in bad
    assert "\\" not in bad
    assert bad.endswith(".jpg")


def test_preview_still_inline_image(client_db):
    c = client_db["client"]
    fx = client_db["fixtures"]["jpeg"]
    r = c.get(
        f"/evidence/{fx.id}/preview",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    disp = r.headers.get("content-disposition", "")
    assert "inline" in disp.lower()
    assert r.content == JPEG_BYTES


def test_cors_exposes_content_disposition():
    main_src = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert 'expose_headers=["Content-Disposition"]' in main_src


def test_frontend_download_helpers_present():
    src = FE_API.read_text(encoding="utf-8")
    assert "filenameFromContentDisposition" in src
    assert "sniffMimeFromBytes" in src
    assert "ensureFilenameExtension" in src
    assert "text/plain" in src
    assert '".bin"' in src  # only as last-resort unknown
    assert "downloadEvidenceFile" in src
    assert "openEvidenceFile" in src
