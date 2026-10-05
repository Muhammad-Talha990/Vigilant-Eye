/**
 * Presentation helpers for the real UFM review workflow.
 * Mirrors backend/workflow.py and STATUS_NEXT_ROLE in main.py — labels only.
 * Do not invent transitions here.
 */

import {
  formatResultStatusLabel,
  formatRoleLabel,
  formatStatusLabel,
  RESPONSIBLE_BY_STATUS,
} from "./casePresentation";

/** role → action → allowed current statuses + resulting status (backend WORKFLOW). */
export const WORKFLOW_RULES = Object.freeze({
  HOD: {
    FORWARD: { from: ["PENDING", "UNDER_REVIEW"], to: "DEC_REVIEW" },
    RETURN: { from: ["DEC_REVIEW", "UNDER_REVIEW"], to: "PENDING" },
  },
  DEC: {
    FORWARD: { from: ["DEC_REVIEW"], to: "EXAM_DEPARTMENT_REVIEW" },
    RETURN: {
      from: ["DEC_REVIEW", "EXAM_DEPARTMENT_REVIEW"],
      to: "PENDING",
    },
  },
  EXAM_DEPARTMENT: {
    FORWARD: {
      from: ["EXAM_DEPARTMENT_REVIEW"],
      to: "UFM_COMMITTEE_REVIEW",
    },
    RETURN: {
      from: ["EXAM_DEPARTMENT_REVIEW", "UFM_COMMITTEE_REVIEW"],
      to: "PENDING",
    },
  },
  UFM_COMMITTEE: {
    APPROVE: { from: ["UFM_COMMITTEE_REVIEW"], to: "APPROVED" },
    REJECT: { from: ["UFM_COMMITTEE_REVIEW"], to: "REJECTED" },
  },
});

/** Who is notified / expected to act after a status (backend STATUS_NEXT_ROLE). */
export const STATUS_NEXT_ROLE = Object.freeze({
  PENDING: "HOD",
  UNDER_REVIEW: "HOD",
  DEC_REVIEW: "DEC",
  EXAM_DEPARTMENT_REVIEW: "EXAM_DEPARTMENT",
  UFM_COMMITTEE_REVIEW: "UFM_COMMITTEE",
});

const ACTION_MEANING = Object.freeze({
  FORWARD:
    "Send the reviewed case to the next institutional stage. This is not a final decision.",
  RETURN:
    "Send the case back to Pending so HOD can restart departmental review. This does not keep the case with the previous reviewer — status becomes Pending. Result control is unchanged.",
  APPROVE:
    "Record the final UFM Committee decision that the case is sustained. The case workflow ends. A result hold is applied automatically.",
  REJECT:
    "Record the final UFM Committee decision that the case is not sustained. The case workflow ends. No result hold is created by this action.",
});

const ACTION_BUTTON_HINT = Object.freeze({
  FORWARD: "Next stage",
  RETURN: "Back to Pending (HOD)",
  APPROVE: "Final decision · places hold",
  REJECT: "Final decision · no hold",
});

export function availableReviewActions(role, status) {
  const roleRules = WORKFLOW_RULES[role];
  if (!roleRules || !status) return [];
  return Object.entries(roleRules)
    .filter(([, rule]) => rule.from.includes(status))
    .map(([action]) => action);
}

export function actionMeaning(action) {
  return ACTION_MEANING[action] || "Records a review action on this UFM case.";
}

export function actionButtonHint(action) {
  return ACTION_BUTTON_HINT[action] || "";
}

/**
 * Predict outcome of a review action from the real workflow tables.
 * Returns null if the action is not allowed for role+status.
 */
export function resolveReviewOutcome(role, currentStatus, action) {
  const rule = WORKFLOW_RULES[role]?.[action];
  if (!rule || !rule.from.includes(currentStatus)) return null;

  const nextStatus = rule.to;
  const nextRole = STATUS_NEXT_ROLE[nextStatus] || null;
  const isFinal = nextStatus === "APPROVED" || nextStatus === "REJECTED";

  let resultImpact = "No change to result control.";
  if (action === "APPROVE") {
    resultImpact =
      "Creates an On Hold result control (transcript Blocked) if none exists for this case.";
  } else if (action === "REJECT") {
    resultImpact = "Does not create or release a result hold.";
  } else if (action === "RETURN" || action === "FORWARD") {
    resultImpact = "Does not create or release a result hold.";
  }

  let afterAction;
  if (isFinal) {
    afterAction = `Case status becomes ${formatStatusLabel(nextStatus)}. This is a final workflow decision.`;
  } else if (action === "RETURN") {
    afterAction = `Case status becomes ${formatStatusLabel(
      nextStatus
    )}. Responsibility returns to ${formatRoleLabel(
      nextRole
    )} to restart the review chain (not only the previous reviewer).`;
  } else {
    afterAction = `Case status becomes ${formatStatusLabel(
      nextStatus
    )}. Next responsible role: ${formatRoleLabel(nextRole)}.`;
  }

  return {
    action,
    currentStatus,
    nextStatus,
    nextRole,
    isFinal,
    resultImpact,
    afterAction,
    meaning: actionMeaning(action),
    buttonHint: actionButtonHint(action),
    studentNotified: true, // backend notifies linked student on every review status change
    reporterNotified: true,
  };
}

export function currentStageSummary(status) {
  const role = RESPONSIBLE_BY_STATUS[status];
  if (status === "APPROVED") {
    return {
      statusLabel: formatStatusLabel(status),
      responsibility: "Final decision recorded (Approved)",
      isFinal: true,
      note: "Case workflow is complete. Check Result Control for hold status.",
    };
  }
  if (status === "REJECTED") {
    return {
      statusLabel: formatStatusLabel(status),
      responsibility: "Final decision recorded (Rejected)",
      isFinal: true,
      note: "Case workflow is complete. Reject does not place a result hold.",
    };
  }
  return {
    statusLabel: formatStatusLabel(status),
    responsibility: role
      ? formatRoleLabel(role)
      : "No active operational owner",
    isFinal: false,
    note: role
      ? `${formatRoleLabel(role)} is expected to act while the case is in this status.`
      : null,
  };
}

export function resultImpactForCase(caseData) {
  const rc = caseData?.result_control;
  if (!rc) {
    if (caseData?.status === "APPROVED") {
      return "Approved — no result-control row linked yet.";
    }
    if (caseData?.status === "REJECTED") {
      return "Rejected — no result hold is created by reject.";
    }
    return "No result hold linked to this case yet (hold is created on Approve).";
  }
  return `Result ${formatResultStatusLabel(rc.result_status)} · Transcript ${formatStatusLabel(
    rc.transcript_status
  )}`;
}
