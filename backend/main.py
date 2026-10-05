import uuid
from datetime import datetime
from pathlib import Path

from time_utils import to_api_iso, utc_now

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app_config import (
    ENABLE_API_DOCS,
    IS_PRODUCTION,
    auth_mode,
    cors_allow_origins,
    demo_helpers_enabled,
    google_auth_enabled,
    password_login_enabled,
    validate_production_settings,
)

# Fail fast before mounting routes/middleware when production env is unsafe.
validate_production_settings()
from case_access import (
    CAMERA_VIEW_ROLES,
    DETECTION_STAFF_ROLES,
    EVIDENCE_UPLOAD_ROLES,
    EXAM_CATALOG_ROLES,
    REPORTS_ROLES,
    STAFF_USER_VIEW_ROLES,
    STUDENT_DIRECTORY_ROLES,
    active_queue_statuses_for_role,
    assert_can_access_case,
    assert_can_access_case_id,
    case_list_statuses_for_role,
)
from case_camera import resolve_camera_for_case_create
from case_enrich import enrich_case
from database import engine, get_db
from deps import get_current_user, require_roles
from detection_bridge import create_draft_case_from_detection
from evidence_auto import attach_detection_evidence_to_case, video_file_to_animated_webp
from evidence_download import preferred_download_filename, resolve_evidence_media_type
from models.audit_log import AuditLog  # registers audit_logs table on Base
from models.base import Base
from models.camera import Camera  # registers cameras table on Base
from models.case_review import CaseReview  # registers case_reviews table on Base
from models.clarification import Clarification  # registers clarifications table on Base
from models.detection import Detection  # registers detections table on Base
from models.exam import Exam  # registers exams table on Base
from models.exam_enrollment import ExamEnrollment  # noqa: F401
from models.exam_invigilator import ExamInvigilator  # noqa: F401
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
from exam_ops import (
    assert_student_enrolled_if_roster,
    enrollment_out,
    invigilator_out,
)
from schemas.audit_log import AuditLogOut
from schemas.auth import (
    AuthPublicConfig,
    GoogleLoginRequest,
    LoginRequest,
    LoginResponse,
)
from schemas.camera import CameraCreate, CameraOut
from schemas.case_review import CaseReviewCreate, CaseReviewOut
from schemas.clarification import ClarificationCreate, ClarificationOut
from schemas.detection import DetectionOut, DraftCaseFromDetection
from schemas.exam import ExamCreate, ExamOut
from schemas.exam_ops import (
    ExamDetailOut,
    ExamEnrollmentCreate,
    ExamEnrollmentOut,
    ExamInvigilatorCreate,
    ExamInvigilatorOut,
    ExamUpdate,
)
from schemas.exam_room import ExamRoomCreate, ExamRoomOut
from schemas.evidence import EvidenceOut
from schemas.notification import NotificationOut
from schemas.result_control import ResultControlCreate, ResultControlOut
from result_control_enrich import enrich_result_control
from schemas.student import StudentCreate, StudentLinkUser, StudentOut
from schemas.ufm_case import (
    UfmCaseCreate,
    UfmCaseOut,
    serialize_recovered_materials,
)
from schemas.user import UserCreate, UserOut
from security import create_access_token, hash_password, verify_password
from google_auth import normalize_email, verify_google_id_token
from student_portal import resolve_linked_student
from routers.admin_users import router as admin_users_router
from routers.live import router as live_router
from routers.ws_alerts import router as ws_router
import ws_hub
from workflow import next_status

