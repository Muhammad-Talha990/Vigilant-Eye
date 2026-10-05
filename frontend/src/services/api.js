const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("ve_token");
}

export async function apiRequest(path, options = {}) {
  const headers = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers || {}),
  };

  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const rawDetail =
      (data && data.detail) ||
      (typeof data === "string" ? data : null) ||
      null;
    let detail = null;
    if (typeof rawDetail === "string") {
      detail = rawDetail;
    } else if (Array.isArray(rawDetail)) {
      // FastAPI / Pydantic validation errors
      detail = rawDetail
        .map((item) => {
          if (!item || typeof item !== "object") return String(item);
          const loc = Array.isArray(item.loc)
            ? item.loc.filter((p) => p !== "body").join(".")
            : "";
          const msg = item.msg || item.message || "Invalid value";
          return loc ? `${loc}: ${msg}` : msg;
        })
        .filter(Boolean)
        .join("; ");
    } else if (rawDetail && typeof rawDetail === "object" && rawDetail.msg) {
      detail = String(rawDetail.msg);
    } else if (rawDetail != null) {
      detail = JSON.stringify(rawDetail);
    }

    // Prefer clear, non-technical messages for common HTTP statuses.
    if (response.status === 401) {
      detail =
        detail ||
        "Your session has expired or is invalid. Please sign in again.";
    } else if (response.status === 403) {
      detail =
        detail ||
        "You do not have permission to perform this action.";
    } else if (response.status === 404) {
      detail = detail || "The requested resource was not found.";
    } else if (response.status === 409) {
      detail = detail || "This action conflicts with the current state.";
    } else if (response.status === 422) {
      detail = detail || "Please check the form fields and try again.";
    } else if (response.status === 429) {
      detail = detail || "Too many requests. Please wait and try again.";
    } else if (response.status >= 500) {
      detail =
        "The server encountered an error. Please try again shortly.";
    } else if (!detail) {
      detail = `Request failed (${response.status})`;
    }

    const error = new Error(detail);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export async function loginRequest(email, password) {
  return apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function googleLoginRequest(idToken) {
  return apiRequest("/auth/google", {
    method: "POST",
    body: JSON.stringify({ id_token: idToken }),
  });
}

export async function fetchAuthConfig() {
  return apiRequest("/auth/config");
}

export async function fetchCurrentUser() {
  return apiRequest("/auth/me");
}

export async function fetchNotifications(unreadOnly = false) {
  const query = unreadOnly ? "?unread_only=true" : "";
  return apiRequest(`/notifications${query}`);
}

export async function markNotificationRead(id) {
  return apiRequest(`/notifications/${id}/read`, { method: "PATCH" });
}

export async function markAllNotificationsRead() {
  return apiRequest("/notifications/mark-all-read", { method: "POST" });
}

export async function fetchCases({ scope, status } = {}) {
  const params = new URLSearchParams();
  if (scope) params.set("scope", scope);
  if (status) params.set("status", status);
  const qs = params.toString();
  return apiRequest(`/ufm-cases${qs ? `?${qs}` : ""}`);
}

export async function fetchDetections(confirmedOnly = false, unseenOnly = false) {
  const params = new URLSearchParams();
  if (confirmedOnly) params.set("confirmed_only", "true");
  if (unseenOnly) params.set("unseen_only", "true");
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiRequest(`/detections${query}`);
}

export async function markDetectionSeen(detectionId) {
  return apiRequest(`/detections/${detectionId}/seen`, { method: "PATCH" });
}

export async function markAllDetectionsSeen() {
  return apiRequest("/detections/mark-all-seen?confirmed_only=true", {
    method: "POST",
  });
}

export async function fetchCameras() {
  return apiRequest("/cameras");
}

export async function fetchStudents(searchQuery = null) {
  const params = new URLSearchParams();
  if (searchQuery != null && String(searchQuery).trim()) {
    params.set("q", String(searchQuery).trim());
  }
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiRequest(`/students${qs}`);
}

export async function fetchExams(searchQuery = null) {
  const params = new URLSearchParams();
  if (searchQuery != null && String(searchQuery).trim()) {
    params.set("q", String(searchQuery).trim());
  }
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiRequest(`/exams${qs}`);
}

export async function fetchEvidenceLibrary(searchQuery = null) {
  const params = new URLSearchParams({ unlinked_only: "true" });
  if (searchQuery != null && String(searchQuery).trim()) {
    params.set("q", String(searchQuery).trim());
  }
  return apiRequest(`/evidence?${params.toString()}`);
}

export async function fetchCase(caseId) {
  return apiRequest(`/ufm-cases/${caseId}`);
}

export async function createCase(payload) {
  const body = { ...payload };
  if (Array.isArray(body.evidence_ids) && body.evidence_ids.length === 0) {
    delete body.evidence_ids;
  }
  return apiRequest("/ufm-cases", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchCaseReviews(caseId) {
  return apiRequest(`/ufm-cases/${caseId}/reviews`);
}

export async function createCaseReview(caseId, payload) {
  return apiRequest(`/ufm-cases/${caseId}/reviews`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createDraftCaseFromDetection(detectionId, payload) {
  return apiRequest(`/detections/${detectionId}/create-draft-case`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function casesCsvExportUrl() {
  const token = getToken() || "";
  const params = new URLSearchParams({ token });
  return `${API_URL}/ufm-cases/export.csv?${params.toString()}`;
}

export async function downloadCasesCsv() {
  const token = getToken();
  const response = await fetch(`${API_URL}/ufm-cases/export.csv`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `CSV export failed (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ufm_cases.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export async function fetchEvidence(caseId = null, detectionId = null) {
  const params = new URLSearchParams();
  if (caseId != null && caseId !== "") params.set("case_id", String(caseId));
  if (detectionId != null && detectionId !== "") {
    params.set("detection_id", String(detectionId));
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiRequest(`/evidence${query}`);
}

export async function uploadEvidence(formData) {
  return apiRequest("/evidence", {
    method: "POST",
    body: formData,
  });
}

/** Authenticated evidence file URL for <a href> / window.open with token query. */
export function evidenceFileUrl(evidenceId) {
  const token = getToken() || "";
  const params = new URLSearchParams({ token });
  // Prefer Bearer via fetch blob helper for browsers that ignore query auth
  return `${API_URL}/evidence/${evidenceId}/file?${params.toString()}`;
}

/** Fetch evidence bytes as an object URL for inline preview (caller must revoke). */
export async function loadEvidenceObjectUrl(
  evidenceId,
  { preview = false, previewOnly = false } = {}
) {
  const token = getToken();
  const tryPaths = preview
    ? previewOnly
      ? [
          `/evidence/${evidenceId}/preview`,
          `/evidence/${evidenceId}/file?view=true`,
        ]
      : [
          `/evidence/${evidenceId}/preview`,
          `/evidence/${evidenceId}/file?view=true`,
          `/evidence/${evidenceId}/file`,
        ]
    : [`/evidence/${evidenceId}/file`];

  let lastError = null;
  for (const path of tryPaths) {
    const response = await fetch(`${API_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      const text = await response.text();
      lastError = new Error(text || `Failed to load evidence (${response.status})`);
      continue;
    }

    const headerType = (response.headers.get("content-type") || "")
      .split(";")[0]
      .trim();
    const disposition = response.headers.get("content-disposition") || "";
    const buffer = await response.arrayBuffer();

    let filename =
      filenameFromContentDisposition(disposition) || `evidence-${evidenceId}`;
    let mime = "application/octet-stream";
    if (headerType && headerType !== "application/octet-stream") {
      mime = headerType;
    } else {
      mime =
        sniffMimeFromBytes(buffer) ||
        guessMimeFromName(filename) ||
        "application/octet-stream";
    }

    filename = ensureFilenameExtension(filename, mime, evidenceId);

    const blob = new Blob([buffer], { type: mime });
    return { url: URL.createObjectURL(blob), mime, filename };
  }
  throw lastError || new Error("Failed to load evidence");
}

/** Parse RFC 5987 / quoted Content-Disposition filenames (C32). */
export function filenameFromContentDisposition(disposition) {
  if (!disposition) return "";
  const star = /filename\*\s*=\s*(?:UTF-8''|utf-8'')([^;\s]+)/i.exec(
    disposition
  );
  if (star) {
    try {
      return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ""));
    } catch {
      // fall through
    }
  }
  const quoted = /filename\s*=\s*"([^"]+)"/i.exec(disposition);
  if (quoted) return quoted[1];
  const plain = /filename\s*=\s*([^;]+)/i.exec(disposition);
  if (plain) return plain[1].trim().replace(/^"|"$/g, "");
  return "";
}

export function sniffMimeFromBytes(buffer) {
  if (!buffer || buffer.byteLength < 4) return "";
  const u8 = new Uint8Array(buffer);
  const at = (i) => u8[i] ?? 0;
  // JPEG
  if (at(0) === 0xff && at(1) === 0xd8 && at(2) === 0xff) return "image/jpeg";
  // PNG
  if (
    at(0) === 0x89 &&
    at(1) === 0x50 &&
    at(2) === 0x4e &&
    at(3) === 0x47
  )
    return "image/png";
  // GIF
  if (at(0) === 0x47 && at(1) === 0x49 && at(2) === 0x46) return "image/gif";
  // BMP
  if (at(0) === 0x42 && at(1) === 0x4d) return "image/bmp";
  // WEBP (RIFF....WEBP)
  if (
    u8.byteLength >= 12 &&
    at(0) === 0x52 &&
    at(1) === 0x49 &&
    at(2) === 0x46 &&
    at(3) === 0x46 &&
    at(8) === 0x57 &&
    at(9) === 0x45 &&
    at(10) === 0x42 &&
    at(11) === 0x50
  )
    return "image/webp";
  // PDF
  if (at(0) === 0x25 && at(1) === 0x50 && at(2) === 0x44 && at(3) === 0x46)
    return "application/pdf";
  // MP4 (....ftyp)
  if (
    u8.byteLength >= 8 &&
    at(4) === 0x66 &&
    at(5) === 0x74 &&
    at(6) === 0x79 &&
    at(7) === 0x70
  )
    return "video/mp4";
  // WebM
  if (at(0) === 0x1a && at(1) === 0x45 && at(2) === 0xdf && at(3) === 0xa3)
    return "video/webm";
  // Plain text heuristic
  const n = Math.min(64, u8.byteLength);
  let textish = n > 0;
  for (let i = 0; i < n; i++) {
    const b = at(i);
    if (!(b === 9 || b === 10 || b === 13 || (b >= 32 && b <= 126))) {
      textish = false;
      break;
    }
  }
  if (textish) return "text/plain";
  return "";
}

function ensureFilenameExtension(filename, mime, evidenceId) {
  let name = String(filename || "").trim() || `evidence-${evidenceId}`;
  // Strip any path segments that slipped through Content-Disposition
  name = name.replace(/\\/g, "/").split("/").pop() || `evidence-${evidenceId}`;
  const ext = extensionForMime(mime);
  if (/\.[a-z0-9]+$/i.test(name)) {
    // Replace wrong/generic .bin when we know a better type.
    if (/\.bin$/i.test(name) && ext && ext !== ".bin") {
      return name.replace(/\.bin$/i, ext);
    }
    return name;
  }
  return `${name}${ext}`;
}

function isBrowserViewable(mime) {
  if (!mime) return false;
  if (mime.startsWith("image/")) return true;
  if (mime === "application/pdf") return true;
  // Browsers generally play these; AVI/MOV often force a download instead of viewing
  if (mime === "video/mp4" || mime === "video/webm") return true;
  return false;
}

function renderEvidenceViewer(win, { url, mime, filename }) {
  const safeName = String(filename || "evidence").replace(/[<>&"]/g, "");
  if (mime.startsWith("image/")) {
    win.document.open();
    win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>${safeName}</title>
<style>html,body{margin:0;height:100%;background:#0f172a}body{display:flex;align-items:center;justify-content:center}
img{max-width:100%;max-height:100vh;object-fit:contain}</style></head>
<body><img src="${url}" alt="${safeName}"/></body></html>`);
    win.document.close();
    return;
  }
  if (mime === "video/mp4" || mime === "video/webm") {
    win.document.open();
    win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>${safeName}</title>
<style>html,body{margin:0;height:100%;background:#0f172a}body{display:flex;align-items:center;justify-content:center}
video{max-width:100%;max-height:100vh}</style></head>
<body><video src="${url}" controls autoplay></video></body></html>`);
    win.document.close();
    return;
  }
  if (mime === "application/pdf") {
    win.location.href = url;
    return;
  }
  win.document.open();
  win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>${safeName}</title>
<style>body{font-family:system-ui,sans-serif;padding:2rem;color:#0f172a}</style></head>
<body><h1>Preview not available in browser</h1>
<p>This file type (<code>${mime || "unknown"}</code>) cannot be shown inline.</p>
<p>Close this tab and use <strong>Download</strong> on the portal.</p>
</body></html>`);
  win.document.close();
}

export async function openEvidenceFile(evidenceId) {
  // Open blank tab synchronously (user gesture) — never navigate the portal tab,
  // and never trigger a download from Open (Download button is separate).
  const win = window.open("about:blank", "_blank");

  try {
    let loaded = null;
    // 1) Browser-friendly preview (converts AVI/MP4 → animated WebP when needed)
    try {
      loaded = await loadEvidenceObjectUrl(evidenceId, {
        preview: true,
        previewOnly: true,
      });
    } catch {
      loaded = null;
    }
    // 2) Original file only if the browser can actually view it
    if (!loaded || !isBrowserViewable(loaded.mime)) {
      if (loaded?.url) URL.revokeObjectURL(loaded.url);
      const original = await loadEvidenceObjectUrl(evidenceId, { preview: false });
      if (isBrowserViewable(original.mime)) {
        loaded = original;
      } else {
        URL.revokeObjectURL(original.url);
        if (win && !win.closed) {
          win.document.open();
          win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Evidence</title>
<style>body{font-family:system-ui,sans-serif;padding:2rem}</style></head>
<body><h1>Cannot open this file in the browser</h1>
<p>Use the <strong>Download</strong> button to save and open it locally (e.g. AVI clips).</p>
</body></html>`);
          win.document.close();
        }
        return;
      }
    }

    if (win && !win.closed) {
      try {
        win.opener = null;
      } catch {
        // ignore
      }
      renderEvidenceViewer(win, loaded);
      setTimeout(() => URL.revokeObjectURL(loaded.url), 180_000);
      return;
    }

    // Popup blocked: do not download — user asked Open ≠ Download
    URL.revokeObjectURL(loaded.url);
    throw new Error(
      "Popup blocked. Allow popups for this site to Open evidence, or use Download."
    );
  } catch (err) {
    if (win && !win.closed) {
      try {
        win.document.open();
        win.document.write(
          `<!DOCTYPE html><html><body style="font-family:sans-serif;padding:2rem"><p>Could not open evidence.</p><p>${String(
            err.message || err
          )}</p></body></html>`
        );
        win.document.close();
      } catch {
        try {
          win.close();
        } catch {
          // ignore
        }
      }
    }
    throw err;
  }
}

export async function downloadEvidenceFile(evidenceId) {
  const { url, filename } = await loadEvidenceObjectUrl(evidenceId, {
    preview: false,
  });
  triggerDownload(url, filename);
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function guessMimeFromName(name) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  const map = {
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    gif: "image/gif",
    webp: "image/webp",
    bmp: "image/bmp",
    mp4: "video/mp4",
    webm: "video/webm",
    avi: "video/x-msvideo",
    mov: "video/quicktime",
    pdf: "application/pdf",
    txt: "text/plain",
  };
  return map[ext] || "application/octet-stream";
}

export function extensionForMime(mime) {
  const map = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/x-msvideo": ".avi",
    "video/quicktime": ".mov",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
  };
  return map[mime] || ".bin";
}

