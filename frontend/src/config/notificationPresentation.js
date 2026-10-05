/**
 * Presentation helpers for notification records returned by GET /notifications.
 * Categories are derived only from known backend `type` values — never from message text.
 */

import {
  DETECTION_ROLES,
  RESULT_CONTROL_ROLES,
  roleIn,
} from "./roleAccess";

export function formatNotificationType(type) {
  return String(type || "NOTICE").replaceAll("_", " ");
}

/** User-facing category from known API type values only. */
export function categoryForNotificationType(type) {
  switch (type) {
    case "CASE_ACTION_REQUIRED":
      return "Action Required";
    case "CASE_CREATED":
    case "CASE_STATUS":
    case "CLARIFICATION":
      return "Case Update";
    case "RESULT_HOLD":
    case "RESULT_RELEASED":
      return "Result Control";
    case "DETECTION_ALERT":
      return "Detection Alert";
    default:
      return "Information";
  }
}

/**
 * Navigation target for a notification, role-aware so users are not
 * sent to pages their C11-B role cannot open.
 */
export function destinationForNotification(note, role) {
  if (!note) return null;
  if (note.case_id) return `/app/cases/${note.case_id}`;

  if (role === "STUDENT") return null;
  if (role === "ADMINISTRATOR") return "/app/notifications";

  if (note.type === "DETECTION_ALERT") {
    return roleIn(role, DETECTION_ROLES) ? "/app/detections" : null;
  }
  if (note.type === "RESULT_HOLD" || note.type === "RESULT_RELEASED") {
    return roleIn(role, RESULT_CONTROL_ROLES) ? "/app/result-controls" : null;
  }
  return null;
}

export function actionLabelForNotification(note, role) {
  const dest = destinationForNotification(note, role);
  if (!dest) return null;
  if (note.case_id) return "Open case";
  if (note.type === "DETECTION_ALERT") return "Open detections";
  if (note.type === "RESULT_HOLD" || note.type === "RESULT_RELEASED") {
    return "Open Result Holds";
  }
  return "Open";
}