app = FastAPI(
    title="VigilantEye API",
    version="0.1.0",
    docs_url="/docs" if ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_API_DOCS else None,
)
app.include_router(live_router)
app.include_router(ws_router)
app.include_router(admin_users_router)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Conservative API security headers (compatible with React/Vite clients)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Cache-Control", "no-store, no-cache, must-revalidate"
        )
        return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Avoid leaking stack traces / internals in production responses."""
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)
    if IS_PRODUCTION:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


@app.on_event("startup")
async def _on_startup() -> None:
    import asyncio
    import os

    # Production must never evolve schema via create_all — use Alembic.
    # Development may optionally ensure tables for bare `uvicorn` without
    # docker entrypoint (default on). Compose uses alembic via bootstrap.
    allow_create_all = (os.getenv("ALLOW_CREATE_ALL_ON_STARTUP") or "").strip()
    if allow_create_all == "":
        allow_create_all = "0" if IS_PRODUCTION else "1"
    if allow_create_all.lower() in {"1", "true", "yes", "on"} and not IS_PRODUCTION:
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as exc:  # noqa: BLE001
            print(f"Schema init at startup deferred ({type(exc).__name__})")
    elif IS_PRODUCTION:
        print("Schema: production startup skips create_all (Alembic-managed)")

    ws_hub.set_event_loop(asyncio.get_running_loop())

@app.on_event("shutdown")
def _stop_live_sessions() -> None:
    from live_stream import live_manager

    live_manager.stop_all()

# CORS: localhost Vite defaults unless CORS_ORIGINS is set (comma-separated).
# Expose Content-Disposition so the SPA can read download filenames (C32).
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(SecurityHeadersMiddleware)

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

# Human labels for notification copy only (statuses unchanged).
_STATUS_NOTIFY_LABEL = {
    "PENDING": "Pending",
    "UNDER_REVIEW": "Under Review",
    "DEC_REVIEW": "DEC Review",
    "EXAM_DEPARTMENT_REVIEW": "Exam Department Review",
    "UFM_COMMITTEE_REVIEW": "UFM Committee Review",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
}


def _status_notify_label(status: str) -> str:
    return _STATUS_NOTIFY_LABEL.get(status, str(status).replace("_", " "))


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
    """Liveness: process is up (does not require DB)."""
    return {
        "status": "ok",
        "project": "VigilantEye",
        "application": "up",
    }


@app.get("/ready")
def ready_check():
    """Readiness: API can reach PostgreSQL (and reports migration status safely)."""
    from db_migrations import get_alembic_migration_status

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            mig = get_alembic_migration_status(connection=conn)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "application": "up",
                "database": "down",
                "reason": type(exc).__name__,
            },
        ) from exc
    payload = {
        "status": "ready",
        "project": "VigilantEye",
        "application": "up",
        "database": "ok",
        "alembic_current": mig.get("current_revision"),
        "alembic_head": mig.get("head_revision"),
        "migrations_pending": mig.get("migrations_pending"),
    }
    # Pending migrations: still "ready" for liveness of DB, but flag for operators.
    return payload

@app.get("/auth/config", response_model=AuthPublicConfig)
def auth_public_config():
    """Public login-page flags (no secrets). Google client ID is designed to be public."""
    from app_config import GOOGLE_CLIENT_ID

    google_on = google_auth_enabled()
    return AuthPublicConfig(
        auth_mode=auth_mode(),
        password_login_enabled=password_login_enabled(),
        google_auth_enabled=google_on,
        google_client_id=GOOGLE_CLIENT_ID if google_on else None,
        demo_helpers_enabled=demo_helpers_enabled(),
    )


def _portal_login_response(user: User, *, message: str) -> LoginResponse:
    return LoginResponse(
        message=message,
        access_token=create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
        ),
        token_type="bearer",
        user=user,
    )


@app.post("/auth/login", response_model=LoginResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    if not password_login_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password login is disabled. Use Continue with Google.",
        )
    email = normalize_email(str(credentials.email))
    user = db.scalar(select(User).where(User.email == email))
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
    return _portal_login_response(user, message="Login successful")


@app.post("/auth/google", response_model=LoginResponse)
def login_with_google(body: GoogleLoginRequest, db: Session = Depends(get_db)):
    """
    Verify Google ID token → lookup authorized portal User by email → issue JWT.

    Google identity never sets role; User.role in the database is authoritative.
    """
    identity = verify_google_id_token(body.id_token)
    user = db.scalar(select(User).where(User.email == identity.email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not authorized",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return _portal_login_response(user, message="Google login successful")


@app.get("/auth/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Protected route: requires Authorization: Bearer <token>."""
    return current_user


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("EXAM_DEPARTMENT", "HOD")
    ),
):
    role = user_in.role.strip().upper()
    # Operational POST /users is limited to STUDENT portal accounts (C11-B).
    # Staff/admin provisioning uses Administrator APIs only.
    if role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only STUDENT portal accounts can be created here; use Administrator for staff",
        )

    existing = db.scalar(
        select(User).where(User.email == str(user_in.email).strip().lower())
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        name=user_in.name,
        email=str(user_in.email).strip().lower(),
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
    # Self-access always allowed; otherwise staff roles that can list users.
    if user_id != current_user.id and current_user.role not in STAFF_USER_VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to view this user profile",
        )
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
        require_roles("HOD", "EXAM_DEPARTMENT")
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
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*STUDENT_DIRECTORY_ROLES)),
):
    _ = current_user
    query = select(Student).order_by(Student.id)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.where(
            or_(Student.student_id.ilike(like), Student.name.ilike(like))
        )
    students = db.scalars(query).all()
    return students


@app.patch("/students/{student_pk}/link-user", response_model=StudentOut)
def link_student_user(
    student_pk: int,
    body: StudentLinkUser,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("HOD", "EXAM_DEPARTMENT")
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
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action="ROOM_CREATED",
        entity_type="exam_room",
        entity_id=room.id,
        description=f"Created room {room.room_number} ({room.building})",
    )
    db.commit()
    db.refresh(room)
    return room


