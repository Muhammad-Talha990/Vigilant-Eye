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
    const detail =
      (data && data.detail) ||
      (typeof data === "string" ? data : null) ||
      `Request failed (${response.status})`;
    const error = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
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

export async function fetchCases() {
  return apiRequest("/ufm-cases");
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

export async function fetchStudents() {
  return apiRequest("/students");
}

export async function fetchExams() {
  return apiRequest("/exams");
}

export async function fetchCase(caseId) {
  return apiRequest(`/ufm-cases/${caseId}`);
}

export async function createCase(payload) {
  return apiRequest("/ufm-cases", {
    method: "POST",
    body: JSON.stringify(payload),
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
    const nameMatch = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(disposition);
    let filename = nameMatch
      ? decodeURIComponent(nameMatch[1].replace(/"/g, ""))
      : `evidence-${evidenceId}`;

    const buffer = await response.arrayBuffer();
    const mime =
      headerType && headerType !== "application/octet-stream"
        ? headerType
        : guessMimeFromName(filename);
    if (!/\.[a-z0-9]+$/i.test(filename)) {
      filename += extensionForMime(mime);
    }

    const blob = new Blob([buffer], { type: mime });
    return { url: URL.createObjectURL(blob), mime, filename };
  }
  throw lastError || new Error("Failed to load evidence");
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
  };
  return map[ext] || "application/octet-stream";
}

function extensionForMime(mime) {
  const map = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/x-msvideo": ".avi",
    "application/pdf": ".pdf",
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

export { API_URL };
