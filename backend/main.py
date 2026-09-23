import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from case_enrich import enrich_case
from database import engine, get_db
from deps import get_current_user, require_roles
from detection_bridge import create_draft_case_from_detection
from evidence_auto import attach_detection_evidence_to_case, video_file_to_animated_webp
from models.audit_log import AuditLog  # registers audit_logs table on Base
from models.base import Base
from models.camera import Camera  # registers cameras table on Base
from models.case_review import CaseReview  # registers case_reviews table on Base
from models.clarification import Clarification  # registers clarifications table on Base
from models.detection import Detection  # registers detections table on Base
from models.exam import Exam  # registers exams table on Base
from models.exam_room import ExamRoom  # registers exam_rooms table on Base
from models.evidence import Evidence  # registers evidence table on Base
from models.notification import Notification  # registers notifications table on Base
from models.result_control import ResultControl  # registers result_controls table on Base
from models.student import Student  # registers students table on Base
from models.ufm_case import UfmCase  # registers ufm_cases table on Base
from models.user import User
from notify_helpers import (
    create_notification,
    notify_student_for_case,
    notify_users_with_role,
)
from notification_enrich import enrich_notification
from schemas.audit_log import AuditLogOut
from schemas.auth import LoginRequest, LoginResponse
from schemas.camera import CameraCreate, CameraOut
from schemas.case_review import CaseReviewCreate, CaseReviewOut
from schemas.clarification import ClarificationCreate, ClarificationOut
from schemas.detection import DetectionOut, DraftCaseFromDetection
from schemas.exam import ExamCreate, ExamOut
from schemas.exam_room import ExamRoomCreate, ExamRoomOut
from schemas.evidence import EvidenceOut
from schemas.notification import NotificationOut
from schemas.result_control import ResultControlCreate, ResultControlOut
from schemas.student import StudentCreate, StudentLinkUser, StudentOut
from schemas.ufm_case import UfmCaseCreate, UfmCaseOut
from schemas.user import UserCreate, UserOut
from security import create_access_token, hash_password, verify_password
from student_portal import resolve_linked_student
from routers.live import router as live_router
from routers.ws_alerts import router as ws_router
import ws_hub
from workflow import next_status

app = FastAPI(title="VigilantEye API", version="0.1.0")
app.include_router(live_router)
app.include_router(ws_router)


@app.on_event("startup")
async def _capture_loop_for_ws() -> None:
    import asyncio

    ws_hub.set_event_loop(asyncio.get_running_loop())


@app.on_event("shutdown")
def _stop_live_sessions() -> None:
    from live_stream import live_manager

    live_manager.stop_all()

# Allow local React/Vite frontend (Day 5) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