@app.get("/exam-rooms", response_model=list[ExamRoomOut])
def list_exam_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EXAM_CATALOG_ROLES)),
):
    _ = current_user
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
    current_user: User = Depends(require_roles(*CAMERA_VIEW_ROLES)),
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
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action="EXAM_CREATED",
        entity_type="exam",
        entity_id=exam.id,
        description=(
            f"Created exam {exam.course_code} ({exam.course_name}) "
            f"on {exam.exam_date}"
        ),
    )
    db.commit()
    db.refresh(exam)
    return exam


@app.get("/exams", response_model=list[ExamOut])
def list_exams(
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EXAM_CATALOG_ROLES)),
):
    _ = current_user
    query = select(Exam).order_by(Exam.id)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.where(
            or_(
                Exam.course_code.ilike(like),
                Exam.course_name.ilike(like),
                Exam.semester.ilike(like),
            )
        )
    exams = db.scalars(query).all()
    return exams


@app.get("/exams/{exam_id}", response_model=ExamDetailOut)
def get_exam_detail(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EXAM_CATALOG_ROLES)),
):
    _ = current_user
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    enrollments = [
        ExamEnrollmentOut(**enrollment_out(db, row))
        for row in db.scalars(
            select(ExamEnrollment).where(ExamEnrollment.exam_id == exam_id)
        ).all()
    ]
    invigilators = [
        ExamInvigilatorOut(**invigilator_out(db, row))
        for row in db.scalars(
            select(ExamInvigilator).where(ExamInvigilator.exam_id == exam_id)
        ).all()
    ]
    cameras = db.scalars(
        select(Camera).where(Camera.room_id == exam.room_id).order_by(Camera.id)
    ).all()
    room_cameras = [
        {
            "id": c.id,
            "camera_id": c.camera_id,
            "name": c.name,
            "is_active": c.is_active,
        }
        for c in cameras
    ]
    return ExamDetailOut(
        id=exam.id,
        course_code=exam.course_code,
        course_name=exam.course_name,
        semester=exam.semester,
        exam_date=exam.exam_date,
        start_time=exam.start_time,
        end_time=exam.end_time,
        room_id=exam.room_id,
        enrollments=enrollments,
        invigilators=invigilators,
        room_cameras=room_cameras,
    )


@app.patch("/exams/{exam_id}", response_model=ExamOut)
def update_exam(
    exam_id: int,
    body: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "HOD")),
):
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    data = body.model_dump(exclude_unset=True)
    if "room_id" in data:
        if db.get(ExamRoom, data["room_id"]) is None:
            raise HTTPException(status_code=400, detail="Exam room not found for room_id")
    start = data.get("start_time", exam.start_time)
    end = data.get("end_time", exam.end_time)
    if end <= start:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    for key, value in data.items():
        setattr(exam, key, value)
    write_audit_log(
        db,
        user_id=current_user.id,
        action="EXAM_UPDATED",
        entity_type="exam",
        entity_id=exam.id,
        description=f"Updated exam {exam.course_code}",
    )
    db.commit()
    db.refresh(exam)
    return exam


@app.post(
    "/exams/{exam_id}/enrollments",
    response_model=ExamEnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
def enroll_student(
    exam_id: int,
    body: ExamEnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "HOD")),
):
    if db.get(Exam, exam_id) is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    student = db.get(Student, body.student_id)
    if student is None:
        raise HTTPException(status_code=400, detail="Student not found")
    existing = db.scalar(
        select(ExamEnrollment).where(
            ExamEnrollment.exam_id == exam_id,
            ExamEnrollment.student_id == body.student_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=400, detail="Student already enrolled in this exam")
    row = ExamEnrollment(exam_id=exam_id, student_id=body.student_id)
    db.add(row)
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action="EXAM_ENROLLMENT_CREATED",
        entity_type="exam_enrollment",
        entity_id=row.id,
        description=f"Enrolled student_id={body.student_id} in exam_id={exam_id}",
    )
    db.commit()
    db.refresh(row)
    return ExamEnrollmentOut(**enrollment_out(db, row))


@app.get("/exams/{exam_id}/enrollments", response_model=list[ExamEnrollmentOut])
def list_enrollments(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EXAM_CATALOG_ROLES)),
):
    _ = current_user
    if db.get(Exam, exam_id) is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    rows = db.scalars(
        select(ExamEnrollment).where(ExamEnrollment.exam_id == exam_id)
    ).all()
    return [ExamEnrollmentOut(**enrollment_out(db, r)) for r in rows]


@app.delete("/exams/{exam_id}/enrollments/{enrollment_id}", status_code=status.HTTP_200_OK)
def unenroll_student(
    exam_id: int,
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "HOD")),
):
    row = db.get(ExamEnrollment, enrollment_id)
    if row is None or row.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    write_audit_log(
        db,
        user_id=current_user.id,
        action="EXAM_ENROLLMENT_REMOVED",
        entity_type="exam_enrollment",
        entity_id=row.id,
        description=f"Removed enrollment student_id={row.student_id} from exam_id={exam_id}",
    )
    db.delete(row)
    db.commit()
    return {"deleted": True}


