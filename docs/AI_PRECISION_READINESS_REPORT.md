# AI Precision / False-Positive Readiness — VigilantEye

**Date:** 2026-10-04  
**Phase:** AI-4  
**Performance numbers:** **None invented** — evaluation deferred until a trusted dataset exists.

Operational target (future): **high precision + low false-positive alerts**, with multi-frame confirmation before confirmed AI events.

---

## 1. Why precision is the binding constraint

Live monitoring must not flood Invigilators with bag/monitor/book false alarms (failure mode already observed with weak COCO labels). A high-recall / low-precision detector is operationally worse than a conservative one.

---

## 2. Available negatives (current)

| Item | Count |
|------|------:|
| Explicit empty YOLO labels on candidates | **0** |
| Pending unlabeled candidates (potential negatives) | **650** |
| Verified hard-negative set | **0** |

**Verdict:** Hard-negative coverage is **insufficient / unverified**. Gate FAIL.

---

## 3. Confusable categories (analysis only)

| Confusion | Risk | Mitigation via annotation rules |
|-----------|------|----------------------------------|
| Bag / backpack → gadget | High | Never box as `electronic_gadget` |
| Hall PC / monitor → gadget | High | Infrastructure ≠ prohibited device |
| Answer booklet → notes_paper | High | Default negative unless covert chit cues |
| Ordinary watch → smart_watch | High | Require `normal_watch` hard-negatives |
| Hands / pens / bottles | Medium | Negatives; no OD class |
| Book (COCO) → notes | High | Do not use weak COCO remap |

---

## 4. Class ambiguity

- `smart_watch` vs `normal_watch` needs deliberate dual labeling (wrist-watch auto-map **forbidden**).  
- `notes_paper` vs legitimate exam paper is policy-sensitive; CV rule: covert/unauthorized cues only.  
- `electronic_gadget` must stay narrow (personal devices), not classroom furniture.

---

## 5. Expected FP risks (qualitative)

Until CCTV-domain negatives and dual watch classes exist, expect elevated FP if training on external-only phone/paper or legacy merged labels. **No numeric FP/hour claimed.**

---

## 6. Planned evaluations (next phases — after dataset PASS)

1. **Per-class precision/recall** on held-out **test** sessions only (after freeze).  
2. **Confidence threshold sweeps** on **validation** only — never on test.  
3. **False positives per hour** on continuous normal exam footage (no planted violations).  
4. **Multi-frame confirmation** metrics: raw detections vs confirmed events (streak/cooldown).  
5. Error galleries: FP/FN by class, occlusion, distance.

---

## 7. Multi-frame confirmation requirement

Even with a good detector, single-frame hits must not become confirmed incidents. Preserve:

RAW → observation → streak → CONFIRMED AI EVENT → human review.

Confidence ≠ student guilt.

---

## 8. Readiness verdict

| Criterion | Status |
|-----------|--------|
| Trusted negatives labeled | **FAIL** |
| Hard-negative diversity documented in labels | **FAIL** |
| Per-class precision measurable on clean test | **FAIL** (no test set) |
| FP/hour protocol defined | Planned (not run) |
| Multi-frame architecture present in code | Yes (existing live path) |

**Precision readiness: NOT READY.**
