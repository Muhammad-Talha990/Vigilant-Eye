# AI-3 Annotation Readiness Report — VigilantEye

**Date:** 2026-10-04  
**Phase rule:** NO TRAINING · NO new checkpoint · weak labels remain excluded  
**Final status:** **B — ANNOTATION PIPELINE READY, DATA COLLECTION/ANNOTATION REQUIRED**

---

## 1. Current dataset status

| Source | Status |
|--------|--------|
| Placed CCTV (8156 imgs) | Usable imagery; **0 boxes** |
| Placed cheating videos (37 MOV) | Temporal + selective OD frames later; **0 boxes** |
| Weak COCO bootstrap | **Excluded** from final training |
| Rejected `best.pt` | **Disabled** |
| Training gate (`--training-ready`) | **FAIL** until real labels exist |

Forensics conclusion preserved: **C — DATASET NOT READY** for training.  
This phase makes the **annotation pipeline** ready; it does not claim training readiness.

---

## 2. Proposed taxonomy

**Unchanged** (`ufm-od-taxonomy-v1`):

**Objects:** `mobile_phone`, `smart_watch`, `normal_watch`, `notes_paper`, `electronic_gadget`  

**Temporal (not OD):** `paper_exchange`, `peer_looking`, `posture`

No taxonomy change was required; forensics evidence still supports this split.

---

## 3. Annotation rules

Documented in `docs/AI_ANNOTATION_GUIDELINES.md` (visibility thresholds, per-class include/exclude, negatives, YOLO format).

---

## 4. Annotation tool

| Tool | Role |
|------|------|
| **LabelImg** | Primary for still candidate set (YOLO txt) |
| **CVAT** | Videos, temporal intervals, review |

See `ai/annotation/README.md`.

---

## 5. Sampling strategy

| Metric | Value |
|--------|------:|
| CCTV images | 8156 |
| Unique sessions | **3000** |
| Sessions with 3 augment copies | **2578** |
| Singleton sessions | **422** |
| Annotation candidates generated | **650** (450 scan + 200 negative) |
| Rule | **One image per session_key** |

Artifact: `ai/annotation/candidates/annotation_candidates.json`

---

## 6. Negative-data strategy

Dedicated 200-session negative review bucket; empty labels allowed; no auto-boxing of bags/monitors/hall PCs; external `Non-Cheating` usable as negatives after dropping behavior boxes.

---

## 7. Video strategy

37 MOV @ 1920×1080 ~24 fps (~348 s total).  

- **OD:** selective frames (`every_n=30`, `max_frames≤6`) only after skim.  
- **Temporal:** keep full videos; schema in `ai/annotation/temporal_events.schema.json`.  
- Camera groups `v_c1`…`v_c5` recorded in candidate manifest.

---

## 8. External datasets inspected

| Dataset | Images/labels | Structurally valid? | Names OK? |
|---------|---------------|---------------------|-----------|
| offline-exam-monitoring-4 | 5676 / 5676 | Yes (8 bad rows) | Yes |
| wrist-watch | 1323 / 1323 | Yes (40 empty, 11 bad) | Yes (single class) |
| Exam cheating v1 | 3407 / 3407 | Yes (10394 boxes, 0 empty) | **CORRUPT** |

Offline-exam class box counts: Cheating 4404; Hand-Normalmove 37009; Non-Cheating 20416; cheating-paper **4795**; phone **792**.

---

## 9. License findings

Documented in `ai/dataset/LICENSE_MANIFEST.md`.

| Source | License | Final OD include |
|--------|---------|------------------|
| offline-exam-monitoring-4 | **CC BY 4.0** (yaml + README.dataset.txt) | Yes — remapped phone/paper only |
| wrist-watch | **CC BY 4.0** | No auto (need smart vs normal) |
| Exam cheating v1 | CC BY 4.0 claimed | **No** — corrupt class names |
| CCTV placed | **NOT VERIFIED** | Manual annotate after rights check |
| Hashemite MOV | **NOT VERIFIED** | Not for OD train until clarified |

---

## 10. Class mappings

Formal map in `ai/dataset_mapping.py`:

| Source | Source class | → VE | Action |
|--------|--------------|------|--------|
| offline-exam… | phone | mobile_phone | include |
| offline-exam… | cheating-paper | notes_paper | include |
| offline-exam… | Cheating / Hand-Normalmove | — | exclude |
| offline-exam… | Non-Cheating | — | negative_only |
| wrist-watch | wrist watch | — | exclude (ambiguous) |
| exam-cheating-v1 | * | — | exclude |

---

## 11. Data leakage strategy

Use `ai/session_aware_split.py`. Whole `session_key` / `video:{stem}` → one of train/val/test.  
Quality gate `--training-ready` fails if keys leak across splits.

---

## 12. Dataset structure

```text
ai/dataset/ufm/images/{train,val,test}
ai/dataset/ufm/labels/{train,val,test}
ai/dataset/ufm/data_ufm_od_v0.1.yaml
ai/dataset/LICENSE_MANIFEST.md
ai/annotation/…
```

---

## 13. QA process

Annotator → `dataset_quality_gate.py` → visual review → correction → version bump.  
Inter-annotator agreement: **not measured** (no second pass yet).

---

## 14. Dataset version

| Field | Value |
|-------|--------|
| Taxonomy | `ufm-od-taxonomy-v1` |
| Target dataset | `ufm-od-v0.1` |
| Candidate list | `ufm-od-v0.1-candidates` |
| License manifest | `license-manifest-v1` |
| Annotation revision | **not started** |

---

## 15. Training gate

```powershell
python ai/dataset_quality_gate.py --prepared ai/dataset/ufm --training-ready
```

Returns clear `GATE: PASS|FAIL`. Currently **FAIL** (expected): no trustworthy final labels yet.

Checks include: labels present, valid geometry/IDs, expected taxonomy names, train/val/test non-empty, session leakage, license manifest, weak-label quarantine, `dataset_mapping` import.

---

## 16. Annotation work remaining

1. Confirm CCTV / Hashemite usage rights for FYP.  
2. Label 650 CCTV candidates (LabelImg).  
3. Remap + QA offline-exam `phone` / `cheating-paper`.  
4. Optional manual smart vs normal watches.  
5. Video skim + selective OD frames + temporal CSV.  
6. Session-aware split + gate PASS.  
7. **Only then** train (next phase).

---

## 17. Exact next step

Start LabelImg on `ai/annotation/candidates/annotation_candidates.txt` using `ai/annotation/classes.txt` and `docs/AI_ANNOTATION_GUIDELINES.md`.  
In parallel, build a staging remap of offline-exam phone/paper into `ai/annotation/prelabels/` (no merge into train until QA).

**Do not run YOLO training.**

---

## Files created/updated

- `docs/AI_ANNOTATION_GUIDELINES.md`
- `docs/AI_ANNOTATION_PLAN.md`
- `docs/AI_ANNOTATION_READINESS_REPORT.md`
- `ai/dataset/LICENSE_MANIFEST.md`
- `ai/dataset/README.md`
- `ai/dataset/ufm/data_ufm_od_v0.1.yaml`
- `ai/dataset_mapping.py`
- `ai/dataset_quality_gate.py` (training-ready gate)
- `ai/annotation/**`

## Checks executed

- Roboflow label structural scans (offline / wrist / exam-cheating)  
- CCTV session grouping (3000 keys)  
- Candidate generation (650)  
- `--training-ready` gate → FAIL (expected)

## Final status

**B — ANNOTATION PIPELINE READY, DATA COLLECTION/ANNOTATION REQUIRED**