function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export async function fetchResultControls() {
  return apiRequest("/result-controls");
}

export async function releaseResultControl(controlId) {
  return apiRequest(`/result-controls/${controlId}/release`, {
    method: "PATCH",
  });
}

export async function fetchStudentProfile() {
  return apiRequest("/me/student-profile");
}

export async function fetchClarifications(caseId = null) {
  const query = caseId ? `?case_id=${caseId}` : "";
  return apiRequest(`/clarifications${query}`);
}

export async function submitClarification(payload) {
  return apiRequest("/clarifications", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchAuditLogs() {
  return apiRequest("/audit-logs");
}

export async function downloadAuditLogsCsv({
  action = "",
  entity_type = "",
  q = "",
} = {}) {
  const token = getToken();
  const params = new URLSearchParams();
  if (action) params.set("action", action);
  if (entity_type) params.set("entity_type", entity_type);
  if (q) params.set("q", q);
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_URL}/audit-logs/export.csv${query}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Audit CSV export failed (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "audit_logs.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export async function fetchUsers(
  role = null,
  { unlinkedStudentsOnly = false, staffOnly = false } = {}
) {
  const params = new URLSearchParams();
  if (role) params.set("role", role);
  if (unlinkedStudentsOnly) params.set("unlinked_students_only", "true");
  if (staffOnly) params.set("staff_only", "true");
  const query = params.toString() ? `?${params}` : "";
  return apiRequest(`/users${query}`);
}

export async function createUser(payload) {
  return apiRequest("/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchExamRooms() {
  return apiRequest("/exam-rooms");
}

export async function createExamRoom(payload) {
  return apiRequest("/exam-rooms", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createCamera(payload) {
  return apiRequest("/cameras", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createExam(payload) {
  return apiRequest("/exams", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateExam(examId, payload) {
  return apiRequest(`/exams/${examId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchExamDetail(examId) {
  return apiRequest(`/exams/${examId}`);
}

export async function enrollExamStudent(examId, studentId) {
  return apiRequest(`/exams/${examId}/enrollments`, {
    method: "POST",
    body: JSON.stringify({ student_id: studentId }),
  });
}

export async function fetchExamEnrollments(examId) {
  return apiRequest(`/exams/${examId}/enrollments`);
}

export async function removeExamEnrollment(examId, enrollmentId) {
  return apiRequest(`/exams/${examId}/enrollments/${enrollmentId}`, {
    method: "DELETE",
  });
}

export async function assignExamInvigilator(examId, userId) {
  return apiRequest(`/exams/${examId}/invigilators`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function fetchExamInvigilators(examId) {
  return apiRequest(`/exams/${examId}/invigilators`);
}

export async function removeExamInvigilator(examId, assignmentId) {
  return apiRequest(`/exams/${examId}/invigilators/${assignmentId}`, {
    method: "DELETE",
  });
}

export async function createStudent(payload) {
  return apiRequest("/students", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function linkStudentUser(studentPk, userId) {
  return apiRequest(`/students/${studentPk}/link-user`, {
    method: "PATCH",
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function fetchLiveStatus() {
  return apiRequest("/live/status");
}

export async function startLiveCamera(cameraId, payload = {}) {
  return apiRequest(`/live/cameras/${cameraId}/start`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function stopLiveCamera(cameraId) {
  return apiRequest(`/live/cameras/${cameraId}/stop`, {
    method: "POST",
  });
}

export async function testCameraSource(streamUrl) {
  return apiRequest("/live/test-source", {
    method: "POST",
    body: JSON.stringify({ stream_url: streamUrl }),
  });
}

/** MJPEG URL for <img src> — token query because img cannot set Authorization. */
export function liveMjpegUrl(cameraId, { cacheBust } = {}) {
  const token = getToken() || "";
  const params = new URLSearchParams({ token });
  if (cacheBust) params.set("t", String(cacheBust));
  return `${API_URL}/live/cameras/${cameraId}/mjpeg?${params.toString()}`;
}

export async function fetchAdminUserStats() {
  return apiRequest("/admin/users/stats");
}

export async function fetchAdminUsers(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  });
  const qs = q.toString() ? `?${q}` : "";
  return apiRequest(`/admin/users${qs}`);
}

export async function fetchAdminUser(userId) {
  return apiRequest(`/admin/users/${userId}`);
}

export async function createAdminUser(payload) {
  return apiRequest("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function patchAdminUser(userId, payload) {
  return apiRequest(`/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function activateAdminUser(userId) {
  return apiRequest(`/admin/users/${userId}/activate`, { method: "POST" });
}

export async function deactivateAdminUser(userId) {
  return apiRequest(`/admin/users/${userId}/deactivate`, { method: "POST" });
}

export async function previewAdminUserImport(file) {
  const form = new FormData();
  form.append("file", file);
  return apiRequest("/admin/users/import/preview", {
    method: "POST",
    body: form,
  });
}

export async function confirmAdminUserImport(rows) {
  return apiRequest("/admin/users/import", {
    method: "POST",
    body: JSON.stringify({ rows }),
  });
}

export async function fetchAdminAuditLogs(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  });
  const qs = q.toString() ? `?${q}` : "";
  return apiRequest(`/admin/audit-logs${qs}`);
}

export async function fetchAdminStudents(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  });
  const qs = q.toString() ? `?${q}` : "";
  return apiRequest(`/admin/students${qs}`);
}

export async function fetchAdminSystemInfo() {
  return apiRequest("/admin/system-info");
}

export async function sendAdminTestEmail() {
  return apiRequest("/admin/email/test", { method: "POST" });
}

export async function fetchAdminRoles() {
  return apiRequest("/admin/roles");
}

export { API_URL };
