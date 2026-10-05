/** Presentation helpers for UFM cases — labels only; no API/status changes. */

import { apiDateTimeMs, formatDateTime } from "./dateTime.js";
import { ROLE_LABELS } from "./navByRole.js";

/**
 * Format a case creation timestamp (Asia/Karachi via C30 dateTime utility).
 */
export function formatCaseCreatedAt(iso) {
  return formatDateTime(iso);
}

export const STATUS_LABELS = {
  PENDING: "Pending",
  UNDER_REVIEW: "Under Review",
  DEC_REVIEW: "DEC Review",
  EXAM_DEPARTMENT_REVIEW: "Exam Department Review",
  UFM_COMMITTEE_REVIEW: "UFM Committee Review",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  HELD: "On Hold",
  RELEASED: "Released",
  BLOCKED: "Blocked",
  ALLOWED: "Allowed",
  SUBMITTED: "Submitted",
  CLOSED: "Closed",
};

/** Result-control specific labels (distinct from UFM case status). */
export const RESULT_STATUS_LABELS = {
  HELD: "On Hold",
  RELEASED: "Released",
};

export const REVIEW_ACTION_LABELS = {
  FORWARD: "Forward",
  RETURN: "Return",
  APPROVE: "Approve",
  REJECT: "Reject",
};

/** Role currently expected to act, based on case status (presentation only). */
export const RESPONSIBLE_BY_STATUS = {
  PENDING: "HOD",
  UNDER_REVIEW: "HOD",
  DEC_REVIEW: "DEC",
  EXAM_DEPARTMENT_REVIEW: "EXAM_DEPARTMENT",
  UFM_COMMITTEE_REVIEW: "UFM_COMMITTEE",
};

export function formatStatusLabel(status) {
  if (!status) return "Unknown";
  return STATUS_LABELS[status] || String(status).replaceAll("_", " ");
}

export function formatResultStatusLabel(status) {
  if (!status) return "Unknown";
  return RESULT_STATUS_LABELS[status] || formatStatusLabel(status);
}

export function formatReviewActionLabel(action) {
  if (!action) return "Action";
  return REVIEW_ACTION_LABELS[action] || String(action).replaceAll("_", " ");
}

export function formatViolationLabel(type) {
  if (!type) return "—";
  return String(type).replaceAll("_", " ");
}

export function formatRoleLabel(role) {
  if (!role) return "—";
  return ROLE_LABELS[role] || String(role).replaceAll("_", " ");
}

export function responsibleLabelForStatus(status) {
  const role = RESPONSIBLE_BY_STATUS[status];
  if (!role) {
    if (status === "APPROVED" || status === "REJECTED") return "Decision recorded";
    return null;
  }
  return formatRoleLabel(role);
}

