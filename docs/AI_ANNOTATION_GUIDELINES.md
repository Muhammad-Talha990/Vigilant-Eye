# VigilantEye Object-Detection Annotation Guidelines

**Taxonomy version:** `ufm-od-taxonomy-v1`  
**Scope:** Computer-vision labeling rules only (not university disciplinary policy)  
**Applies to:** Manual annotation of examination-hall imagery for YOLO object detection  

Temporal behaviors (`paper_exchange`, `peer_looking`, `posture`) are **out of scope** for these box guidelines.

---

## 1. Class list (objects only)

| ID | Class | Short definition |
|----|-------|------------------|
| 0 | `mobile_phone` | Mobile handset / smartphone |
| 1 | `smart_watch` | Wrist-worn smart device (screen/digital interface cues) |
| 2 | `normal_watch` | Ordinary analog/digital wristwatch (allowed hard-negative) |
| 3 | `notes_paper` | Unauthorized notes / chits / crib sheets (not the official answer booklet by default) |
| 4 | `electronic_gadget` | Other prohibited electronics (tablet, laptop, earpiece, powerbank used covertly, etc.) |

Do **not** invent additional OD classes without updating this document and the taxonomy version.

---

## 2. Global box rules

1. Draw a **tight** axis-aligned box around the visible object instance.  
2. One instance → one box. Multiple phones → multiple boxes.  
3. Prefer the object, not the whole desk or student.  
4. If unsure between two classes, use the **more specific** class; if still unsure, **skip** and mark the image for review (do not guess).  
5. Empty label files are valid for **true negatives** (no target objects).  
6. Never label bags, monitors, chairs, bottles, or answer booklets as `electronic_gadget` / `suspicious_*`.

### Visibility thresholds

| Situation | Rule |
|-----------|------|
| Fully visible | Annotate |
| Partially occluded (≥ ~30% visible, class clear) | Annotate visible portion |
| Heavily occluded (< ~30% or class unclear) | **Do not** annotate |
| Behind hands (shape still clearly a phone/watch) | Annotate if identity clear |
| Under desk (mostly hidden) | Annotate only if clearly identifiable |
| At image edge (clip ≥ ~40% of object missing) | Annotate if class still clear; else skip |
| Tiny object (< ~12 px on shortest side after resize) | Skip unless unmistakably the class |
| Severely blurred | Skip if class cannot be confirmed |
| Ambiguous object | Skip + flag for review |
| Overlapping objects | Separate boxes; do not merge into one |

---

## 3. Per-class rules

### 3.1 `mobile_phone`

**Box:** The handset body (screen + chassis). Include case if attached.  
**Do box:** phones in hand, on lap, on desk, partially under paper if phone still clear.  
**Do not box:** calculators (unless clearly a phone), phone-shaped stickers, phone icons on monitors, empty phone cases with no device.

### 3.2 `smart_watch`

**Box:** Watch head + visible band segment needed for identity.  
**Requires:** cues of a smart device (rectangular/digital face, app UI, distinct smartwatch form).  
**Do not box:** ordinary analog watches as smart; fitness bands only if clearly smart-device class agreed in review.

### 3.3 `normal_watch`

**Box:** Ordinary wristwatch.  
**Purpose:** hard-negative so the model does not treat every wrist object as prohibited.  
**Do not** map all “wrist watch” external labels here without visual confirmation of ordinary vs smart.

### 3.4 `notes_paper`

**Box:** Unauthorized note / chit / crib sheet distinct from the official exam booklet when possible.  
**Do box:** small folded notes, hidden papers with writing used covertly.  
**Do not box by default:** large official answer booklets, question papers issued by invigilators, blank A4 sheets with no covert-note cues.  
If only “paper on desk” is visible with no covert cue → **negative** (no box).

### 3.5 `electronic_gadget`

**Box:** Non-phone / non-watch electronics that are clearly devices (tablet, laptop lid/keyboard, earpiece, etc.).  
**Do not box:** classroom PCs/monitors that are hall infrastructure, bags, bottles, pens, power outlets, keyboards that are fixed lab equipment unless the scenario is clearly a personal prohibited device.

---

## 4. Negatives (critical)

Preserve images that contain students, desks, legitimate papers, books, hands, bags, monitors, and other harmless objects **without** adding positive boxes.

These prevent the failure mode seen with weak COCO labels (bags/monitors → false “suspicious” gadgets).

Target: a substantial fraction of the annotation set should be **true negatives** or contain only `normal_watch`.

---

## 5. Multi-object & difficult cases

- Annotate all clear instances of the five classes in the frame.  
- Prefer quality over quantity: one correct box beats five guessed boxes.  
- For dense halls, prioritize closer / clearer objects; do not invent tiny distant phones.

---

## 6. Consistency between annotators

Two annotators should be able to apply these rules without legal interpretation:

1. Is it one of the five object classes?  
2. Is ≥ ~30% visible and class clear?  
3. Is the box tight?

If any answer is no → skip or negative.

---

## 7. File format

YOLO txt, one file per image, same stem:

```text
<class_id> <x_center> <y_center> <width> <height>
```

Normalized coordinates in `[0, 1]`. UTF-8, one box per line.
