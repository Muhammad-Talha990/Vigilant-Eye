# VigilantEye AI-3 Annotation Plan

**Status:** Annotation pipeline designed — human labeling required next  
**Taxonomy:** `ufm-od-taxonomy-v1` (unchanged from forensics)  
**Dataset version target:** `ufm-od-v0.1`  
**No training in this phase.**

---

## 1. Goals

1. Produce trustworthy OD boxes for `mobile_phone`, `smart_watch`, `normal_watch`, `notes_paper`, `electronic_gadget`.  
2. Preserve negatives (no weak COCO bags/monitors).  
3. Integrate only license-cleared external boxes with formal remap.  
4. Keep temporal behaviors on a separate track.

---

## 2. Annotation tool (selected)

| Option | Verdict |
|--------|---------|
| **LabelImg** | **Primary for stills** — simple, YOLO txt export, low overhead |
| **CVAT** | **Primary for videos / review** — timeline, attributes, team review |
| Roboflow Annotate | Optional if already used; export YOLO + keep license notes |

**Workflow:**

1. Import candidate list from `ai/annotation/candidates/annotation_candidates.txt`.  
2. Label with LabelImg (YOLO format) using classes from `ai/annotation/classes.txt`.  
3. Run `dataset_quality_gate.py` automated checks.  
4. Visual QA sample in CVAT or overlay script.  
5. Correct → bump annotation revision → session-aware split.

---

## 3. Sampling strategy (CCTV)

From forensics + candidate generation:

| Fact | Value |
|------|------:|
| Total CCTV images | 8156 |
| Unique `session_key` | **3000** |
| Keys with 3 augment copies | **2578** |
| Singleton keys | **422** |

**Rule:** Annotate **at most one image per `session_key`** (never all three `.rf.` augment copies).

**Generated candidate set** (`ai/annotation/candidates/`):

| Bucket | Sessions / images |
|--------|------------------:|
| `annotate_scan` | 450 |
| `negative_review` | 200 |
| **Total candidates** | **650** |

Selection: seeded shuffle (`seed=42`) over session keys; one mid-sorted file per key.

Coverage intent: diverse sessions (not first-N), mix of multiplicities, dedicated negative pass.

Expand later only if class counts remain insufficient after first pass.

---

## 4. Negative-data strategy

1. 200 sessions reserved for **negative_review** first (expect many true negatives).  
2. During `annotate_scan`, leave empty `.txt` when no target object is present.  
3. Never auto-label bags/monitors/PCs.  
4. External `Non-Cheating` images may be used as negatives **only** after dropping behavior boxes.

---

## 5. Video strategy (37 MOV)

| Camera group | Count (from stems) |
|--------------|-------------------:|
| v_c1 … v_c5 | present across 37 files |

**OD:** Do **not** dump all ~8345 frames. For each video, extract at most `every_n=30`, `max_frames=6` **after** visual skim confirms phone/notes visibility. Keep `video:{stem}` as session key.

**Temporal:** Keep full MOV files. Annotate events later with:

| Field | Meaning |
|-------|---------|
| video_id | filename stem |
| camera_group | `v_cN` |
| event_category | `paper_exchange` / `peer_looking` / `cell_use` / `cheat_sheet` / `non_cheating` |
| t_start / t_end | seconds |
| notes | free text |
| annotator | id |

No temporal labels invented without watching the clip.

---

## 6. External data integration (license-cleared)

See `ai/dataset/LICENSE_MANIFEST.md` + `ai/dataset_mapping.py`.

| Source | Action |
|--------|--------|
| offline-exam-monitoring-4 | Include remapped `phone`, `cheating-paper` |
| wrist-watch | Exclude auto-map; optional manual re-label |
| Exam cheating v1 | **Exclude** (corrupt names) |
| Hashemite videos | Not in OD train until license cleared |
| Weak COCO labels | **Exclude** |

Measured offline-exam box counts (structurally valid):

| source_id | name | boxes |
|----------:|------|------:|
| 0 | Cheating | 4404 (exclude) |
| 1 | Hand-Normalmove | 37009 (exclude) |
| 2 | Non-Cheating | 20416 (negative-only) |
| 3 | cheating-paper | 4795 (**→ notes_paper**) |
| 4 | phone | 792 (**→ mobile_phone**) |

---

## 7. Final dataset structure

```text
ai/dataset/ufm/
  data.yaml                 # ufm-od-v0.1 names
  README.md
  LICENSE_MANIFEST.md       # (also mirrored under ai/dataset/)
  images/{train,val,test}/
  labels/{train,val,test}/
  dataset/                  # raw exports (not copied to Docker)
  experimental/             # weak labels quarantined (optional)
```

Build steps (future, still no train until gate PASS):

1. Manual labels for 650 CCTV candidates (+ expand).  
2. Remap offline-exam phone/paper into staging.  
3. `session_aware_split.py --apply`.  
4. `dataset_quality_gate.py --training-ready`.

---

## 8. QA process

```text
ANNOTATOR → AUTOMATED VALIDATION → VISUAL REVIEW → CORRECTION → DATASET VERSION
```

Automated: missing/orphan labels, bad IDs, geometry, empty ratio, corrupt class names, license manifest present, session leakage check.

Visual: wrong class, missing object, fat/skinny boxes, ambiguous cases.

Inter-annotator: if a second annotator is available, double-label ≥10% of candidates; **do not claim IAA until measured**.

---

## 9. Work remaining (human)

1. Confirm CCTV imagery license for FYP use/redistribution.  
2. Label 650 candidates per guidelines.  
3. Skim 37 videos; extract selective OD frames; draft temporal event CSV.  
4. Remap + QA offline-exam phone/paper.  
5. Manual watch smart vs normal (optional wrist-watch subset).  
6. Pass `--training-ready` gate before any `train_yolo.py`.