EVIDENCE_UPLOAD_DIR = Path(__file__).resolve().parent / "uploads" / "evidence"
EVIDENCE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def write_audit_log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None,
    description: str,
    user_id: int | None = None,
) -> None:
    """Save one audit trail row. Caller must commit."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
        )
    )


# After a status change, notify the role that should act next (or the reporter).
STATUS_NEXT_ROLE = {
    "PENDING": "HOD",
    "UNDER_REVIEW": "HOD",
    "DEC_REVIEW": "DEC",
    "EXAM_DEPARTMENT_REVIEW": "EXAM_DEPARTMENT",
    "UFM_COMMITTEE_REVIEW": "UFM_COMMITTEE",
}


def _require_signoff(*, signer_name: str, signature_ack: bool) -> str:
    name = (signer_name or "").strip()
    if not signature_ack:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Digital sign-off acknowledgment is required",
        )
    if len(name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signer full name is required for digital sign-off",
        )
    return name


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "project": "VigilantEye",
    }


@app.post("/auth/login", response_model=LoginResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == credentials.email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return LoginResponse(
        message="Login successful",
        access_token=create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
        ),
        token_type="bearer",
        user=user,
    )


@app.get("/auth/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Protected route: requires Authorization: Bearer <token>."""
    return current_user


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("EXAM_DEPARTMENT", "HOD", "INVIGILATOR")
    ),
):
    role = user_in.role.strip().upper()
    # Invigilators may only register STUDENT portal accounts
    if current_user.role == "INVIGILATOR" and role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invigilators can only create STUDENT portal users",
        )
    # Staff portal accounts require HOD or Exam Department
    if role != "STUDENT" and current_user.role not in {
        "HOD",
        "EXAM_DEPARTMENT",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HOD or Exam Department can create staff portal users",
        )
    allowed_roles = {
        "STUDENT",
        "INVIGILATOR",
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
    }
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Allowed: {', '.join(sorted(allowed_roles))}",
        )

    existing = db.scalar(select(User).where(User.email == user_in.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        name=user_in.name,
        email=str(user_in.email).lower(),
        password_hash=hash_password(user_in.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users", response_model=list[UserOut])
def list_users(
    role: str | None = None,
    unlinked_students_only: bool = False,
    staff_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "INVIGILATOR",
            "HOD",
            "DEC",
            "EXAM_DEPARTMENT",
            "UFM_COMMITTEE",
        )
    ),
):
    query = select(User).order_by(User.id)
    if role:
        query = query.where(User.role == role.strip().upper())
    users = list(db.scalars(query).all())

    if staff_only:
        users = [u for u in users if u.role != "STUDENT"]

    if unlinked_students_only:
        linked_ids = set(
            db.scalars(
                select(Student.user_id).where(Student.user_id.is_not(None))
            ).all()
        )
        users = [
            u for u in users if u.role == "STUDENT" and u.id not in linked_ids
        ]

    return users


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


def _validate_student_portal_user(db: Session, user_id: int | None) -> None:
    """Ensure user_id is a STUDENT role user and not already linked elsewhere."""
    if user_id is None:
        return
    portal_user = db.get(User, user_id)
    if portal_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portal user not found for user_id",
        )
    if portal_user.role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only users with role STUDENT can be linked to a student profile",
        )
    taken = db.scalar(
        select(Student).where(Student.user_id == user_id)
    )
    if taken is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"user_id already linked to student roll {taken.student_id}",
        )


@app.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(
    student_in: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("INVIGILATOR", "HOD", "EXAM_DEPARTMENT")
    ),
):
    existing = db.scalar(
        select(Student).where(Student.student_id == student_in.student_id)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student ID already registered",
        )

    _validate_student_portal_user(db, student_in.user_id)

    student = Student(
        student_id=student_in.student_id,
        name=student_in.name,
        department=student_in.department,
        program=student_in.program,
        user_id=student_in.user_id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@app.get("/students", response_model=list[StudentOut])
def list_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    students = db.scalars(select(Student).order_by(Student.id)).all()
    return students


@app.patch("/students/{student_pk}/link-user", response_model=StudentOut)
def link_student_user(
    student_pk: int,
    body: StudentLinkUser,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("HOD", "EXAM_DEPARTMENT", "INVIGILATOR")
    ),
):
    """Attach or clear the portal login for a student (replaces DEMO001 hardcode)."""
    student = db.get(Student, student_pk)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    if body.user_id is not None:
        # Allow re-linking the same student to the same user without conflict
        other = db.scalar(
            select(Student).where(
                Student.user_id == body.user_id,
                Student.id != student.id,
            )
        )
        if other is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"user_id already linked to student roll {other.student_id}",
            )
        portal_user = db.get(User, body.user_id)
        if portal_user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Portal user not found for user_id",
            )
        if portal_user.role != "STUDENT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only users with role STUDENT can be linked",
            )

    student.user_id = body.user_id
    db.commit()
    db.refresh(student)
    return student


