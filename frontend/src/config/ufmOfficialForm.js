/**
 * Official Air University UFM incident form — field labels & recovered materials.
 * Align with AU UFM form terminology; do not invent extra categories.
 */

export const UFM_FORM_TITLE = "UNFAIR MEANS / UFM INCIDENT REPORT";
export const UFM_FORM_INSTITUTION = "AIR UNIVERSITY";

/** Official recovered / cheating material checklist (exact source terminology). */
export const RECOVERED_MATERIALS = [
  { code: "ANSWER_EXTRA_SHEET", label: "Answer / extra sheet" },
  { code: "MOBILE_PHONE", label: "Mobile phone" },
  { code: "CALCULATOR", label: "Calculator" },
  {
    code: "MATERIAL_ON_BODY",
    label: "Material written on body/body part",
  },
  { code: "SMART_DEVICES", label: "Smart devices" },
  { code: "OTHER", label: "Other cheating material" },
];

/** Map checklist → existing VigilantEye violation_type workflow codes. */
export const RECOVERED_TO_VIOLATION = {
  ANSWER_EXTRA_SHEET: "NOTES_PAPER",
  MOBILE_PHONE: "MOBILE_PHONE",
  CALCULATOR: "ELECTRONIC_GADGET",
  MATERIAL_ON_BODY: "SUSPICIOUS_OBJECT",
  SMART_DEVICES: "SMART_WATCH",
  OTHER: "OTHER",
};

export function mapDetectionToRecovered(detectionType) {
  const t = String(detectionType || "").toLowerCase();
  if (t.includes("phone") || t.includes("cell")) return ["MOBILE_PHONE"];
  if (t.includes("watch") || t.includes("smart")) return ["SMART_DEVICES"];
  if (t.includes("note") || t.includes("paper") || t.includes("book")) {
    return ["ANSWER_EXTRA_SHEET"];
  }
  if (t.includes("calc")) return ["CALCULATOR"];
  if (t.includes("body") || t.includes("written")) return ["MATERIAL_ON_BODY"];
  if (t.includes("remote") || t.includes("laptop") || t.includes("tablet")) {
    return ["SMART_DEVICES"];
  }
  return [];
}

export function primaryViolationFromRecovered(codes) {
  if (!Array.isArray(codes) || codes.length === 0) return "OTHER";
  for (const code of codes) {
    const mapped = RECOVERED_TO_VIOLATION[code];
    if (mapped) return mapped;
  }
  return "OTHER";
}

export function recoveredMaterialLabel(code) {
  const row = RECOVERED_MATERIALS.find((m) => m.code === code);
  return row?.label || String(code || "").replaceAll("_", " ");
}
