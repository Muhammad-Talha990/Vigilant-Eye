# AI-4 Dataset Construction Gate Report — VigilantEye

**Date:** 2026-10-04  
**Gate artifact:** `ai/runs/dataset_gate/dataset_gate.json`  
**Training executed:** **No**  
**COCO baseline / custom best.pt:** **Untouched**

## FINAL STATUS: **B — ANNOTATION/DATA COLLECTION STILL REQUIRED**

Construction gate: **FAIL**  
Also recorded: **BLOCKED — MORE DATA REQUIRED** for meaningful session-aware TEST set (0 labels).

---

## 1. Annotation completion

| Metric | Value |
|--------|------:|
| Candidate images | **650** |
| Images existing on disk | **650** |
| Manually annotated (YOLO txt found) | **0** |
| Missing annotations | **650** |
| Empty/negative labels | **0** |
| Malformed / invalid IDs | N/A (no files) |
| Objects per class | all **0** |

Visual QA: `ai/runs/annotation_qa/pending_unlabeled/` (12 samples marked NO LABEL).  
Positive/hard/per-class galleries empty (no labels to render).

---

## 2. Train / val / test

| Split | Final constructed count |
|-------|-------------------------|
| train | **not constructed** |
| val | **not constructed** |
| test | **not constructed** |

Legacy prepared root (inspection only — **not approved**):

| Split | Images | Issue |
|-------|-------:|-------|
| train | 5957 | Wrong taxonomy; leakage |
| val | 632 | Leakage vs train (95 keys) |
| test | **0** | Empty |

---

## 3. Session leakage

| Check | Result |
|-------|--------|
| Final dataset intersections | **NOT RUN** (no final splits) |
| Prepared train∩val | **95 sessions** → FAIL |
| Requirement | each session → exactly one split |

---

## 4. Duplicates

Candidate set: **0** exact MD5 duplicate groups; **650** distinct sessions.  
Source CCTV still has augment triplets — do not annotate all copies.

---

## 5. Class balance

All approved classes: **0** objects. Underrepresentation is total.  
No forced oversampling performed.

---

## 6. Hard negatives

**FAIL** — no empty labels; confusable categories listed in precision report; insufficient verified negatives.

---

## 7. External / license

| Source | Decision |
|--------|----------|
| offline-exam phone/paper (CC BY 4.0) | Allowed **after** remap+QA — **not merged** (gate FAIL) |
| wrist-watch | Auto-map excluded |
| Exam cheating v1 | Excluded (corrupt names) |
| Hashemite MOV | License NOT VERIFIED — excluded from OD train |

---

## 8. Annotation QA result

**FAIL** — incomplete. No silent repairs. Machine-readable: `annotation_completion.json`.

---

## 9. Overfitting / precision

See:

- `docs/AI_OVERFITTING_RISK_ASSESSMENT.md`
- `docs/AI_PRECISION_READINESS_REPORT.md`

---

## 10. Exact blockers

1. 0/650 manual annotations.  
2. Cannot build defensible session-aware TEST set.  
3. Hard negatives unverified.  
4. Legacy prepared root: empty test, taxonomy mismatch, leakage.  
5. External data not promoted (correctly blocked until manual CCTV labels exist).

---

## 11. Exact next action

1. Open LabelImg with `ai/annotation/classes.txt`.  
2. Label paths in `ai/annotation/candidates/annotation_candidates.txt`.  
3. Save YOLO `.txt` beside each image **or** under `ai/annotation/labels/`.  
4. Ensure many **empty** negatives.  
5. Prioritize: `mobile_phone`, `notes_paper`, watches (`smart` vs `normal`), true negatives.  
6. Re-run:

```powershell
python ai/dataset_construction_gate.py
```

7. Only if `gate_pass=true` → authorize **AI-5 training phase** (not before).

---

## Commands / artifacts

```powershell
python ai/annotation_qa.py --fail-on-incomplete
python ai/dataset_construction_gate.py
```

| Path | Content |
|------|---------|
| `ai/runs/dataset_gate/dataset_gate.json` | PASS/FAIL |
| `ai/runs/dataset_gate/dataset_statistics.json` | Counts |
| `ai/runs/dataset_gate/leakage_report.json` | Leakage |
| `ai/runs/dataset_gate/duplicate_report.json` | Dupes |
| `ai/runs/dataset_gate/class_balance.json` | Per-class |
| `ai/runs/dataset_gate/provenance_report.json` | Provenance |
| `ai/runs/dataset_gate/hard_negative_report.json` | Negatives |
| `ai/runs/annotation_qa/` | Visual QA dirs |