@app.post("/exam-rooms", response_model=ExamRoomOut, status_code=status.HTTP_201_CREATED)
def create_exam_room(
    room_in: ExamRoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "HOD")),
):
    existing = db.scalar(
        select(ExamRoom).where(ExamRoom.room_number == room_in.room_number)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room number already registered",
        )

    room = ExamRoom(
        room_number=room_in.room_number,
        building=room_in.building,
        capacity=room_in.capacity,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@app.get("/exam-rooms", response_model=list[ExamRoomOut])
def list_exam_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rooms = db.scalars(select(ExamRoom).order_by(ExamRoom.id)).all()
    return rooms


@app.post("/cameras", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(
    camera_in: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "HOD")),
):
    from routers.live import _validate_source_url

    room = db.get(ExamRoom, camera_in.room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam room not found for room_id",
        )

    existing = db.scalar(
        select(Camera).where(Camera.camera_id == camera_in.camera_id)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera ID already registered",
        )

    validated_url = _validate_source_url(
        camera_in.stream_url, allow_sample_file=True
    )

    camera = Camera(
        camera_id=camera_in.camera_id,
        name=camera_in.name,
        room_id=camera_in.room_id,
        stream_url=validated_url,
        is_active=camera_in.is_active,
    )
    db.add(camera)
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action="CAMERA_CREATED",
        entity_type="camera",
        entity_id=camera.id,
        description=f"Registered camera {camera.camera_id}",
    )
    db.commit()
    db.refresh(camera)
    return _camera_out(db, camera, redact_credentials=False)


def _source_kind(url: str) -> str:
    lower = (url or "").lower()
    if lower.startswith("rtsp://"):
        return "rtsp"
    if lower.startswith("webcam") or lower.isdigit() or lower in {"webcam", "cam", "local"}:
        return "webcam"
    if lower.startswith("http"):
        return "http"
    return "file"


def _camera_out(
    db: Session, camera: Camera, *, redact_credentials: bool = True
) -> CameraOut:
    from live_stream import _redact_source

    room = db.get(ExamRoom, camera.room_id)
    label = (
        f"{room.room_number} — {room.building}" if room else f"Room #{camera.room_id}"
    )
    display = _redact_source(camera.stream_url)
    return CameraOut(
        id=camera.id,
        camera_id=camera.camera_id,
        name=camera.name,
        room_id=camera.room_id,
        stream_url=display if redact_credentials else camera.stream_url,
        is_active=camera.is_active,
        room_label=label,
        source_kind=_source_kind(camera.stream_url),
        stream_display=display,
    )


@app.get("/cameras", response_model=list[CameraOut])
def list_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only camera admins receive raw RTSP URLs (may contain credentials)
    redact = current_user.role not in ("HOD", "EXAM_DEPARTMENT")
    cameras = db.scalars(select(Camera).order_by(Camera.id)).all()
    return [_camera_out(db, c, redact_credentials=redact) for c in cameras]


