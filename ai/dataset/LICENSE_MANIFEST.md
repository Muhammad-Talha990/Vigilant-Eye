# VigilantEye Dataset License Manifest

**Manifest version:** `license-manifest-v1`  
**Dataset version target:** `ufm-od-v0.1`  
**Rule:** Do not include a source in final training unless license status is verified below.

CC BY 4.0 obligations (when declared by source): attribution required; redistribution of adapted material must keep license notice. Confirm current Roboflow Universe page before public redistribution of derivatives.

---

## 1. Placed local collections (FYP tree)

### 1.1 CCTV-Exam -Monitor -Dataset

| Field | Value |
|-------|--------|
| Path | `FYP/.../ai/dataset/ufm/dataset/CCTV-Exam -Monitor -Dataset` |
| Type | Images only (8,156 JPEG), no boxes |
| Source URL | **NOT VERIFIED** in-repo (Roboflow-style filenames; no `data.yaml`) |
| License | **NOT VERIFIED** |
| Included in training (`ufm-od-v0.1`) | **No (not yet)** — pending manual annotation + license clarification |
| Reason | Domain-relevant imagery for **manual labeling**; cannot claim cleared redistribution rights from local folder alone |

### 1.2 Dataset_cheating (Hashemite University sequences)

| Field | Value |
|-------|--------|
| Path | `FYP/.../ai/dataset/ufm/dataset/Dataset_cheating` |
| Type | 37 MOV videos + README |
| Source | README: Hashemite University Faculty of IT classroom capture |
| License | **NOT VERIFIED** (README states research/academic objective; no SPDX / Creative Commons text) |
| Included in training | **No** for OD boxes until rights clarified; usable for **internal temporal research** only after confirmation |
| Attribution | Cite source paper/authors when identified |
| Modification / redistribution | **NOT VERIFIED** |

---

## 2. Secondary Roboflow exports (NEW PROJ `ai/dataset/ufm/dataset/`)

### 2.1 offline-exam-monitoring-4 (v6)

| Field | Value |
|-------|--------|
| Local path | `ai/dataset/ufm/dataset/offline-exam-monitoring-4` |
| URL | https://universe.roboflow.com/cp2-sgbvv/offline-exam-monitoring-4/dataset/6 |
| License declaration | **CC BY 4.0** (`data.yaml` `roboflow.license` + `README.dataset.txt`) |
| Classes | Cheating, Hand-Normalmove, Non-Cheating, cheating-paper, phone |
| Permitted use (per CC BY 4.0) | Use/adapt with attribution |
| Included in training | **Conditionally yes** — only remapped `phone` → `mobile_phone` and `cheating-paper` → `notes_paper` after structural QA |
| Excluded classes | Cheating, Hand-Normalmove (behavior); Non-Cheating as negative-only |

### 2.2 wrist-watch (v4)

| Field | Value |
|-------|--------|
| Local path | `ai/dataset/ufm/dataset/wrist-watch` |
| URL | https://universe.roboflow.com/wristwatchv2/wrist-watch-lky3p/dataset/4 |
| License declaration | **CC BY 4.0** |
| Classes | `wrist watch` (single) |
| Included in training | **No (auto)** — cannot map to `smart_watch` vs `normal_watch` without manual re-label |
| Optional | Manual subset re-annotation under CC BY 4.0 attribution |

### 2.3 Exam cheating v1

| Field | Value |
|-------|--------|
| Local path | `ai/dataset/ufm/dataset/Exam cheating.v1i.yolov5pytorch` |
| URL | https://universe.roboflow.com/cheating-detection-bp8bo/exam-cheating-9iz1y-gmrua/dataset/1 |
| License declaration | **CC BY 4.0** in README/`data.yaml` |
| Class names in local yaml | **CORRUPT** (README text leaked into `names`) |
| Label files | Structurally valid YOLO (IDs 0–7, 10,394 boxes, 0 empty, 0 bad geometry in scan) |
| Included in training | **No** — class identity cannot be proven; do not guess names |

---

## 3. Experimental / excluded artifacts

| Artifact | License | Training include? | Reason |
|----------|---------|-------------------|--------|
| COCO weak labels (`prepare_placed_dataset.py`) | COCO terms apply to pretrained detector use; labels are derived | **No** | High FP; forensic status unsuitable |
| Rejected `best.pt` | N/A | **No** | Failed eval; not a dataset |

---

## 4. Attribution snippet (for included Roboflow CC BY sets)

When publishing or submitting the FYP, include attribution similar to:

> Offline Exam Monitoring 4 dataset by Roboflow user `cp2-sgbvv`, CC BY 4.0,  
> https://universe.roboflow.com/cp2-sgbvv/offline-exam-monitoring-4/dataset/6

Update if additional CC BY sources are added after verification.
