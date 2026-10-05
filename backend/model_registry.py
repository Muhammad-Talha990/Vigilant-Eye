"""Import all SQLAlchemy models so Base.metadata is complete (Alembic / bootstrap)."""

from __future__ import annotations

import models.audit_log  # noqa: F401
import models.camera  # noqa: F401
import models.case_review  # noqa: F401
import models.clarification  # noqa: F401
import models.detection  # noqa: F401
import models.exam  # noqa: F401
import models.exam_enrollment  # noqa: F401
import models.exam_invigilator  # noqa: F401
import models.exam_room  # noqa: F401
import models.evidence  # noqa: F401
import models.notification  # noqa: F401
import models.result_control  # noqa: F401
import models.student  # noqa: F401
import models.ufm_case  # noqa: F401
import models.user  # noqa: F401
from models.base import Base

__all__ = ["Base"]
