import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import ConfirmDialog from "../components/ConfirmDialog";
import EvidenceLibraryPicker from "../components/EvidenceLibraryPicker";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import PortalSearchSelect from "../components/PortalSearchSelect";
import { fileNameFromPath } from "../config/casePresentation";
import {
  UFM_FORM_INSTITUTION,
  UFM_FORM_TITLE,
  RECOVERED_MATERIALS,
  mapDetectionToRecovered,
  primaryViolationFromRecovered,
  recoveredMaterialLabel,
} from "../config/ufmOfficialForm";
import {
  createCase,
  fetchDetections,
  fetchEvidence,
  fetchExamDetail,
  fetchExamEnrollments,
  fetchExamInvigilators,
  fetchExamRooms,
  fetchExams,
  fetchStudents,
  loadEvidenceObjectUrl,
  openEvidenceFile,
  downloadEvidenceFile,
} from "../services/api";
import { CASE_CREATE_ROLES, roleIn } from "../config/roleAccess";
import { formatDateTime } from "../config/dateTime";

import { useAuth } from "../context/AuthContext";

const CAN_CREATE = new Set(CASE_CREATE_ROLES);

function FormSection({ letter, title, children, className = "" }) {
  return (
    <section
      className={`ufm-form-section border-b border-slate-300 px-4 py-5 sm:px-6 ${className}`}
      aria-labelledby={`ufm-section-${letter}`}
    >
      <h2
        id={`ufm-section-${letter}`}
        className="mb-4 border-b border-slate-100 pb-2 text-sm font-bold uppercase tracking-wide text-au-navy"
      >
        <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded bg-au-navy text-[11px] font-bold normal-case text-white">
          {letter}
        </span>
        <span>{title}</span>
      </h2>
      {children}
    </section>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-0.5 break-words text-sm text-slate-900">
        {value || "—"}
      </dd>
    </div>
  );
}

