# AI Overfitting Risk Assessment — VigilantEye

**Date:** 2026-10-04  
**Phase:** AI-4 Dataset Construction Gate  
**Training executed:** **No**  
**Dataset construction status:** **FAIL** (0/650 manual candidate labels)

---

## 1. Executive assessment

| Risk factor | Current state | Severity |
|-------------|---------------|----------|
| Dataset size (trusted OD labels) | **0** annotated candidates | Critical |
| Independent CCTV sessions available | 650 candidates from 3000 sessions | Potential OK after labeling |
| Independent environments | CCTV halls + external Roboflow domains | Mixed / shift risk |
| Near-duplicate risk | Candidate set: 0 exact dup groups; source CCTV has 2578×3 augments | High if augments labeled blindly |
| Train/val/test separation | Final splits **not constructed** | Critical |
| Prepared-root leakage | train∩val = **95** session keys | Critical (legacy merge) |
| Empty test set | prepared `images/test` = **0** | Critical |
| External-domain shift | phone/paper mostly external if merged early | High |
| Hard-negative coverage | **Unverified** (no negatives labeled) | Critical |
| Augmentation risk | Must not precede diversity proof | Medium |

**Conclusion:** Overfitting is **not** “solved” by tooling alone. With zero manual labels, any training would overfit noise or the wrong taxonomy (legacy merge). Session-aware splits reduce leakage **only after** trustworthy labels exist.

---

## 2. Dataset size & sessions

| Quantity | Value |
|----------|------:|
| Annotation candidates | 650 |
| Manually annotated | **0** |
| Candidate sessions | 650 (1 image/session) |
| Broader CCTV sessions (forensics) | 3000 |
| Meaningful OD objects (approved taxonomy) | **0** |

---

## 3. Source / environment diversity

| Source | Role | Overfitting note |
|--------|------|------------------|
| CCTV placed stills | Primary target domain | Must dominate evaluation |
| offline-exam-monitoring-4 (CC BY) | Phone/paper supplement only | Domain shift vs CCTV |
| wrist-watch | Excluded auto-map | Close-ups ≠ hall scale |
| Exam cheating v1 | Excluded | Corrupt classes |
| Legacy merged `ai/dataset/ufm` | Contaminated taxonomy + leakage | **Do not train as-is** |

---

## 4. Near-duplicate risk

- Candidate generation already enforces one image per `session_key` → good.  
- Original CCTV export contains triple `.rf.` augments — **never label all three**.  
- Adjacent video frames must stay in one split via `video:{stem}`.

---

## 5. Split integrity

Requirements:

```text
train_sessions ∩ val_sessions = ∅
train_sessions ∩ test_sessions = ∅
val_sessions ∩ test_sessions = ∅
```

**Final dataset:** not built.  
**Prepared root:** fails leakage + empty test + wrong class names.

Test set must not be used for threshold/model selection once created.

---

## 6. Augmentation policy (pre-training)

Allowed only **after** gate PASS, on train split only:

- mild color/brightness, small rotation, mosaic with care  
Forbidden for now:

- fabricating thousands of variants to “balance” classes  
- distorting watch identity  
- applying augments that cross into val/test  

Original provenance must remain recoverable.

---

## 7. What remains uncertain

1. How many of the 650 candidates actually contain visible phones/watches/notes.  
2. Whether CCTV license allows FYP redistribution of derived labels.  
3. Whether external phone/paper boxes survive visual QA at CCTV operating point.  
4. Real FP rate on continuous exam video (needs later FP/hour study — not invented here).

---

## 8. Gate implication

Until manual annotation + session-aware train/val/**test** + hard negatives exist:

**Do not train.** Overfitting risk is unacceptable.