@app.post("/exams", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    exam_in: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "HOD")),
):
    room = db.get(ExamRoom, exam_in.room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam room not found for room_id",
        )

    if exam_in.end_time <= exam_in.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time",
        )

    exam = Exam(
        course_code=exam_in.course_code,
        course_name=exam_in.course_name,
        semester=exam_in.semester,
        exam_date=exam_in.exam_date,
        start_time=exam_in.start_time,
        end_time=exam_in.end_time,
        room_id=exam_in.room_id,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@app.get("/exams", response_model=list[ExamOut])
def list_exams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exams = db.scalars(select(Exam).order_by(Exam.id)).all()
    return exams


def _next_case_number(db: Session) -> str:
    """Build a simple unique case number, e.g. UFM-20260822-0001."""
    today = datetime.utcnow().strftime("%Y%m%d")
    total = db.scalar(select(func.count()).select_from(UfmCase)) or 0
    return f"UFM-{today}-{total + 1:04d}"


@app.post("/ufm-cases", response_model=UfmCaseOut, status_code=status.HTTP_201_CREATED)
def create_ufm_case(
    case_in: UfmCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("INVIGILATOR", "HOD")),
):
    student = db.get(Student, case_in.student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student not found for student_id",
        )
    if db.get(Exam, case_in.exam_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam not found for exam_id",
        )

    signer = _require_signoff(
        signer_name=case_in.signer_name,
        signature_ack=case_in.signature_ack,
    )
    signed_at = datetime.utcnow()

    if case_in.detection_id is not None:
        detection = db.get(Detection, case_in.detection_id)
        if detection is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Detection not found for detection_id",
            )
        if getattr(detection, "is_demo", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Demo/test detections cannot create production UFM cases",
            )

    case = UfmCase(
        case_number=_next_case_number(db),
        student_id=case_in.student_id,
        exam_id=case_in.exam_id,
        reported_by=current_user.id,
        violation_type=case_in.violation_type,
        description=case_in.description,
        remarks=case_in.remarks,
        status="PENDING",
        signer_name=signer,
        signed_at=signed_at,
        signature_ack=True,
    )
    db.add(case)
    db.flush()  # get case.id before commit

    if case_in.detection_id is not None:
        attach_detection_evidence_to_case(
            db, detection_id=case_in.detection_id, case_id=case.id
        )

    write_audit_log(
        db,
        user_id=current_user.id,
        action="CASE_CREATED",
        entity_type="ufm_case",
        entity_id=case.id,
        description=f"Created case {case.case_number} ({case.violation_type})",
    )
    write_audit_log(
        db,
        user_id=current_user.id,
        action="CASE_SIGNED",
        entity_type="ufm_case",
        entity_id=case.id,
        description=f"Digital sign-off by {signer} on create {case.case_number}",
    )
    notify_users_with_role(
        db,
        role="HOD",
        case_id=case.id,
        type="CASE_CREATED",
        title="New UFM case",
        message=f"{case.case_number} created and awaits HOD review.",
    )
    notify_student_for_case(
        db,
        student=student,
        case_id=case.id,
        case_number=case.case_number,
    )
    db.commit()
    db.refresh(case)
    return enrich_case(db, case)


@app.get("/ufm-cases", response_model=list[UfmCaseOut])
def list_ufm_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(UfmCase).order_by(UfmCase.id)
    if current_user.role == "STUDENT":
        linked = resolve_linked_student(db, current_user)
        if linked is None:
            return []
        query = query.where(UfmCase.student_id == linked.id)
    cases = db.scalars(query).all()
    return [enrich_case(db, c) for c in cases]