export default function CreateCasePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canCreate = CAN_CREATE.has(user?.role);
  const [searchParams] = useSearchParams();
  const detectionId = searchParams.get("detection_id");

  const [allStudents, setAllStudents] = useState([]);
  const [exams, setExams] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [enrollmentIds, setEnrollmentIds] = useState(null); // null = open roster
  const [examDetail, setExamDetail] = useState(null);
  const [examLoadError, setExamLoadError] = useState("");
  const [examLoading, setExamLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [detection, setDetection] = useState(null);
  const [evidenceItems, setEvidenceItems] = useState([]);
  const [previews, setPreviews] = useState({});
  const [evidenceStatus, setEvidenceStatus] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [studentDetails, setStudentDetails] = useState({
    student_id: "",
    name: "",
    department: "",
    program: "",
  });
  const [examDetails, setExamDetails] = useState({
    course_code: "",
    course_name: "",
    semester: "",
    exam_date: "",
    start_time: "09:00",
    end_time: "12:00",
    room: "",
    room_id: null,
  });
  const [staffPool, setStaffPool] = useState([]);
  const [selectedStaffUserId, setSelectedStaffUserId] = useState("");
  const [staffDetails, setStaffDetails] = useState({
    name: "",
    email: "",
    staff_id: "",
    role: "",
  });
  const [libraryEvidence, setLibraryEvidence] = useState([]);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const [libraryPreviews, setLibraryPreviews] = useState({});

  const [form, setForm] = useState({
    student_id: "",
    exam_id: "",
    camera_id: "",
    recovered: [],
    recovered_other_detail: "",
    description: "",
    remarks: "",
    signer_name: user?.name || "",
    signature_ack: false,
  });

  const selectableStudents = useMemo(() => {
    if (enrollmentIds == null) return allStudents;
    if (enrollmentIds.length === 0) return [];
    const set = new Set(enrollmentIds.map(Number));
    return allStudents.filter((s) => set.has(s.id));
  }, [allStudents, enrollmentIds]);

  const selectedStudent = useMemo(
    () => selectableStudents.find((s) => String(s.id) === String(form.student_id)),
    [selectableStudents, form.student_id]
  );

  const displayedStudent = studentDetails;

  function applyStudentSelection(s) {
    setAllStudents((prev) => {
      if (prev.some((x) => x.id === s.id)) return prev;
      return [...prev, s];
    });
    setForm((prev) => ({ ...prev, student_id: String(s.id) }));
    setStudentDetails({
      student_id: s.student_id || "",
      name: s.name || "",
      department: s.department || "",
      program: s.program || "",
    });
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.student_id;
      delete next.manual_roll;
      delete next.manual_name;
      delete next.manual_department;
      delete next.manual_program;
      return next;
    });
  }

  function onStudentFieldChange(field, value) {
    setStudentDetails((p) => ({ ...p, [field]: value }));
    // Editing after a directory pick → treat as filing-time manual values.
    if (form.student_id) {
      setForm((prev) => ({ ...prev, student_id: "" }));
    }
    setFieldErrors((prev) => {
      if (!prev.manual_roll && !prev.manual_name && !prev.manual_department && !prev.manual_program) {
        return prev;
      }
      const next = { ...prev };
      delete next.manual_roll;
      delete next.manual_name;
      delete next.manual_department;
      delete next.manual_program;
      return next;
    });
  }

  function toTimeInput(value) {
    if (!value) return "";
    const s = String(value);
    return s.length >= 5 ? s.slice(0, 5) : s;
  }

  function toDateInput(value) {
    if (!value) return "";
    const s = String(value);
    return s.length >= 10 ? s.slice(0, 10) : s;
  }

  function formatRoomText(roomId) {
    if (roomId == null || roomId === "") return "";
    const room = rooms.find((r) => Number(r.id) === Number(roomId));
    if (!room) return `Room #${roomId}`;
    return [room.room_number, room.building].filter(Boolean).join(" · ");
  }

  function resolveRoomIdFromText(roomText) {
    const raw = (roomText || "").trim();
    if (!raw) return null;
    const lower = raw.toLowerCase();
    // Fallback label used when room catalog was not loaded yet: "Room #<id>"
    const idMatch = lower.match(/^room\s*#\s*(\d+)$/);
    if (idMatch) {
      const byId = rooms.find((r) => Number(r.id) === Number(idMatch[1]));
      if (byId) return byId.id;
      // Even if catalog row is missing, preserve numeric id for filing.
      return Number(idMatch[1]);
    }
    const exact = rooms.find(
      (r) => String(r.room_number).toLowerCase() === lower
    );
    if (exact) return exact.id;
    const labeled = rooms.find((r) => {
      const label = [r.room_number, r.building]
        .filter(Boolean)
        .join(" · ")
        .toLowerCase();
      const withPrefix = `room ${r.room_number}${
        r.building ? ` · ${r.building}` : ""
      }`.toLowerCase();
      return label === lower || withPrefix === lower;
    });
    if (labeled) return labeled.id;
    const contains = rooms.find((r) =>
      lower.includes(String(r.room_number).toLowerCase())
    );
    return contains ? contains.id : null;
  }

  function resolveManualRoomId() {
    if (examDetails.room_id != null && Number(examDetails.room_id) > 0) {
      return Number(examDetails.room_id);
    }
    return resolveRoomIdFromText(examDetails.room);
  }

  function applyExamSelection(e) {
    setExams((prev) => {
      if (prev.some((x) => x.id === e.id)) return prev;
      return [...prev, e];
    });
    setForm((prev) => ({ ...prev, exam_id: String(e.id) }));
    setExamDetails({
      course_code: e.course_code || "",
      course_name: e.course_name || "",
      semester: e.semester || "",
      exam_date: toDateInput(e.exam_date),
      start_time: toTimeInput(e.start_time) || "09:00",
      end_time: toTimeInput(e.end_time) || "12:00",
      room: formatRoomText(e.room_id),
      room_id:
        e.room_id != null && e.room_id !== "" ? Number(e.room_id) : null,
    });
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.exam_id;
      delete next.manual_course_code;
      delete next.manual_course_name;
      delete next.manual_semester;
      delete next.manual_exam_date;
      delete next.manual_room;
      return next;
    });
  }

  function onExamFieldChange(field, value) {
    setExamDetails((p) => {
      const next = { ...p, [field]: value };
      if (field === "room") {
        next.room_id = resolveRoomIdFromText(value);
      }
      return next;
    });
    if (form.exam_id) {
      setForm((prev) => ({ ...prev, exam_id: "" }));
    }
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.manual_course_code;
      delete next.manual_course_name;
      delete next.manual_semester;
      delete next.manual_exam_date;
      delete next.manual_room;
      return next;
    });
  }

  function applyStaffSelection(s) {
    setSelectedStaffUserId(String(s.user_id));
    setStaffDetails({
      name: s.user_name || "",
      email: s.user_email || "",
      staff_id: s.staff_id != null ? String(s.staff_id) : "",
      role: s.role || "",
    });
  }

  function onStaffFieldChange(field, value) {
    setStaffDetails((p) => ({ ...p, [field]: value }));
    if (selectedStaffUserId) {
      setSelectedStaffUserId("");
    }
  }

  const selectedExam = useMemo(
    () => exams.find((e) => String(e.id) === String(form.exam_id)),
    [exams, form.exam_id]
  );

  const displayedExam = examDetails;

  const selectedStaff = useMemo(
    () =>
      staffPool.find(
        (s) => String(s.user_id) === String(selectedStaffUserId)
      ),
    [staffPool, selectedStaffUserId]
  );

  const displayedStaff = useMemo(
    () => ({
      user_name: staffDetails.name,
      user_email: staffDetails.email,
      staff_id: staffDetails.staff_id,
      role: staffDetails.role || (selectedStaffUserId ? selectedStaff?.role : "Recorded on form"),
    }),
    [staffDetails, selectedStaffUserId, selectedStaff]
  );

  const searchStudents = useCallback(
    async (q) => {
      const rows = await fetchStudents(q);
      let list = Array.isArray(rows) ? rows : [];
      if (enrollmentIds != null && enrollmentIds.length > 0) {
        const allowed = new Set(enrollmentIds.map(Number));
        list = list.filter((s) => allowed.has(s.id));
      }
      return list;
    },
    [enrollmentIds]
  );

  const searchExams = useCallback(async (q) => {
    const rows = await fetchExams(q);
    return Array.isArray(rows) ? rows : [];
  }, []);

  const searchStaff = useCallback(
    async (q) => {
      const term = q.trim().toLowerCase();
      if (!term) return staffPool;
      return staffPool.filter((s) => {
        const hay = [
          s.user_name,
          s.user_email,
          s.user_id,
          s.staff_id,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return hay.includes(term);
      });
    },
    [staffPool]
  );

  const roomLabel = useMemo(() => {
    if (examDetails.room?.trim()) return examDetails.room.trim();
    const roomId = examDetail?.room_id ?? selectedExam?.room_id;
    return formatRoomText(roomId);
  }, [examDetails.room, examDetail, selectedExam, rooms]);

  const roomCameras = useMemo(() => {
    const cams = Array.isArray(examDetail?.room_cameras)
      ? examDetail.room_cameras
      : [];
    return cams.filter((c) => c && c.is_active !== false);
  }, [examDetail]);

  const detectionCameraLocked = detection?.camera_id != null;

  const selectedCameraLabel = useMemo(() => {
    if (detectionCameraLocked) {
      const fromRoom = roomCameras.find(
        (c) => Number(c.id) === Number(detection.camera_id)
      );
      if (fromRoom) {
        return `${fromRoom.camera_id}${fromRoom.name ? ` — ${fromRoom.name}` : ""}`;
      }
      return `Camera #${detection.camera_id}`;
    }
    const cam = roomCameras.find(
      (c) => String(c.id) === String(form.camera_id)
    );
    if (!cam) return "";
    return `${cam.camera_id}${cam.name ? ` — ${cam.name}` : ""}`;
  }, [
    detectionCameraLocked,
    detection,
    roomCameras,
    form.camera_id,
  ]);

  const examTimeLabel = useMemo(() => {
    const start =
      examDetails.start_time ||
      examDetail?.start_time ||
      selectedExam?.start_time;
    const end =
      examDetails.end_time || examDetail?.end_time || selectedExam?.end_time;
    if (!start && !end) return "";
    return [start, end].filter(Boolean).join(" – ");
  }, [examDetails, examDetail, selectedExam]);

  useEffect(() => {
    let cancelled = false;
    if (!canCreate) {
      setLoading(false);
      return undefined;
    }
    (async () => {
      try {
        const r = await fetchExamRooms().catch(() => []);
        if (cancelled) return;
        setRooms(Array.isArray(r) ? r : []);

        let linkedDetection = null;
        if (detectionId) {
          const all = await fetchDetections(false).catch(() => []);
          linkedDetection = (all || []).find(
            (d) => String(d.id) === String(detectionId)
          );
          if (!cancelled) setDetection(linkedDetection || null);
        }

        const recoveredFromDetection = linkedDetection
          ? mapDetectionToRecovered(linkedDetection.detection_type)
          : [];

        const linkedStudentId =
          linkedDetection?.student_id != null
            ? String(linkedDetection.student_id)
            : "";

        // Prefetch linked student / exam only when detection provides IDs
        if (linkedDetection?.student_id != null) {
          try {
            const students = await fetchStudents(
              String(linkedDetection.student_id)
            );
            const match = (Array.isArray(students) ? students : []).find(
              (s) => String(s.id) === String(linkedDetection.student_id)
            );
            if (match && !cancelled) {
              setAllStudents([match]);
              setStudentDetails({
                student_id: match.student_id || "",
                name: match.name || "",
                department: match.department || "",
                program: match.program || "",
              });
            }
          } catch {
            /* search later */
          }
        }
        if (linkedDetection?.exam_id != null) {
          try {
            const detail = await fetchExamDetail(linkedDetection.exam_id);
            if (detail && !cancelled) {
              setExams([detail]);
            }
          } catch {
            /* search later */
          }
        }

        setForm((prev) => ({
          ...prev,
          student_id: linkedStudentId,
          exam_id:
            linkedDetection?.exam_id != null
              ? String(linkedDetection.exam_id)
              : "",
          camera_id:
            linkedDetection?.camera_id != null
              ? String(linkedDetection.camera_id)
              : "",
          signer_name: prev.signer_name || user?.name || "",
          recovered: recoveredFromDetection,
          description: detectionId
            ? `Case filed from confirmed AI detection #${detectionId}${
                linkedDetection
                  ? ` (${linkedDetection.detection_type}, conf ${(
                      linkedDetection.confidence * 100
                    ).toFixed(0)}%).`
                  : "."
              }`
            : prev.description,
        }));
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load examination information.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [detectionId, user?.name, canCreate]);

  // Exam detail + enrollment roster
  useEffect(() => {
    if (!canCreate || !form.exam_id) {
      setExamDetail(null);
      setEnrollmentIds(null);
      setExamLoadError("");
      // Must clear loading when exam_id is cleared mid-fetch; otherwise the
      // in-flight request's cancelled=true path never resets examLoading and
      // "Submit UFM Report" stays disabled forever.
      setExamLoading(false);
      return undefined;
    }
    let cancelled = false;
    setExamLoading(true);
    setExamLoadError("");
    (async () => {
      try {
        const [detail, enrollments] = await Promise.all([
          fetchExamDetail(form.exam_id),
          fetchExamEnrollments(form.exam_id).catch(() => []),
        ]);
        if (cancelled) return;
        setExamDetail(detail || null);
        if (detail) {
          setExamDetails({
            course_code: detail.course_code || "",
            course_name: detail.course_name || "",
            semester: detail.semester || "",
            exam_date: toDateInput(detail.exam_date),
            start_time: toTimeInput(detail.start_time) || "09:00",
            end_time: toTimeInput(detail.end_time) || "12:00",
            room: formatRoomText(detail.room_id),
            room_id:
              detail.room_id != null && detail.room_id !== ""
                ? Number(detail.room_id)
                : null,
          });
        }
        const rows = Array.isArray(enrollments) ? enrollments : [];
        if (rows.length === 0) {
          setEnrollmentIds(null); // open enrollment
        } else {
          setEnrollmentIds(rows.map((r) => r.student_id));
        }
      } catch (err) {
        if (!cancelled) {
          setExamLoadError(
            err.message || "Unable to load examination information."
          );
          setExamDetail(null);
          setEnrollmentIds(null);
        }
      } finally {
        if (!cancelled) setExamLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [form.exam_id, canCreate]);

  // Replace temporary "Room #<id>" labels once the room catalog is available.
  useEffect(() => {
    if (!examDetails.room_id || rooms.length === 0) return;
    const current = (examDetails.room || "").trim();
    if (current && !/^room\s*#\s*\d+$/i.test(current)) return;
    const label = formatRoomText(examDetails.room_id);
    if (label && label !== current) {
      setExamDetails((prev) => ({ ...prev, room: label }));
    }
  }, [rooms, examDetails.room_id, examDetails.room]);

  // Examination staff pool (logged-in invigilator + exam assignments)
  useEffect(() => {
    if (!canCreate || !user) {
      setStaffPool([]);
      return undefined;
    }
    const self = {
      user_id: user.id,
      user_name: user.name,
      user_email: user.email,
      role: user.role,
    };
    if (!form.exam_id) {
      setStaffPool([self]);
      setSelectedStaffUserId((prev) => prev || String(user.id));
      setStaffDetails((prev) =>
        prev.name
          ? prev
          : {
              name: user.name || "",
              email: user.email || "",
              staff_id: "",
              role: user.role || "",
            }
      );
      return undefined;
    }
    let cancelled = false;
    (async () => {
      try {
        const rows = await fetchExamInvigilators(form.exam_id);
        if (cancelled) return;
        const map = new Map();
        const add = (entry) => {
          if (entry?.user_id == null) return;
          map.set(entry.user_id, entry);
        };
        add(self);
        (Array.isArray(rows) ? rows : []).forEach((r) =>
          add({ ...r, role: "INVIGILATOR" })
        );
        setStaffPool([...map.values()]);
        setSelectedStaffUserId((prev) =>
          prev && map.has(Number(prev)) ? prev : String(user.id)
        );
      } catch {
        if (!cancelled) {
          setStaffPool([self]);
          setSelectedStaffUserId(String(user.id));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [form.exam_id, canCreate, user]);

  // Library evidence previews
  useEffect(() => {
    if (!libraryEvidence.length) {
      setLibraryPreviews((prev) => {
        Object.values(prev).forEach((p) => {
          if (p?.url) URL.revokeObjectURL(p.url);
        });
        return {};
      });
      return undefined;
    }
    let cancelled = false;
    const objectUrls = [];
    (async () => {
      const next = {};
      for (const ev of libraryEvidence) {
        try {
          const { url, mime } = await loadEvidenceObjectUrl(ev.id, {
            preview: true,
          });
          if (cancelled) {
            URL.revokeObjectURL(url);
            continue;
          }
          objectUrls.push(url);
          next[ev.id] = { url, mime };
        } catch {
          /* metadata only */
        }
      }
      if (!cancelled) {
        setLibraryPreviews((prev) => {
          Object.values(prev).forEach((p) => {
            if (p?.url) URL.revokeObjectURL(p.url);
          });
          return next;
        });
      }
    })();
    return () => {
      cancelled = true;
      objectUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [libraryEvidence]);

  // Keep student_id valid when roster filters
  useEffect(() => {
    if (!form.student_id) return;
    const ok = selectableStudents.some(
      (s) => String(s.id) === String(form.student_id)
    );
    if (!ok) {
      setForm((prev) => ({ ...prev, student_id: "" }));
    }
  }, [selectableStudents, form.student_id]);

  // Prefill / constrain camera_id to exam room cameras (or detection camera)
  useEffect(() => {
    if (detectionCameraLocked && detection?.camera_id != null) {
      setForm((prev) =>
        String(prev.camera_id) === String(detection.camera_id)
          ? prev
          : { ...prev, camera_id: String(detection.camera_id) }
      );
      return;
    }
    if (!form.camera_id) return;
    const ok = roomCameras.some(
      (c) => String(c.id) === String(form.camera_id)
    );
    if (!ok) {
      setForm((prev) => ({ ...prev, camera_id: "" }));
    }
  }, [roomCameras, form.camera_id, detectionCameraLocked, detection]);

  // Detection evidence
  useEffect(() => {
    if (!canCreate || !detectionId) return undefined;

    let cancelled = false;
    let attempt = 0;
    const objectUrls = [];
    let retryTimer = null;

    async function loadOnce() {
      setEvidenceStatus((prev) => (prev === "ready" ? prev : "loading"));
      try {
        const rows = await fetchEvidence(null, detectionId);
        if (cancelled) return false;
        const list = Array.isArray(rows) ? rows : [];
        setEvidenceItems(list);

        if (list.length === 0) {
          setEvidenceStatus("empty");
          return false;
        }

        const next = {};
        for (const ev of list) {
          try {
            const { url, mime } = await loadEvidenceObjectUrl(ev.id, {
              preview: true,
            });
            if (cancelled) {
              URL.revokeObjectURL(url);
              continue;
            }
            objectUrls.push(url);
            next[ev.id] = { url, mime };
          } catch {
            /* metadata only */
          }
        }
        if (!cancelled) {
          setPreviews((prev) => {
            Object.values(prev).forEach((p) => {
              if (p?.url) URL.revokeObjectURL(p.url);
            });
            return next;
          });
          setEvidenceStatus("ready");
        }
        return true;
      } catch {
        if (!cancelled) setEvidenceStatus("empty");
        return false;
      }
    }

    (async () => {
      const ok = await loadOnce();
      if (ok || cancelled) return;
      retryTimer = setInterval(async () => {
        attempt += 1;
        const found = await loadOnce();
        if (found || attempt >= 6 || cancelled) {
          clearInterval(retryTimer);
          retryTimer = null;
        }
      }, 2000);
    })();

    return () => {
      cancelled = true;
      if (retryTimer) clearInterval(retryTimer);
      objectUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [detectionId, canCreate]);

  function onChange(event) {
    const { name, value, type, checked } = event.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
    setFieldErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }

  function toggleRecovered(code) {
    setForm((prev) => {
      const has = prev.recovered.includes(code);
      const recovered = has
        ? prev.recovered.filter((c) => c !== code)
        : [...prev.recovered, code];
      return {
        ...prev,
        recovered,
        recovered_other_detail:
          code === "OTHER" && has ? "" : prev.recovered_other_detail,
      };
    });
    setFieldErrors((prev) => {
      if (!prev.recovered && !prev.recovered_other_detail) return prev;
      const next = { ...prev };
      delete next.recovered;
      delete next.recovered_other_detail;
      return next;
    });
  }

  function buildStaffRemarksNote() {
    if (selectedStaffUserId) {
      if (
        selectedStaff &&
        user &&
        Number(selectedStaff.user_id) !== Number(user.id)
      ) {
        return `Examination staff on duty (selected record): ${selectedStaff.user_name}${
          selectedStaff.user_email ? ` (${selectedStaff.user_email})` : ""
        }`;
      }
      return "";
    }
    const name = staffDetails.name.trim();
    if (!name) return "";
    // Don't duplicate the reporting invigilator's own name into remarks.
    if (user?.name && name === user.name.trim() && !staffDetails.staff_id.trim()) {
      return "";
    }
    const parts = [name];
    if (staffDetails.email.trim()) parts.push(staffDetails.email.trim());
    if (staffDetails.staff_id.trim()) {
      parts.push(`ID ${staffDetails.staff_id.trim()}`);
    }
    return `Examination staff (manual entry — not a portal account): ${parts.join(" · ")}`;
  }

  function validate() {
    const errs = {};
    if (!form.exam_id) {
      if (!examDetails.course_code.trim()) {
        errs.manual_course_code = "Course code is required.";
      }
      if (!examDetails.course_name.trim()) {
        errs.manual_course_name = "Course name is required.";
      }
      if (!examDetails.semester.trim()) {
        errs.manual_semester = "Semester is required.";
      }
      if (!examDetails.exam_date.trim()) {
        errs.manual_exam_date = "Exam date is required.";
      }
      if (!examDetails.room.trim() && resolveManualRoomId() == null) {
        errs.manual_room = "Examination room is required.";
      } else if (resolveManualRoomId() == null) {
        errs.manual_room =
          "Room not found. Enter a registered room number (e.g. the catalog room number).";
      }
    }
    if (!form.student_id) {
      if (!studentDetails.student_id.trim()) {
        errs.manual_roll = "Roll number is required.";
      }
      if (!studentDetails.name.trim()) {
        errs.manual_name = "Student name is required.";
      }
      if (!studentDetails.department.trim()) {
        errs.manual_department = "Department is required.";
      }
      if (!studentDetails.program.trim()) {
        errs.manual_program = "Program is required.";
      }
    }
    if (!form.description.trim()) {
      errs.description = "Details of the UFM incident are required.";
    }
    if (!form.recovered.length) {
      errs.recovered = "Select at least one recovered / cheating material.";
    }
    if (
      form.recovered.includes("OTHER") &&
      !form.recovered_other_detail.trim()
    ) {
      errs.recovered_other_detail =
        "Explain the other cheating material when Other is selected.";
    }
    if (!form.signer_name.trim() || form.signer_name.trim().length < 2) {
      errs.signer_name = "Typed signature (full name) is required.";
    }
    if (!form.signature_ack) {
      errs.signature_ack =
        "You must acknowledge the digital sign-off certificate.";
    }
    if (enrollmentIds != null && enrollmentIds.length === 0) {
      errs.student_id = "No students are available for this examination.";
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function onReviewSubmit(event) {
    event.preventDefault();
    setError("");
    setSuccessMsg("");
    if (examLoading) {
      setError("Still loading examination details. Wait a moment, then try again.");
      requestAnimationFrame(() => {
        document
          .getElementById("ufm-submit-feedback")
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
      return;
    }
    if (!validate()) {
      setError("Please correct the highlighted fields before submitting.");
      requestAnimationFrame(() => {
        const firstInvalid =
          document.querySelector("[aria-invalid='true']") ||
          document.getElementById("ufm-submit-feedback");
        firstInvalid?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
      return;
    }
    setConfirmOpen(true);
  }

  async function doSubmit() {
    setSubmitting(true);
    setError("");
    try {
      const staffNote = buildStaffRemarksNote();
      const remarksCombined = [form.remarks.trim(), staffNote]
        .filter(Boolean)
        .join("\n\n");

      const libraryIds = libraryEvidence.map((ev) => ev.id);

      const payload = {
        violation_type: primaryViolationFromRecovered(form.recovered),
        description: form.description.trim(),
        remarks: remarksCombined || null,
        recovered_materials: form.recovered,
        recovered_other_detail: form.recovered.includes("OTHER")
          ? form.recovered_other_detail.trim()
          : null,
        detection_id: detectionId ? Number(detectionId) : null,
        camera_id: form.camera_id ? Number(form.camera_id) : null,
        evidence_ids: libraryIds.length ? libraryIds : undefined,
        signer_name: form.signer_name.trim(),
        signature_ack: true,
      };

      if (form.student_id) {
        payload.student_id = Number(form.student_id);
      } else {
        payload.manual_student = {
          student_id: studentDetails.student_id.trim(),
          name: studentDetails.name.trim(),
          department: studentDetails.department.trim(),
          program: studentDetails.program.trim(),
        };
      }

      if (form.exam_id) {
        payload.exam_id = Number(form.exam_id);
      } else {
        const roomId = resolveManualRoomId();
        if (roomId == null || Number(roomId) <= 0) {
          throw new Error(
            "Examination room could not be resolved. Enter a registered room number."
          );
        }
        const start = (examDetails.start_time || "09:00").trim();
        const end = (examDetails.end_time || "12:00").trim();
        payload.manual_exam = {
          course_code: examDetails.course_code.trim(),
          course_name: examDetails.course_name.trim(),
          semester: examDetails.semester.trim(),
          exam_date: examDetails.exam_date,
          start_time: start.length === 5 ? `${start}:00` : start,
          end_time: end.length === 5 ? `${end}:00` : end,
          room_id: Number(roomId),
        };
      }

      const created = await createCase(payload);
      setSuccessMsg("UFM incident submitted successfully.");
      setConfirmOpen(false);
      navigate(`/app/cases/${created.id}`);
    } catch (err) {
      setError(err.message || "Could not create case");
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  }

  if (!canCreate) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <p className="font-semibold">Report UFM Incident is not available</p>
        <p className="mt-1">
          Only invigilators can file new UFM cases from this portal.
          Committee recommendations and UMCC remarks are entered later by
          authorized reviewers — not on this form.
        </p>
        <Link
          to="/app/dashboard"
          className="mt-3 inline-flex text-sm font-semibold text-au-blue"
        >
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  if (loading) {
    return <LoadingState label="Loading exam information..." />;
  }

  const totalEvidenceCount =
    evidenceItems.length + libraryEvidence.length;

  const reviewSummary = [
    displayedStudent?.name
      ? `${displayedStudent.name} (${displayedStudent.student_id || "—"})`
      : "—",
    displayedExam?.course_code
      ? `${displayedExam.course_code} — ${displayedExam.course_name || ""}`
      : "—",
    form.recovered.map(recoveredMaterialLabel).join("; ") || "—",
    totalEvidenceCount
      ? `${totalEvidenceCount} evidence item(s)`
      : detectionId
        ? "Detection linked (evidence may attach on submit)"
        : "No evidence attached yet",
    user?.name || form.signer_name,
  ].join(" · ");

  const submitBlockedReason = examLoading
    ? "Loading examination details…"
    : submitting
      ? "Submitting UFM report…"
      : "";

  return (
    <div className="ufm-official-form mx-auto max-w-3xl space-y-4 print:max-w-none">
      <div className="print:hidden">
        <PageHeader
          breadcrumb="Home / Cases / Report UFM Incident"
          title="Report UFM Incident"
          description="Official Unfair Means (UFM) incident report for examination integrity review."
        />
      </div>

      {error ? (
        <div
          id="ufm-form-error"
          className="print:hidden rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          role="alert"
        >
          <p className="font-semibold">Unable to submit UFM incident.</p>
          <p className="mt-1">{error}</p>
        </div>
      ) : null}

      {successMsg ? (
        <div
          className="print:hidden rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
          role="status"
        >
          {successMsg}
        </div>
      ) : null}

      {rooms.length === 0 ? (
        <div className="print:hidden rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          No examination rooms are available for manual examination entry.
          Contact Exam Department if rooms are missing from the catalog.
        </div>
      ) : null}

      <form
        onSubmit={onReviewSubmit}
        className="overflow-hidden rounded-sm border border-slate-400 bg-white shadow-sm print:border-black print:shadow-none"
        noValidate
      >
        {/* Document header */}
        <header className="border-b-2 border-au-navy bg-slate-50 px-4 py-6 text-center sm:px-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-au-blue">
            {UFM_FORM_INSTITUTION}
          </p>
          <h1 className="mt-2 text-lg font-bold uppercase leading-snug text-au-navy sm:text-xl">
            {UFM_FORM_TITLE}
          </h1>
          <p className="mt-2 text-xs text-slate-600">
            Invigilator submission · Committee / UMCC sections completed later by
            authorized reviewers
          </p>
          {detectionId ? (
            <p className="mt-2 text-xs font-medium text-slate-700">
              Linked detection #{detectionId}
              {detection
                ? ` — ${String(detection.detection_type).replaceAll("_", " ")}`
                : ""}
            </p>
          ) : null}
        </header>

        {/* SECTION A — Student */}
        <FormSection letter="A" title="Student Information">
          <PortalSearchSelect
            label="Student roll number or name"
            placeholder="Search by roll number or name…"
            value={form.student_id}
            selectedItem={selectedStudent}
            onSelect={applyStudentSelection}
            onClear={() => {
              setForm((prev) => ({ ...prev, student_id: "" }));
            }}
            searchFn={searchStudents}
            getOptionKey={(s) => String(s.id)}
            formatOptionLabel={(s) => `${s.student_id} — ${s.name}`}
            renderOption={(s) => (
              <div className="min-w-0">
                <p className="font-semibold text-slate-900">
                  {s.student_id} — {s.name}
                </p>
                <p className="text-xs text-slate-600">
                  {[s.program, s.department].filter(Boolean).join(" · ")}
                </p>
              </div>
            )}
            disabled={enrollmentIds != null && enrollmentIds.length === 0}
            error={fieldErrors.student_id || ""}
            hint={
              enrollmentIds != null && enrollmentIds.length === 0
                ? "No students are enrolled in this examination."
                : enrollmentIds != null
                  ? "Only students enrolled in the selected examination appear in results."
                  : "Search to select an existing student (autofills below), or type the student details manually."
            }
            emptyMessage="No students found."
            loadingMessage="Searching students…"
          />

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="block sm:col-span-2">
              <span className="portal-label">
                Roll number <span className="text-red-600">*</span>
              </span>
              <input
                className="portal-input w-full"
                value={studentDetails.student_id}
                onChange={(e) =>
                  onStudentFieldChange("student_id", e.target.value)
                }
                aria-invalid={Boolean(fieldErrors.manual_roll)}
              />
              {fieldErrors.manual_roll ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_roll}
                </span>
              ) : null}
            </label>
            <label className="block">
              <span className="portal-label">
                Student name <span className="text-red-600">*</span>
              </span>
              <input
                className="portal-input w-full"
                value={studentDetails.name}
                onChange={(e) => onStudentFieldChange("name", e.target.value)}
                aria-invalid={Boolean(fieldErrors.manual_name)}
              />
              {fieldErrors.manual_name ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_name}
                </span>
              ) : null}
            </label>
            <label className="block">
              <span className="portal-label">
                Department <span className="text-red-600">*</span>
              </span>
              <input
                className="portal-input w-full"
                value={studentDetails.department}
                onChange={(e) =>
                  onStudentFieldChange("department", e.target.value)
                }
                aria-invalid={Boolean(fieldErrors.manual_department)}
              />
              {fieldErrors.manual_department ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_department}
                </span>
              ) : null}
            </label>
            <label className="block sm:col-span-2">
              <span className="portal-label">
                Program <span className="text-red-600">*</span>
              </span>
              <input
                className="portal-input w-full"
                value={studentDetails.program}
                onChange={(e) =>
                  onStudentFieldChange("program", e.target.value)
                }
                aria-invalid={Boolean(fieldErrors.manual_program)}
              />
              {fieldErrors.manual_program ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_program}
                </span>
              ) : null}
            </label>
            <p className="sm:col-span-2 text-xs text-slate-500">
              Selecting a directory match autofills these fields and links the
              existing student. Typing without a selection files with the
              values entered here (existing rolls are reused — no duplicate).
            </p>
          </div>
        </FormSection>

        {/* SECTION B — Examination */}
        <FormSection letter="B" title="Incident / Examination Information">
          <PortalSearchSelect
            label="Examination"
            placeholder="Search examination, course, or code…"
            value={form.exam_id}
            selectedItem={selectedExam}
            onSelect={applyExamSelection}
            onClear={() => setForm((prev) => ({ ...prev, exam_id: "" }))}
            searchFn={searchExams}
            getOptionKey={(e) => String(e.id)}
            formatOptionLabel={(e) =>
              `${e.course_code} — ${e.course_name}`
            }
            renderOption={(e) => (
              <div className="min-w-0">
                <p className="font-semibold text-slate-900">
                  {e.course_code} — {e.course_name}
                </p>
                <p className="text-xs text-slate-600">
                  {[e.exam_date, e.semester].filter(Boolean).join(" · ")}
                </p>
              </div>
            )}
            error={fieldErrors.exam_id || ""}
            hint="Search to select an existing examination (autofills below), or enter examination details manually."
            emptyMessage="No examinations found."
            loadingMessage="Searching examinations…"
          />

          {examLoading && form.exam_id ? (
            <p className="mt-3 text-sm text-slate-600">
              Loading exam information…
            </p>
          ) : null}
          {examLoadError ? (
            <p className="mt-3 text-sm text-red-700" role="alert">
              {examLoadError}
            </p>
          ) : null}

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="portal-label">
                Course code <span className="text-red-600">*</span>
              </span>
              <input
                className="portal-input w-full"
                value={examDetails.course_code}
                onChange={(e) =>
                  onExamFieldChange("course_code", e.target.value)
                }
              />
              {fieldErrors.manual_course_code ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_course_code}
                </span>
              ) : null}
            </label>
            <label className="block">
              <span className="portal-label">
                Course name <span className="text-red-600">*</span>
              </span>
              <input
                className="portal-input w-full"
                value={examDetails.course_name}
                onChange={(e) =>
                  onExamFieldChange("course_name", e.target.value)
                }
              />
              {fieldErrors.manual_course_name ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_course_name}
                </span>
              ) : null}
            </label>
            <label className="block">
              <span className="portal-label">
                Semester <span className="text-red-600">*</span>
              </span>
              <input
                className="portal-input w-full"
                value={examDetails.semester}
                onChange={(e) =>
                  onExamFieldChange("semester", e.target.value)
                }
              />
              {fieldErrors.manual_semester ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_semester}
                </span>
              ) : null}
            </label>
            <label className="block">
              <span className="portal-label">
                Exam date <span className="text-red-600">*</span>
              </span>
              <input
                type="date"
                className="portal-input w-full"
                value={examDetails.exam_date}
                onChange={(e) =>
                  onExamFieldChange("exam_date", e.target.value)
                }
              />
              {fieldErrors.manual_exam_date ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_exam_date}
                </span>
              ) : null}
            </label>
            <label className="block">
              <span className="portal-label">Start time</span>
              <input
                type="time"
                className="portal-input w-full"
                value={examDetails.start_time}
                onChange={(e) =>
                  onExamFieldChange("start_time", e.target.value)
                }
              />
            </label>
            <label className="block">
              <span className="portal-label">End time</span>
              <input
                type="time"
                className="portal-input w-full"
                value={examDetails.end_time}
                onChange={(e) =>
                  onExamFieldChange("end_time", e.target.value)
                }
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="portal-label">
                Examination room <span className="text-red-600">*</span>
              </span>
              <input
                className="portal-input w-full"
                value={examDetails.room}
                onChange={(e) => onExamFieldChange("room", e.target.value)}
                placeholder="Enter room number (e.g. A-101)"
                aria-invalid={Boolean(fieldErrors.manual_room)}
              />
              {fieldErrors.manual_room ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.manual_room}
                </span>
              ) : (
                <span className="mt-1 block text-xs text-slate-500">
                  Type the room number. Autofills when an existing examination
                  is selected.
                </span>
              )}
            </label>
            <p className="sm:col-span-2 text-xs text-slate-500">
              Creation date/time is recorded by the server when you submit
              {roomLabel ? ` · ${roomLabel}` : ""}
              {examTimeLabel ? ` · ${examTimeLabel}` : ""}
            </p>
          </div>

          {detectionCameraLocked ? (
            <div className="mt-4">
              <ReadOnlyField
                label="Camera (from detection)"
                value={selectedCameraLabel || "—"}
              />
              <p className="mt-1 text-xs text-slate-500">
                Camera is taken from the linked detection and cannot be changed.
              </p>
            </div>
          ) : (
            <label className="mt-4 block">
              <span className="portal-label">Camera</span>
              <select
                name="camera_id"
                value={form.camera_id}
                onChange={onChange}
                disabled={!form.exam_id || roomCameras.length === 0}
                className="portal-select w-full"
              >
                <option value="">
                  {roomCameras.length === 0
                    ? "No cameras registered for this exam room"
                    : "Select camera (optional)…"}
                </option>
                {roomCameras.map((cam) => (
                  <option key={cam.id} value={cam.id}>
                    {cam.camera_id}
                    {cam.name ? ` — ${cam.name}` : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
        </FormSection>

        {/* SECTION C — Incident details */}
        <FormSection letter="C" title="Details of UFM Incident">
          <label className="block">
            <span className="portal-label">
              Description of the unfair means incident{" "}
              <span className="text-red-600">*</span>
            </span>
            <textarea
              name="description"
              required
              rows={5}
              value={form.description}
              onChange={onChange}
              className="portal-textarea w-full"
              placeholder="Describe what happened, when it was observed, and any relevant circumstances…"
              aria-invalid={Boolean(fieldErrors.description)}
              aria-describedby={
                fieldErrors.description ? "err-description" : undefined
              }
            />
            {fieldErrors.description ? (
              <span
                id="err-description"
                className="mt-1 block text-xs text-red-600"
              >
                {fieldErrors.description}
              </span>
            ) : null}
          </label>

          <label className="mt-4 block">
            <span className="portal-label">Additional remarks (optional)</span>
            <textarea
              name="remarks"
              rows={2}
              value={form.remarks}
              onChange={onChange}
              className="portal-textarea w-full"
            />
          </label>
        </FormSection>

        {/* SECTION D — Recovered material */}
        <FormSection letter="D" title="Recovered / Confiscated Material">
          <p className="mb-3 text-sm text-slate-600">
            Select all categories that apply (official UFM form checklist).
          </p>
          <fieldset
            aria-invalid={Boolean(fieldErrors.recovered)}
            aria-describedby={
              fieldErrors.recovered ? "err-recovered" : undefined
            }
          >
            <legend className="sr-only">Recovered / cheating material</legend>
            <ul className="divide-y divide-slate-200 border border-slate-200">
              {RECOVERED_MATERIALS.map((item) => {
                const checked = form.recovered.includes(item.code);
                return (
                  <li key={item.code}>
                    <label className="portal-option flex cursor-pointer items-start gap-3 px-3 py-2.5 hover:bg-sky-200">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4 accent-au-blue"
                        checked={checked}
                        onChange={() => toggleRecovered(item.code)}
                      />
                      <span className="text-sm text-slate-800">{item.label}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
          {fieldErrors.recovered ? (
            <span id="err-recovered" className="mt-2 block text-xs text-red-600">
              {fieldErrors.recovered}
            </span>
          ) : null}

          {form.recovered.includes("OTHER") ? (
            <label className="mt-4 block">
              <span className="portal-label">
                Other cheating material — explanation{" "}
                <span className="text-red-600">*</span>
              </span>
              <textarea
                name="recovered_other_detail"
                rows={2}
                value={form.recovered_other_detail}
                onChange={onChange}
                className="portal-textarea w-full"
                aria-invalid={Boolean(fieldErrors.recovered_other_detail)}
                aria-describedby={
                  fieldErrors.recovered_other_detail
                    ? "err-recovered_other"
                    : undefined
                }
              />
              {fieldErrors.recovered_other_detail ? (
                <span
                  id="err-recovered_other"
                  className="mt-1 block text-xs text-red-600"
                >
                  {fieldErrors.recovered_other_detail}
                </span>
              ) : null}
            </label>
          ) : null}
        </FormSection>

        {/* SECTION E — Invigilator / staff */}
        <FormSection letter="E" title="Invigilator / Examination Staff Information">
          <p className="mb-3 text-xs text-slate-600">
            Reporting invigilator:{" "}
            <strong>{user?.name}</strong> ({user?.email}). This does not
            create or modify portal user accounts.
          </p>

          <PortalSearchSelect
            label="Examination staff"
            placeholder="Search by name, email, or user ID…"
            value={selectedStaffUserId}
            selectedItem={selectedStaff}
            onSelect={applyStaffSelection}
            onClear={() => setSelectedStaffUserId("")}
            searchFn={searchStaff}
            getOptionKey={(s) => String(s.user_id)}
            formatOptionLabel={(s) =>
              `${s.user_name || "Staff"}${s.user_email ? ` · ${s.user_email}` : ""}`
            }
            renderOption={(s) => (
              <div>
                <p className="font-semibold text-slate-900">
                  {s.user_name || `User #${s.user_id}`}
                </p>
                <p className="text-xs text-slate-600">
                  {[s.user_email, s.role].filter(Boolean).join(" · ")}
                </p>
              </div>
            )}
            hint="Search to select staff (autofills below), or enter staff details manually. Manual values are recorded in case remarks only."
            emptyMessage="No staff found."
            loadingMessage="Searching staff…"
            minSearchLength={0}
          />

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="portal-label">Staff name</span>
              <input
                className="portal-input w-full"
                value={staffDetails.name}
                onChange={(e) => onStaffFieldChange("name", e.target.value)}
              />
            </label>
            <label className="block">
              <span className="portal-label">Email (optional)</span>
              <input
                type="email"
                className="portal-input w-full"
                value={staffDetails.email}
                onChange={(e) => onStaffFieldChange("email", e.target.value)}
              />
            </label>
            <label className="block">
              <span className="portal-label">
                Employee / staff ID (optional)
              </span>
              <input
                className="portal-input w-full"
                value={staffDetails.staff_id}
                onChange={(e) =>
                  onStaffFieldChange("staff_id", e.target.value)
                }
              />
            </label>
            <label className="block">
              <span className="portal-label">Role</span>
              <input
                className="portal-input w-full"
                value={staffDetails.role}
                onChange={(e) => onStaffFieldChange("role", e.target.value)}
              />
            </label>
          </div>
        </FormSection>

        {/* SECTION F — Evidence */}
        <FormSection letter="F" title="Supporting Evidence">
          <div className="flex flex-wrap gap-2 print:hidden">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setLibraryPickerOpen(true)}
            >
              Attach from Evidence Library
            </button>
          </div>

          {libraryEvidence.length > 0 ? (
            <div className="mt-4 space-y-3">
              <p className="text-sm font-semibold text-au-navy">
                Selected from Evidence Library ({libraryEvidence.length})
              </p>
              <ul className="divide-y divide-slate-200 border border-slate-200">
                {libraryEvidence.map((ev) => {
                  const preview = libraryPreviews[ev.id];
                  const isImage = preview?.mime?.startsWith("image/");
                  return (
                    <li
                      key={ev.id}
                      className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-start sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-900">
                          #{ev.id} · {ev.evidence_type}
                        </p>
                        <p className="text-xs text-slate-600">
                          {fileNameFromPath(ev.file_path)}
                        </p>
                        {isImage ? (
                          <img
                            src={preview.url}
                            alt=""
                            className="mt-2 max-h-32 rounded border border-slate-200 object-contain"
                          />
                        ) : null}
                      </div>
                      <button
                        type="button"
                        className="btn-secondary shrink-0 text-xs"
                        onClick={() =>
                          setLibraryEvidence((prev) =>
                            prev.filter((x) => x.id !== ev.id)
                          )
                        }
                      >
                        Remove
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}

          {!detectionId ? (
            <p className="mt-3 text-sm text-slate-600">
              Link a confirmed detection from the Detections page for automatic
              evidence, or attach existing library records above.
            </p>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-slate-700">
                Automatically captured evidence from detection #{detectionId}
                {detection?.camera_id != null
                  ? ` · camera ${detection.camera_id}`
                  : ""}
                {detection?.created_at
                  ? ` · ${formatDateTime(detection.created_at)}`
                  : ""}
                . Attached count: {evidenceItems.length}.
              </p>
              {evidenceStatus === "loading" ? (
                <p className="text-xs text-slate-600">
                  Loading evidence preview…
                </p>
              ) : null}
              {evidenceStatus === "empty" ? (
                <p className="text-xs text-amber-800">
                  No evidence has been attached to this case yet. Snapshot/clip
                  may still be generating — you can submit and attach evidence
                  later.
                </p>
              ) : null}
              {evidenceItems.length > 0 ? (
                <div className="grid gap-3 sm:grid-cols-2 print:grid-cols-1">
                  {evidenceItems.map((ev) => {
                    const preview = previews[ev.id];
                    const isImage = preview?.mime?.startsWith("image/");
                    const isVideo = preview?.mime?.startsWith("video/");
                    return (
                      <div
                        key={ev.id}
                        className="overflow-hidden border border-slate-200 bg-white"
                      >
                        <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-1.5 print:hidden">
                          <span className="text-xs font-semibold uppercase tracking-wide text-au-navy">
                            {ev.evidence_type}
                          </span>
                          <div className="flex shrink-0 items-center gap-2">
                            <button
                              type="button"
                              className="text-xs font-semibold text-au-blue hover:underline"
                              onClick={async () => {
                                try {
                                  await openEvidenceFile(ev.id);
                                } catch (err) {
                                  setError(
                                    err.message || "Could not open evidence"
                                  );
                                }
                              }}
                            >
                              Open full
                            </button>
                            <button
                              type="button"
                              className="text-xs font-semibold text-slate-700 hover:underline"
                              onClick={async () => {
                                try {
                                  await downloadEvidenceFile(ev.id);
                                } catch (err) {
                                  setError(
                                    err.message || "Could not download evidence"
                                  );
                                }
                              }}
                            >
                              Download
                            </button>
                          </div>
                        </div>
                        <div className="bg-slate-100 print:hidden">
                          {isImage ? (
                            <img
                              src={preview.url}
                              alt={`${ev.evidence_type} from detection ${detectionId}`}
                              className="max-h-56 w-full object-contain"
                            />
                          ) : isVideo ? (
                            <video
                              src={preview.url}
                              controls
                              className="max-h-56 w-full bg-black"
                            />
                          ) : (
                            <div className="flex h-28 items-center justify-center px-3 text-center text-xs text-slate-600">
                              Preview unavailable. Use Open full or Download.
                            </div>
                          )}
                        </div>
                        <p className="hidden px-3 py-2 text-xs text-slate-700 print:block">
                          Evidence #{ev.id} · {ev.evidence_type}
                          {ev.confidence != null
                            ? ` · confidence ${(ev.confidence * 100).toFixed(0)}%`
                            : ""}
                        </p>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>
          )}
        </FormSection>

        {/* SECTION G — Committee (read-only for invigilator) */}
        <FormSection letter="G" title="Recommendations / Committee Review">
          <div className="border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <p className="font-semibold text-au-navy">Pending committee review</p>
            <p className="mt-1">
              Committee recommendations, UMCC remarks, and final decisions are
              entered later by authorized roles (HOD / DEC / UFM Committee) in
              the existing VigilantEye case-review workflow. Invigilators cannot
              finalize committee outcomes on this form.
            </p>
          </div>
        </FormSection>

        {/* SECTION H — Sign-off */}
        <FormSection
          letter="H"
          title="Remarks / Signatures / Submission"
          className="border-b-0"
        >
          <div className="space-y-3 border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-au-navy">
              Invigilator digital sign-off
            </p>
            <label className="block">
              <span className="portal-label">
                Full name (typed signature){" "}
                <span className="text-red-600">*</span>
              </span>
              <input
                name="signer_name"
                required
                minLength={2}
                value={form.signer_name}
                onChange={onChange}
                className="portal-input w-full bg-white"
                placeholder="Type your full name"
                aria-invalid={Boolean(fieldErrors.signer_name)}
              />
              {fieldErrors.signer_name ? (
                <span className="mt-1 block text-xs text-red-600">
                  {fieldErrors.signer_name}
                </span>
              ) : null}
            </label>
            <label className="flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                name="signature_ack"
                checked={form.signature_ack}
                onChange={onChange}
                className="mt-1 h-4 w-4 accent-au-blue"
                aria-invalid={Boolean(fieldErrors.signature_ack)}
              />
              <span>
                I certify that the information in this UFM incident report is
                accurate to the best of my knowledge (auditable acknowledgment).
              </span>
            </label>
            {fieldErrors.signature_ack ? (
              <span className="block text-xs text-red-600">
                {fieldErrors.signature_ack}
              </span>
            ) : null}
          </div>
        </FormSection>

        <div className="space-y-2 border-t border-slate-300 bg-slate-50 px-4 py-4 print:hidden sm:px-6">
          <div
            id="ufm-submit-feedback"
            className="min-h-[1.25rem] text-sm"
            aria-live="polite"
          >
            {error ? (
              <p className="font-medium text-red-700">{error}</p>
            ) : submitBlockedReason ? (
              <p className="text-slate-600">{submitBlockedReason}</p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={submitting || examLoading}
              className="btn-primary"
            >
              {submitting ? "Submitting UFM report..." : "Submit UFM Report"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => window.print()}
            >
              Print preview
            </button>
            <Link to="/app/cases" className="btn-secondary">
              Cancel
            </Link>
          </div>
        </div>
      </form>

      <EvidenceLibraryPicker
        open={libraryPickerOpen}
        onClose={() => setLibraryPickerOpen(false)}
        selectedIds={libraryEvidence.map((e) => e.id)}
        onApply={(rows) => {
          setLibraryEvidence(
            rows.map((r) => {
              const prev = libraryEvidence.find((e) => e.id === r.id);
              return prev && prev.evidence_type ? prev : r;
            })
          );
        }}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Confirm UFM report submission"
        message={`Please confirm before creating the UFM case: ${reviewSummary}`}
        confirmLabel={submitting ? "Submitting..." : "Confirm & submit"}
        cancelLabel="Back to form"
        tone="primary"
        busy={submitting}
        onConfirm={doSubmit}
        onCancel={() => {
          if (!submitting) setConfirmOpen(false);
        }}
      />
    </div>
  );
}