export function fileNameFromPath(path) {
  if (!path) return null;
  const parts = String(path).replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

/** Human-readable evidence type (API values unchanged). */
export function formatEvidenceTypeLabel(type) {
  return formatViolationLabel(type);
}

/**
 * Source label from real evidence fields only.
 * Does not invent provenance beyond detection / camera / manual upload.
 */
export function evidenceSourceLabel(evidence) {
  if (!evidence) return "—";
  if (evidence.detection_id != null) {
    const conf =
      evidence.confidence != null
        ? ` · ${(Number(evidence.confidence) * 100).toFixed(0)}% confidence (system)`
        : "";
    return `AI detection #${evidence.detection_id}${conf}`;
  }
  if (evidence.camera_id != null) return `Camera ${evidence.camera_id}`;
  return "Manual upload";
}

export function evidenceHasAiSignal(evidence) {
  return (
    evidence &&
    (evidence.detection_id != null || evidence.confidence != null)
  );
}

/** Reviewer display: prefer typed sign-off name; never invent a display name. */
export function reviewActorLabel(review) {
  if (!review) return "—";
  if (review.signer_name) return review.signer_name;
  if (review.reviewer_id != null) return `User #${review.reviewer_id}`;
  return "—";
}

export function formatAuditActionLabel(action) {
  if (!action) return "—";
  return String(action).replaceAll("_", " ");
}

export function formatEntityTypeLabel(entityType) {
  if (!entityType) return "—";
  const map = {
    ufm_case: "UFM Case",
    result_control: "Result Hold",
    evidence: "Evidence",
    clarification: "Clarification",
    detection: "Detection",
    user: "User",
  };
  return map[entityType] || String(entityType).replaceAll("_", " ");
}

/** Numeric actor ids only — do not invent names. */
export function formatUserIdLabel(userId) {
  if (userId == null || userId === "") return "—";
  return `User #${userId}`;
}

/**
 * Timeline event kinds — lower values sort first when timestamps are equal.
 * Workflow semantics: action/transition (review) → resulting status.
 */
export const TIMELINE_KIND_ORDER = {
  created: 10,
  signoff: 20,
  evidence: 30,
  clarification: 40,
  review: 50,
  status: 60,
};

function timelineTimeMs(iso) {
  return apiDateTimeMs(iso);
}

/**
 * Deterministic timeline ordering:
 * 1) chronological timestamp (sortAt if set, else at)
 * 2) kind order — review/action before resulting status
 * 3) stable id
 */
export function compareTimelineEvents(a, b) {
  const ta = timelineTimeMs(a.sortAt ?? a.at);
  const tb = timelineTimeMs(b.sortAt ?? b.at);
  if (ta !== tb) return ta - tb;
  const ka = TIMELINE_KIND_ORDER[a.kind] ?? 100;
  const kb = TIMELINE_KIND_ORDER[b.kind] ?? 100;
  if (ka !== kb) return ka - kb;
  return String(a.id).localeCompare(String(b.id));
}

/**
 * Build a chronological timeline from real case / review / evidence / clarification data.
 * Does not invent stages that have no backing records.
 *
 * Ordering rule: when a workflow action and the resulting/current status share a
 * transition timestamp (or historical ms skew where status.updated_at precedes
 * review.created_at), the action is shown before the resulting status.
 */
export function buildCaseTimeline({
  caseData,
  reviews = [],
  evidence = [],
  clarifications = [],
  includeEvidence = true,
  includeClarifications = true,
  includeReviews = true,
  includeCreateSignOff = true,
  includeReporterDetail = true,
  includeResponsibleDetail = true,
}) {
  if (!caseData) return [];
  const events = [];

  events.push({
    id: `created-${caseData.id}`,
    kind: "created",
    at: caseData.created_at,
    title: "Case created",
    detail: includeReporterDetail
      ? [
          caseData.reporter_name || null,
          caseData.reporter_role
            ? formatRoleLabel(caseData.reporter_role)
            : null,
        ]
          .filter(Boolean)
          .join(" · ")
      : null,
  });

  if (
    includeCreateSignOff &&
    (caseData.signed_at || caseData.signer_name)
  ) {
    events.push({
      id: `create-signoff-${caseData.id}`,
      kind: "signoff",
      at: caseData.signed_at || caseData.created_at,
      title: "Create sign-off recorded",
      detail: caseData.signer_name || null,
    });
  }

  if (includeEvidence) {
    for (const e of evidence) {
      events.push({
        id: `evidence-${e.id}`,
        kind: "evidence",
        at: e.created_at || e.timestamp,
        title: "Evidence attached",
        detail: [
          e.evidence_type ? formatEvidenceTypeLabel(e.evidence_type) : null,
          e.detection_id != null ? `Linked detection #${e.detection_id}` : null,
        ]
          .filter(Boolean)
          .join(" · "),
      });
    }
  }

  if (includeClarifications) {
    for (const c of clarifications) {
      events.push({
        id: `clarification-${c.id}`,
        kind: "clarification",
        at: c.created_at,
        title: "Student clarification submitted",
        detail: c.status ? formatStatusLabel(c.status) : null,
      });
    }
  }

  let latestReviewMs = null;
  if (includeReviews) {
    for (const r of reviews) {
      const at = r.created_at || r.signed_at;
      const ms = timelineTimeMs(at);
      if (Number.isFinite(ms)) {
        latestReviewMs =
          latestReviewMs == null ? ms : Math.max(latestReviewMs, ms);
      }
      events.push({
        id: `review-${r.id}`,
        kind: "review",
        at,
        title: `${formatReviewActionLabel(r.action)} · ${formatRoleLabel(r.reviewer_role)}`,
        detail: [
          r.remarks || null,
          r.signer_name ? `Signed: ${r.signer_name}` : null,
        ]
          .filter(Boolean)
          .join(" · "),
      });
    }
  }

  const statusAt = caseData.updated_at || caseData.created_at;
  const statusMs = timelineTimeMs(statusAt);
  // Historical rows may have updated_at slightly before review.created_at
  // (previous backend assigned them in two utcnow() calls). Keep displayed
  // `at` as the real case.updated_at; for sort only, align with the latest
  // transition so action → status still holds.
  let statusSortAt = statusAt;
  if (
    latestReviewMs != null &&
    Number.isFinite(statusMs) &&
    latestReviewMs > statusMs
  ) {
    statusSortAt = new Date(latestReviewMs).toISOString();
  }

  events.push({
    id: `status-${caseData.id}-${caseData.status}`,
    kind: "status",
    at: statusAt,
    sortAt: statusSortAt,
    title: `Current status: ${formatStatusLabel(caseData.status)}`,
    detail: includeResponsibleDetail
      ? responsibleLabelForStatus(caseData.status)
      : null,
    current: true,
  });

  return events.filter((e) => e.at).sort(compareTimelineEvents);
}