@app.get("/ufm-cases/export.csv")
def export_ufm_cases_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("INVIGILATOR", "HOD", "DEC", "EXAM_DEPARTMENT", "UFM_COMMITTEE")
    ),
):
    """Simple CSV export of enriched cases (not PDF)."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    _ = current_user
    cases = db.scalars(select(UfmCase).order_by(UfmCase.id)).all()
    rows = [enrich_case(db, c) for c in cases]
    buf = io.StringIO()
    fieldnames = [
        "id",
        "case_number",
        "status",
        "violation_type",
        "student_roll",
        "student_name",
        "student_department",
        "exam_course_code",
        "exam_course_name",
        "exam_date",
        "room_number",
        "reporter_name",
        "signer_name",
        "signed_at",
        "created_at",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in fieldnames})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ufm_cases.csv"},
    )


@app.get("/ufm-cases/{case_id}", response_model=UfmCaseOut)
def get_ufm_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.get(UfmCase, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UFM case not found",
        )
    if current_user.role == "STUDENT":
        linked = resolve_linked_student(db, current_user)
        if linked is None or case.student_id != linked.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own UFM cases",
            )
    # Optional: mark UNDER_REVIEW when first staff opens a PENDING case
    if (
        current_user.role in {"HOD", "DEC", "EXAM_DEPARTMENT", "UFM_COMMITTEE"}
        and case.status == "PENDING"
    ):
        case.status = "UNDER_REVIEW"
        case.updated_at = datetime.utcnow()
        write_audit_log(
            db,
            user_id=current_user.id,
            action="CASE_OPENED",
            entity_type="ufm_case",
            entity_id=case.id,
            description=f"{current_user.role} opened {case.case_number}; status → UNDER_REVIEW",
        )
        db.commit()
        db.refresh(case)
    return enrich_case(db, case)


@app.get("/me/student-profile", response_model=StudentOut | None)
def my_student_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("STUDENT")),
):
    """Linked student record for the logged-in student portal user."""
    return resolve_linked_student(db, current_user)


@app.post(
    "/ufm-cases/{case_id}/reviews",
    response_model=CaseReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_case_review(
    case_id: int,
    review_in: CaseReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("HOD", "DEC", "EXAM_DEPARTMENT", "UFM_COMMITTEE")
    ),
):
    case = db.get(UfmCase, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UFM case not found",
        )

    new_status = next_status(
        role=current_user.role,
        action=review_in.action,
        current_status=case.status,
    )

    signer = _require_signoff(
        signer_name=review_in.signer_name,
        signature_ack=review_in.signature_ack,
    )
    signed_at = datetime.utcnow()

    review = CaseReview(
        case_id=case.id,
        reviewer_id=current_user.id,
        reviewer_role=current_user.role,
        action=review_in.action.strip().upper(),
        remarks=review_in.remarks,
        signer_name=signer,
        signed_at=signed_at,
        signature_ack=True,
    )
    case.status = new_status
    case.updated_at = datetime.utcnow()

    db.add(review)
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action=f"CASE_REVIEW_{review.action}",
        entity_type="ufm_case",
        entity_id=case.id,
        description=(
            f"{current_user.role} {review.action} on {case.case_number}; "
            f"status → {new_status}; signed by {signer}"
        ),
    )

    # Notify reporter about every status change
    create_notification(
        db,
        user_id=case.reported_by,
        case_id=case.id,
        type="CASE_STATUS",
        title="Case status updated",
        message=f"{case.case_number} is now {new_status}.",
    )

    # Notify linked student
    student = db.get(Student, case.student_id)
    if student and student.user_id:
        create_notification(
            db,
            user_id=student.user_id,
            case_id=case.id,
            type="CASE_STATUS",
            title="Your UFM case status changed",
            message=f"{case.case_number} is now {new_status}.",
        )

    # Notify next role in the chain (if any)
    next_role = STATUS_NEXT_ROLE.get(new_status)
    if next_role:
        notify_users_with_role(
            db,
            role=next_role,
            case_id=case.id,
            type="CASE_ACTION_REQUIRED",
            title="Case needs your action",
            message=f"{case.case_number} moved to {new_status}.",
        )

    # On APPROVED: auto-hold result/transcript for the student
    if new_status == "APPROVED":
        existing_hold = db.scalar(
            select(ResultControl).where(ResultControl.case_id == case.id)
        )
        if existing_hold is None:
            hold = ResultControl(
                student_id=case.student_id,
                case_id=case.id,
                result_status="HELD",
                transcript_status="BLOCKED",
                reason=f"Automatic hold after UFM decision on {case.case_number}",
            )
            db.add(hold)
            write_audit_log(
                db,
                user_id=current_user.id,
                action="RESULT_HOLD_CREATED",
                entity_type="result_control",
                entity_id=case.id,
                description=f"Result/transcript hold applied for case {case.case_number}",
            )
            notify_users_with_role(
                db,
                role="EXAM_DEPARTMENT",
                case_id=case.id,
                type="RESULT_HOLD",
                title="Result hold applied",
                message=f"{case.case_number}: student result held / transcript blocked.",
            )

    db.commit()
    db.refresh(review)
    return review


@app.get("/ufm-cases/{case_id}/reviews", response_model=list[CaseReviewOut])
def list_case_reviews(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if db.get(UfmCase, case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UFM case not found",
        )
    reviews = db.scalars(
        select(CaseReview)
        .where(CaseReview.case_id == case_id)
        .order_by(CaseReview.id)
    ).all()
    return reviews


@app.post(
    "/evidence",
    response_model=EvidenceOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(
    case_id: int = Form(...),
    evidence_type: str = Form(...),
    file: UploadFile = File(...),
    camera_id: int | None = Form(None),
    seat_location: str | None = Form(None),
    confidence: float | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("INVIGILATOR", "HOD")),
):
    if db.get(UfmCase, case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="UFM case not found for case_id",
        )
    if camera_id is not None and db.get(Camera, camera_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera not found for camera_id",
        )

    original_name = Path(file.filename or "evidence.bin").name
    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    destination = EVIDENCE_UPLOAD_DIR / stored_name

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    destination.write_bytes(content)

    # Convert non-browser video (AVI/etc.) to animated WebP so Open works in-tab.
    # Original Download still serves whatever is stored; prefer viewable format.
    suffix = destination.suffix.lower()
    if suffix in {".avi", ".mp4", ".mov", ".webm"}:
        try:
            webp_bytes = video_file_to_animated_webp(destination, fps=8.0)
            if webp_bytes:
                webp_dest = destination.with_suffix(".webp")
                webp_dest.write_bytes(webp_bytes)
                try:
                    destination.unlink(missing_ok=True)
                except OSError:
                    pass
                destination = webp_dest
                stored_name = webp_dest.name
        except Exception:  # noqa: BLE001
            pass

    # Store a portable relative path in the database
    relative_path = f"uploads/evidence/{stored_name}"

    evidence = Evidence(
        case_id=case_id,
        detection_id=None,
        evidence_type=evidence_type,
        file_path=relative_path,
        camera_id=camera_id,
        seat_location=seat_location,
        confidence=confidence,
        uploaded_by=current_user.id,
    )
    db.add(evidence)
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action="EVIDENCE_UPLOADED",
        entity_type="evidence",
        entity_id=evidence.id,
        description=f"Uploaded {evidence_type} for case_id={case_id}: {relative_path}",
    )
    db.commit()
    db.refresh(evidence)
    return evidence


@app.get("/evidence", response_model=list[EvidenceOut])
def list_evidence(
    case_id: int | None = None,
    detection_id: int | None = None,
    include_demo: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    query = select(Evidence).order_by(Evidence.id)
    if case_id is not None:
        query = query.where(Evidence.case_id == case_id)
    if detection_id is not None:
        query = query.where(Evidence.detection_id == detection_id)
    if not include_demo:
        try:
            query = query.where(Evidence.is_demo.is_(False))
        except Exception:  # noqa: BLE001
            pass
    return db.scalars(query).all()


@app.get("/evidence/{evidence_id}/file")
def download_evidence_file(
    evidence_id: int,
    view: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Serve an evidence file.
    view=true → browser-friendly inline (AVI/MP4 converted to animated WebP).
    view=false → original bytes (for Download).
    """
    _ = current_user
    row = db.get(Evidence, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")

    path = _resolve_evidence_path(row)
    if path is None:
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")

    suffix = path.suffix.lower()

    # Open-in-browser path: convert non-viewable videos to animated WebP
    if view and suffix in {".avi", ".mp4", ".webm", ".mov"}:
        data = video_file_to_animated_webp(path, fps=8.0)
        if data:
            return Response(
                content=data,
                media_type="image/webp",
                headers={
                    "Content-Disposition": (
                        f'inline; filename="evidence-{evidence_id}-view.webp"'
                    )
                },
            )

    media_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".pdf": "application/pdf",
    }
    media_type = media_map.get(suffix, "application/octet-stream")
    download_name = path.name
    if suffix and not download_name.lower().endswith(suffix):
        download_name = f"{download_name}{suffix}"

    return FileResponse(
        path,
        media_type=media_type,
        filename=download_name,
        content_disposition_type="inline",
    )


