/** Allowed review buttons by role + current case status (mirrors backend workflow). */

import { availableReviewActions as fromWorkflow } from "./workflowPresentation";

export function availableReviewActions(role, status) {
  return fromWorkflow(role, status);
}