@app.post(
    "/exams/{exam_id}/invigilators",
    response_model=ExamInvigilatorOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_invigilator(
    exam_id: int,
    body: ExamInvigilatorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "HOD")),
):
    if db.get(Exam, exam_id) is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    user = db.get(User, body.user_id)
    if user is None or user.role != "INVIGILATOR":
        raise HTTPException(
            status_code=400,
            detail="user_id must reference an active INVIGILATOR portal user",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Invigilator account is inactive")
    existing = db.scalar(
        select(ExamInvigilator).where(
            ExamInvigilator.exam_id == exam_id,
            ExamInvigilator.user_id == body.user_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=400, detail="Invigilator already assigned")
    row = ExamInvigilator(exam_id=exam_id, user_id=body.user_id)
    db.add(row)
    db.flush()
    write_audit_log(
        db,
        user_id=current_user.id,
        action="EXAM_INVIGILATOR_ASSIGNED",
        entity_type="exam_invigilator",
        entity_id=row.id,
        description=f"Assigned invigilator user_id={body.user_id} to exam_id={exam_id}",
    )
    db.commit()
    db.refresh(row)
    return ExamInvigilatorOut(**invigilator_out(db, row))


@app.get("/exams/{exam_id}/invigilators", response_model=list[ExamInvigilatorOut])
def list_exam_invigilators(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EXAM_CATALOG_ROLES)),
):
    _ = current_user
    if db.get(Exam, exam_id) is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    rows = db.scalars(
        select(ExamInvigilator).where(ExamInvigilator.exam_id == exam_id)
    ).all()
    return [ExamInvigilatorOut(**invigilator_out(db, r)) for r in rows]


@app.delete("/exams/{exam_id}/invigilators/{assignment_id}", status_code=status.HTTP_200_OK)
def unassign_invigilator(
    exam_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("EXAM_DEPARTMENT", "HOD")),
):
    row = db.get(ExamInvigilator, assignment_id)
    if row is None or row.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    write_audit_log(
        db,
        user_id=current_user.id,
        action="EXAM_INVIGILATOR_UNASSIGNED",
        entity_type="exam_invigilator",
        entity_id=row.id,
        description=f"Unassigned invigilator user_id={row.user_id} from exam_id={exam_id}",
    )
    db.delete(row)
    db.commit()
    return {"deleted": True}


def _next_case_number(db: Session) -> str:
    """Build a simple unique case number, e.g. UFM-20260822-0001."""
    today = utc_now().strftime("%Y%m%d")
    total = db.scalar(select(func.count()).select_from(UfmCase)) or 0
    return f"UFM-{today}-{total + 1:04d}"


def _link_library_evidence_to_case(
    db: Session,
    *,
    case_id: int,
    evidence_ids: list[int],
    current_user: User,
) -> None:
    """Attach existing orphan evidence rows to a newly created case."""
    for eid in evidence_ids:
        row = db.get(Evidence, eid)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Evidence not found for evidence_id={eid}",
            )
        if getattr(row, "is_demo", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Demo evidence cannot be attached to production UFM cases",
            )
        if row.case_id is not None and row.case_id != case_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Evidence {eid} is already linked to another case",
            )
        _assert_can_access_evidence_row(db, current_user, row)
        if row.case_id != case_id:
            row.case_id = case_id
            write_audit_log(
                db,
                user_id=current_user.id,
                action="EVIDENCE_LINKED",
                entity_type="evidence",
                entity_id=row.id,
                description=f"Linked evidence {row.id} to case_id={case_id}",
            )


def _resolve_filing_student(
    db: Session, case_in: UfmCaseCreate, *, actor: User
) -> Student:
    """Resolve selected student or filing-time manual student (no user link)."""
    if case_in.student_id is not None:
        student = db.get(Student, case_in.student_id)
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student not found for student_id",
            )
        return student

    assert case_in.manual_student is not None
    ms = case_in.manual_student
    roll = ms.student_id.strip()
    existing = db.scalar(select(Student).where(Student.student_id == roll))
    if existing is not None:
        # Prefer existing directory row — do not invent a duplicate roll.
        return existing

    student = Student(
        student_id=roll,
        name=ms.name.strip(),
        department=ms.department.strip(),
        program=ms.program.strip(),
        user_id=None,
    )
    db.add(student)
    db.flush()
    write_audit_log(
        db,
        user_id=actor.id,
        action="STUDENT_REGISTERED_FOR_FILING",
        entity_type="student",
        entity_id=student.id,
        description=(
            f"Filing-time student registration {student.student_id} "
            f"during UFM case create"
        ),
    )
    return student