def _resolve_evidence_path(row: Evidence) -> Path | None:
    backend_root = Path(__file__).resolve().parent
    stored = Path(row.file_path)
    candidates = [
        stored if stored.is_absolute() else backend_root / stored,
        backend_root / "uploads" / "evidence" / stored.name,
    ]
    return next((p for p in candidates if p.is_file()), None)


@app.get("/evidence/{evidence_id}/preview")
def preview_evidence_file(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Browser-friendly view of evidence.
    Images/WebP returned as-is; legacy AVI/MP4 converted to animated WebP.
    """
    _ = current_user
    row = db.get(Evidence, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")

    path = _resolve_evidence_path(row)
    if path is None:
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")

    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        media_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        return FileResponse(
            path,
            media_type=media_map[suffix],
            filename=path.name,
            content_disposition_type="inline",
        )

    if suffix in {".avi", ".mp4", ".webm", ".mov"}:
        data = video_file_to_animated_webp(path, fps=8.0)
        if not data:
            raise HTTPException(
                status_code=422,
                detail="Could not build browser preview for this clip; use Download",
            )
        return Response(
            content=data,
            media_type="image/webp",
            headers={
                "Content-Disposition": f'inline; filename="evidence-{evidence_id}-preview.webp"'
            },
        )

    if suffix == ".pdf":
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=path.name,
            content_disposition_type="inline",
        )

    raise HTTPException(
        status_code=422,
        detail="No in-browser preview for this file type; use Download",
    )


@app.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("HOD", "DEC", "EXAM_DEPARTMENT", "UFM_COMMITTEE")
    ),
):
    logs = db.scalars(select(AuditLog).order_by(AuditLog.id.desc())).all()
    return logs


@app.get("/detections", response_model=list[DetectionOut])
def list_detections(
    confirmed_only: bool = False,
    unseen_only: bool = False,
    include_demo: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    query = select(Detection).order_by(Detection.id.desc())
    if confirmed_only:
        query = query.where(Detection.is_confirmed.is_(True))
    if unseen_only:
        query = query.where(Detection.is_seen.is_(False))
    if not include_demo:
        # Production inbox: exclude demo/testing detections when column exists
        try:
            query = query.where(Detection.is_demo.is_(False))
        except Exception:  # noqa: BLE001
            pass
    rows = db.scalars(query).all()
    out = []
    for row in rows:
        if not hasattr(row, "is_seen") or row.is_seen is None:
            try:
                row.is_seen = False
            except Exception:  # noqa: BLE001
                pass
        if not hasattr(row, "is_demo") or row.is_demo is None:
            try:
                row.is_demo = False
            except Exception:  # noqa: BLE001
                pass
        out.append(row)
    return out


@app.patch("/detections/{detection_id}/seen", response_model=DetectionOut)
def mark_detection_seen(
    detection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    row = db.get(Detection, detection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Detection not found")
    row.is_seen = True
    db.commit()
    db.refresh(row)
    return row


@app.post("/detections/mark-all-seen")
def mark_all_detections_seen(
    confirmed_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    query = select(Detection).where(Detection.is_seen.is_(False))
    if confirmed_only:
        query = query.where(Detection.is_confirmed.is_(True))
    rows = db.scalars(query).all()
    for row in rows:
        row.is_seen = True
    db.commit()
    return {"updated": len(rows)}


@app.post(
    "/detections/{detection_id}/create-draft-case",
    response_model=UfmCaseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_draft_case_from_detection_api(
    detection_id: int,
    body: DraftCaseFromDetection,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("INVIGILATOR", "HOD")),
):
    detection = db.get(Detection, detection_id)
    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection not found",
        )
    if getattr(detection, "is_demo", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Demo/test detections cannot enter the production case queue",
        )

    case = create_draft_case_from_detection(
        db,
        detection=detection,
        student_id=body.student_id,
        exam_id=body.exam_id,
        reported_by=current_user.id,
    )
    db.commit()
    db.refresh(case)
    return enrich_case(db, case)


@app.get("/notifications", response_model=list[NotificationOut])
def list_my_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.id.desc())
    )
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    # Keep demo detection alerts out of the primary institutional inbox
    query = query.where(Notification.type != "DETECTION_ALERT_DEMO")
    notes = db.scalars(query).all()
    return [enrich_notification(db, n) for n in notes]


@app.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    note.is_read = True
    db.commit()
    db.refresh(note)
    return enrich_notification(db, note)


@app.post("/notifications/mark-all-read")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notes = db.scalars(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ).all()
    for note in notes:
        note.is_read = True
    db.commit()
    return {"updated": len(notes)}


@app.post(
    "/result-controls",
    response_model=ResultControlOut,
    status_code=status.HTTP_201_CREATED,
)
def create_result_control(
    body: ResultControlCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "UFM_COMMITTEE")),
):
    if db.get(Student, body.student_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student not found for student_id",
        )
    case = db.get(UfmCase, body.case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="UFM case not found for case_id",
        )
    existing = db.scalar(
        select(ResultControl).where(ResultControl.case_id == body.case_id)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Result control already exists for this case",
        )

    control = ResultControl(
        student_id=body.student_id,
        case_id=body.case_id,
        result_status=body.result_status,
        transcript_status=body.transcript_status,
        reason=body.reason,
    )
    db.add(control)
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action="RESULT_HOLD_CREATED",
        entity_type="result_control",
        entity_id=control.id,
        description=f"Manual result control for case_id={body.case_id}",
    )
    db.commit()
    db.refresh(control)
    return control


@app.get("/result-controls", response_model=list[ResultControlOut])
def list_result_controls(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("EXAM_DEPARTMENT", "UFM_COMMITTEE", "HOD", "DEC")
    ),
):
    return db.scalars(select(ResultControl).order_by(ResultControl.id.desc())).all()


@app.patch(
    "/result-controls/{control_id}/release",
    response_model=ResultControlOut,
)
def release_result_control(
    control_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "UFM_COMMITTEE")),
):
    control = db.get(ResultControl, control_id)
    if control is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result control not found",
        )
    if control.result_status == "RELEASED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Result control already released",
        )

    control.result_status = "RELEASED"
    control.transcript_status = "ALLOWED"
    control.released_at = datetime.utcnow()
    control.released_by = current_user.id

    write_audit_log(
        db,
        user_id=current_user.id,
        action="RESULT_RELEASED",
        entity_type="result_control",
        entity_id=control.id,
        description=f"Released result/transcript for case_id={control.case_id}",
    )
    create_notification(
        db,
        user_id=db.get(UfmCase, control.case_id).reported_by,
        case_id=control.case_id,
        type="RESULT_RELEASED",
        title="Result released",
        message=f"Result/transcript released for case_id={control.case_id}.",
    )
    db.commit()
    db.refresh(control)
    return control


@app.post(
    "/clarifications",
    response_model=ClarificationOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_clarification(
    body: ClarificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("STUDENT")),
):
    linked = resolve_linked_student(db, current_user)
    if linked is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No student profile linked to this account. "
                "Ask staff to set students.user_id (run seed_demo_users.py for demo)."
            ),
        )

    case = db.get(UfmCase, body.case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UFM case not found",
        )
    if case.student_id != linked.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only clarify your own cases",
        )

    clarification = Clarification(
        case_id=case.id,
        student_user_id=current_user.id,
        statement=body.statement.strip(),
        status="SUBMITTED",
    )
    db.add(clarification)
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action="CLARIFICATION_SUBMITTED",
        entity_type="clarification",
        entity_id=clarification.id,
        description=f"Student clarification for {case.case_number}",
    )
    notify_users_with_role(
        db,
        role="HOD",
        case_id=case.id,
        type="CLARIFICATION",
        title="Student clarification received",
        message=f"{case.case_number}: student submitted an explanation.",
    )
    create_notification(
        db,
        user_id=case.reported_by,
        case_id=case.id,
        type="CLARIFICATION",
        title="Clarification submitted",
        message=f"Student responded on {case.case_number}.",
    )
    db.commit()
    db.refresh(clarification)
    return clarification


@app.get("/clarifications", response_model=list[ClarificationOut])
def list_clarifications(
    case_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Clarification).order_by(Clarification.id.desc())

    if current_user.role == "STUDENT":
        query = query.where(Clarification.student_user_id == current_user.id)
        if case_id is not None:
            query = query.where(Clarification.case_id == case_id)
    else:
        if case_id is not None:
            query = query.where(Clarification.case_id == case_id)
        elif current_user.role not in {
            "HOD",
            "DEC",
            "EXAM_DEPARTMENT",
            "UFM_COMMITTEE",
            "INVIGILATOR",
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to list clarifications",
            )

    return db.scalars(query).all()