def _resolve_filing_exam(
    db: Session, case_in: UfmCaseCreate, *, actor: User
) -> Exam:
    """Resolve selected exam or filing-time manual exam create."""
    if case_in.exam_id is not None:
        exam = db.get(Exam, case_in.exam_id)
        if exam is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exam not found for exam_id",
            )
        return exam

    assert case_in.manual_exam is not None
    me = case_in.manual_exam
    room = db.get(ExamRoom, me.room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam room not found for room_id",
        )
    if me.end_time <= me.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time",
        )

    exam = Exam(
        course_code=me.course_code.strip(),
        course_name=me.course_name.strip(),
        semester=me.semester.strip(),
        exam_date=me.exam_date,
        start_time=me.start_time,
        end_time=me.end_time,
        room_id=me.room_id,
    )
    db.add(exam)
    db.flush()
    write_audit_log(
        db,
        user_id=actor.id,
        action="EXAM_CREATED_FOR_FILING",
        entity_type="exam",
        entity_id=exam.id,
        description=(
            f"Filing-time exam {exam.course_code} on {exam.exam_date} "
            f"during UFM case create"
        ),
    )
    return exam


@app.post("/ufm-cases", response_model=UfmCaseOut, status_code=status.HTTP_201_CREATED)
def create_ufm_case(
    case_in: UfmCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("INVIGILATOR")),
):
    student = _resolve_filing_student(db, case_in, actor=current_user)
    exam = _resolve_filing_exam(db, case_in, actor=current_user)

    assert_student_enrolled_if_roster(
        db, exam_id=exam.id, student_id=student.id
    )

    signer = _require_signoff(
        signer_name=case_in.signer_name,
        signature_ack=case_in.signature_ack,
    )
    # Server clock is authoritative for case creation (naive UTC — C20/C30 contract).
    # Do not accept client-supplied created_at (not part of UfmCaseCreate).
    created_at = utc_now()
    signed_at = created_at

    detection = None
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

    resolved_camera_id = resolve_camera_for_case_create(
        db,
        exam_id=exam.id,
        camera_id=case_in.camera_id,
        detection=detection,
    )

    case = UfmCase(
        case_number=_next_case_number(db),
        student_id=student.id,
        exam_id=exam.id,
        reported_by=current_user.id,
        violation_type=case_in.violation_type,
        description=case_in.description,
        remarks=case_in.remarks,
        recovered_materials=serialize_recovered_materials(case_in.recovered_materials),
        recovered_other_detail=case_in.recovered_other_detail,
        status="PENDING",
        camera_id=resolved_camera_id,
        signer_name=signer,
        signed_at=signed_at,
        signature_ack=True,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(case)
    db.flush()  # get case.id before commit

    if case_in.detection_id is not None:
        attach_detection_evidence_to_case(
            db, detection_id=case_in.detection_id, case_id=case.id
        )

    if case_in.evidence_ids:
        _link_library_evidence_to_case(
            db,
            case_id=case.id,
            evidence_ids=case_in.evidence_ids,
            current_user=current_user,
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
    notify_users_with_role(
        db,
        role="EXAM_DEPARTMENT",
        case_id=case.id,
        type="CASE_CREATED",
        title="New UFM case",
        message=f"{case.case_number} created and entered the UFM review workflow.",
    )
    notify_users_with_role(
        db,
        role="UFM_COMMITTEE",
        case_id=case.id,
        type="CASE_CREATED",
        title="New UFM case",
        message=f"{case.case_number} created and entered the UFM review workflow.",
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
    scope: str | None = None,
    case_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List UFM cases for the caller.

    scope:
      - active     → only cases awaiting this role's review (workflow queue)
      - dashboard  → role workspace (active + later/final tracking; no premature upstream)
      - all        → institution-wide for authorized reporters/exporters (HOD/DEC/Exam/UFM);
                     Invigilator still limited to cases they reported
      - (default)  → same as dashboard for reviewing roles; Invigilator = own cases;
                     Student = own linked cases

    Optional status= further narrows within the allowed set for this role/scope.
    """
    # ADMINISTRATOR manages authorization only — no UFM case queue.
    if current_user.role == "ADMINISTRATOR":
        return []

    scope_key = (scope or "dashboard").strip().lower()
    if scope_key not in {"active", "dashboard", "all"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope must be one of: active, dashboard, all",
        )

    query = select(UfmCase).order_by(
        UfmCase.created_at.desc(), UfmCase.id.desc()
    )

    if current_user.role == "STUDENT":
        linked = resolve_linked_student(db, current_user)
        if linked is None:
            return []
        query = query.where(UfmCase.student_id == linked.id)
        if scope_key == "active":
            query = query.where(
                UfmCase.status.in_(
                    sorted(
                        {
                            "PENDING",
                            "UNDER_REVIEW",
                            "DEC_REVIEW",
                            "EXAM_DEPARTMENT_REVIEW",
                            "UFM_COMMITTEE_REVIEW",
                        }
                    )
                )
            )
    elif current_user.role == "INVIGILATOR":
        # Invigilators track cases they reported — not institution-wide queues.
        query = query.where(UfmCase.reported_by == current_user.id)
        if scope_key == "active":
            query = query.where(
                UfmCase.status.in_(
                    sorted(
                        {
                            "PENDING",
                            "UNDER_REVIEW",
                            "DEC_REVIEW",
                            "EXAM_DEPARTMENT_REVIEW",
                            "UFM_COMMITTEE_REVIEW",
                        }
                    )
                )
            )
    else:
        # HOD / DEC / Exam / UFM
        if scope_key == "all":
            allowed = None  # institution-wide records for reporting roles
        elif scope_key == "active":
            allowed = active_queue_statuses_for_role(current_user.role)
        else:
            allowed = case_list_statuses_for_role(current_user.role)

        if allowed is not None:
            query = query.where(UfmCase.status.in_(sorted(allowed)))

    status_filter = (case_status or "").strip().upper()
    if status_filter:
        # Reject status filters outside the role's allowed set for this scope
        # (prevents DEC from pulling PENDING via ?status=PENDING).
        if current_user.role in {"STUDENT", "INVIGILATOR"} or scope_key == "all":
            query = query.where(UfmCase.status == status_filter)
        else:
            allowed_now = (
                active_queue_statuses_for_role(current_user.role)
                if scope_key == "active"
                else case_list_statuses_for_role(current_user.role)
            )
            if allowed_now is not None and status_filter not in allowed_now:
                return []
            query = query.where(UfmCase.status == status_filter)

    cases = db.scalars(query).all()
    return [enrich_case(db, c) for c in cases]


@app.get("/ufm-cases/export.csv")
def export_ufm_cases_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*sorted(REPORTS_ROLES))),
):
    """Simple CSV export of enriched cases (not PDF). Uses REPORTS_ROLES — not monitoring."""
    import csv
    import io
    import json

    from fastapi.responses import StreamingResponse

    query = select(UfmCase).order_by(UfmCase.created_at.desc(), UfmCase.id.desc())
    # Invigilator: own reported cases only (C22). Reviewing roles: reporting export.
    if current_user.role == "INVIGILATOR":
        query = query.where(UfmCase.reported_by == current_user.id)
    cases = db.scalars(query).all()
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
        # Phase C6 — operational completeness (append only; do not remove above)
        "recovered_materials",
        "recovered_other_detail",
        "description",
        "remarks",
        "exam_semester",
        "updated_at",
        "camera_id",
        "camera_code",
        "camera_name",
    ]

    def _csv_cell(value):
        if value is None:
            return ""
        if isinstance(value, datetime):
            # CSV policy (C30): UTC ISO-8601 with Z (same as API JSON).
            return to_api_iso(value) or ""
        if isinstance(value, (list, dict)):
            return json.dumps(value, separators=(",", ":"))
        return value

    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_cell(row.get(k)) for k in fieldnames})
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
    assert_can_access_case(db, current_user, case)
    # Optional: mark UNDER_REVIEW when HOD first opens a PENDING case.
    # Downstream roles must not mutate PENDING via direct GET (C17/C22).
    if current_user.role == "HOD" and case.status == "PENDING":
        case.status = "UNDER_REVIEW"
        case.updated_at = utc_now()
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
    # Row lock prevents lost updates when two reviewers act on the same case.
    case = db.scalar(
        select(UfmCase).where(UfmCase.id == case_id).with_for_update()
    )
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
    # One transition instant for action + resulting status (timeline ordering).
    # Avoid assigning case.updated_at before review.created_at default-on-flush,
    # which made "Current status" sort before the Forward that produced it.
    transition_at = utc_now()

    review = CaseReview(
        case_id=case.id,
        reviewer_id=current_user.id,
        reviewer_role=current_user.role,
        action=review_in.action.strip().upper(),
        remarks=review_in.remarks,
        signer_name=signer,
        signed_at=transition_at,
        created_at=transition_at,
        signature_ack=True,
    )
    previous_status = case.status
    case.status = new_status
    case.updated_at = transition_at

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

    status_label = _status_notify_label(new_status)
    previous_label = _status_notify_label(previous_status)

    # Notify reporter about every status change
    create_notification(
        db,
        user_id=case.reported_by,
        case_id=case.id,
        type="CASE_STATUS",
        title="Case status updated",
        message=(
            f"{case.case_number} is now {status_label} "
            f"(was {previous_label})."
        ),
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
            message=(
                f"{case.case_number} is now {status_label} "
                f"(was {previous_label})."
            ),
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
            message=(
                f"{case.case_number} is now {status_label} "
                f"and needs {next_role.replace('_', ' ').title()} action."
            ),
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
            db.flush()
            write_audit_log(
                db,
                user_id=current_user.id,
                action="RESULT_HOLD_CREATED",
                entity_type="result_control",
                entity_id=hold.id,
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
    # Internal reviewer / sign-off history is staff-only (frontend already skips
    # this for students). Do not expose remarks or signer details to STUDENT.
    if current_user.role == "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Review history is not available for student portal accounts",
        )
    case = db.get(UfmCase, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UFM case not found",
        )
    assert_can_access_case(db, current_user, case)
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
    current_user: User = Depends(require_roles(*sorted(EVIDENCE_UPLOAD_ROLES))),
):
    """Upload evidence attached to a UFM case. Invigilator-only (C28)."""
    case = db.get(UfmCase, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="UFM case not found for case_id",
        )
    # Invigilator may only attach evidence to cases they reported.
    assert_can_access_case(db, current_user, case)
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
    unlinked_only: bool = False,
    q: str | None = None,
    include_demo: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Evidence).order_by(Evidence.id)

    if current_user.role == "STUDENT":
        # Students only see evidence for their own cases; no detection-inbox browse.
        linked = resolve_linked_student(db, current_user)
        if linked is None:
            return []
        own_case_ids = list(
            db.scalars(
                select(UfmCase.id).where(UfmCase.student_id == linked.id)
            ).all()
        )
        if not own_case_ids:
            return []
        if case_id is not None:
            assert_can_access_case_id(db, current_user, case_id)
            query = query.where(Evidence.case_id == case_id)
        else:
            query = query.where(Evidence.case_id.in_(own_case_ids))
        if detection_id is not None:
            query = query.where(Evidence.detection_id == detection_id)
    elif current_user.role == "INVIGILATOR":
        # Own reported cases + orphan library rows (for attach-on-filing).
        own_case_ids = list(
            db.scalars(
                select(UfmCase.id).where(UfmCase.reported_by == current_user.id)
            ).all()
        )
        if case_id is not None:
            assert_can_access_case_id(db, current_user, case_id)
            query = query.where(Evidence.case_id == case_id)
        elif unlinked_only:
            query = query.where(Evidence.case_id.is_(None))
        else:
            if own_case_ids:
                query = query.where(
                    or_(
                        Evidence.case_id.in_(own_case_ids),
                        Evidence.case_id.is_(None),
                    )
                )
            else:
                query = query.where(Evidence.case_id.is_(None))
        if detection_id is not None:
            query = query.where(Evidence.detection_id == detection_id)
    else:
        if case_id is not None:
            assert_can_access_case_id(db, current_user, case_id)
            query = query.where(Evidence.case_id == case_id)
        if detection_id is not None:
            query = query.where(Evidence.detection_id == detection_id)
        if unlinked_only:
            query = query.where(Evidence.case_id.is_(None))

    if not include_demo:
        try:
            query = query.where(Evidence.is_demo.is_(False))
        except Exception:  # noqa: BLE001
            pass

    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        id_match = None
        if term.isdigit():
            id_match = int(term)
        clauses = [
            Evidence.evidence_type.ilike(like),
            Evidence.file_path.ilike(like),
        ]
        if id_match is not None:
            clauses.append(Evidence.id == id_match)
        query = query.where(or_(*clauses))

    return db.scalars(query).all()


def _assert_can_access_evidence_row(
    db: Session, current_user: User, row: Evidence
) -> None:
    """Enforce case ownership for case-linked evidence; staff may see orphans."""
    if row.case_id is not None:
        assert_can_access_case_id(db, current_user, row.case_id)
        return
    if current_user.role == "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this evidence",
        )


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
    view=false → original bytes with correct MIME + attachment filename (C32).
    """
    row = db.get(Evidence, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    _assert_can_access_evidence_row(db, current_user, row)

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

    media_type = resolve_evidence_media_type(path)
    download_name = preferred_download_filename(
        evidence_id=evidence_id,
        stored_path=path,
        media_type=media_type,
    )

    # Preview/Open may reuse this endpoint without view=; keep inline there.
    # Download (view=false, default) must be attachment so browsers save the file.
    disposition = "inline" if view else "attachment"

    return FileResponse(
        path,
        media_type=media_type,
        filename=download_name,
        content_disposition_type=disposition,
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
    row = db.get(Evidence, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    _assert_can_access_evidence_row(db, current_user, row)

    path = _resolve_evidence_path(row)
    if path is None:
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")

    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        media_type = resolve_evidence_media_type(path)
        return FileResponse(
            path,
            media_type=media_type,
            filename=preferred_download_filename(
                evidence_id=evidence_id,
                stored_path=path,
                media_type=media_type,
            ),
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

    if suffix == ".pdf" or resolve_evidence_media_type(path) == "application/pdf":
        media_type = "application/pdf"
        return FileResponse(
            path,
            media_type=media_type,
            filename=preferred_download_filename(
                evidence_id=evidence_id,
                stored_path=path,
                media_type=media_type,
            ),
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
        require_roles(
            "HOD",
            "DEC",
            "EXAM_DEPARTMENT",
            "UFM_COMMITTEE",
        )
    ),
):
    """Institutional UFM audit trail — not Administrator (use /admin/audit-logs)."""
    _ = current_user
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc())).all())
    actor_ids = {row.user_id for row in logs if row.user_id}
    roles_by_id: dict[int, str] = {}
    if actor_ids:
        for user in db.scalars(select(User).where(User.id.in_(actor_ids))).all():
            roles_by_id[user.id] = user.role
    return [
        AuditLogOut(
            id=row.id,
            user_id=row.user_id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            description=row.description,
            timestamp=row.timestamp,
            user_role=roles_by_id.get(row.user_id) if row.user_id else None,
        )
        for row in logs
    ]


@app.get("/audit-logs/export.csv")
def export_audit_logs_csv(
    action: str | None = None,
    entity_type: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "HOD",
            "DEC",
            "EXAM_DEPARTMENT",
            "UFM_COMMITTEE",
        )
    ),
):
    """CSV export of institutional audit events (SCOPE-025 lite). Not PDF."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    _ = current_user
    query = select(AuditLog).order_by(AuditLog.id.desc())
    action_f = (action or "").strip()
    entity_f = (entity_type or "").strip()
    search = (q or "").strip().lower()
    if action_f:
        query = query.where(AuditLog.action == action_f)
    if entity_f:
        query = query.where(AuditLog.entity_type == entity_f)
    logs = db.scalars(query).all()
    if search:
        logs = [
            row
            for row in logs
            if search
            in " ".join(
                [
                    row.action or "",
                    row.entity_type or "",
                    row.description or "",
                    str(row.user_id or ""),
                    str(row.entity_id if row.entity_id is not None else ""),
                ]
            ).lower()
        ]

    fieldnames = [
        "id",
        "timestamp",
        "user_id",
        "action",
        "entity_type",
        "entity_id",
        "description",
    ]

    def _csv_cell(value):
        if value is None:
            return ""
        return value

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in logs:
        writer.writerow(
            {
                "id": _csv_cell(row.id),
                "timestamp": _csv_cell(row.timestamp),
                "user_id": _csv_cell(row.user_id),
                "action": _csv_cell(row.action),
                "entity_type": _csv_cell(row.entity_type),
                "entity_id": _csv_cell(row.entity_id),
                "description": _csv_cell(row.description),
            }
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )

@app.get("/detections", response_model=list[DetectionOut])
def list_detections(
    confirmed_only: bool = False,
    unseen_only: bool = False,
    include_demo: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DETECTION_STAFF_ROLES)),
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
    current_user: User = Depends(require_roles(*DETECTION_STAFF_ROLES)),
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
    current_user: User = Depends(require_roles(*DETECTION_STAFF_ROLES)),
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
    current_user: User = Depends(require_roles("INVIGILATOR")),
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

    # Idempotent: one draft case per detection via evidence link or remarks.
    existing_ev = db.scalar(
        select(Evidence).where(
            Evidence.detection_id == detection_id,
            Evidence.case_id.is_not(None),
        )
    )
    if existing_ev is not None and existing_ev.case_id is not None:
        existing_case = db.get(UfmCase, existing_ev.case_id)
        if existing_case is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Detection already linked to case {existing_case.case_number} "
                    f"(id={existing_case.id})"
                ),
            )
    remark_hit = db.scalar(
        select(UfmCase).where(
            UfmCase.remarks.ilike(f"%source_detection_id={detection_id}%")
        )
    )
    if remark_hit is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Detection already used for draft case {remark_hit.case_number}"
            ),
        )

    assert_student_enrolled_if_roster(
        db, exam_id=body.exam_id, student_id=body.student_id
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
    return enrich_result_control(db, control)


@app.get("/result-controls", response_model=list[ResultControlOut])
def list_result_controls(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("EXAM_DEPARTMENT", "UFM_COMMITTEE")
    ),
):
    rows = db.scalars(select(ResultControl).order_by(ResultControl.id.desc())).all()
    return [enrich_result_control(db, row) for row in rows]


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
    control.released_at = utc_now()
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
    return enrich_result_control(db, control)


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

    already = db.scalar(
        select(Clarification).where(
            Clarification.case_id == case.id,
            Clarification.student_user_id == current_user.id,
        )
    )
    if already is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clarification already submitted for this case",
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
