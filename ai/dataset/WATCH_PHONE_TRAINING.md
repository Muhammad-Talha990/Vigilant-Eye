# Custom UFM detector training notes (watch vs phone)

## Why COCO alone is not enough

`yolov8n.pt` (COCO) includes **cell phone** but has **no** `smartwatch`,
`normal_watch`, or `electronic_gadget` classes. Ordinary analog watches are
often misclassified as `cell phone` or `remote`. Mapping those errors into
UFM alerts caused false positives.

Runtime mitigations (higher confirm thresholds, temporal confirmation,
excluding `remote`, not mapping generic `watch` → smart_watch) reduce but
**do not eliminate** this confusion.

## Required custom classes

Train a custom detector with at least:

| Class | Meaning | Portal |
|-------|---------|--------|
| `mobile_phone` | Phones (any orientation) | MOBILE_PHONE |
| `smart_watch` | Digital / smart wearables | SMART_WATCH |
| `normal_watch` | Ordinary analog / non-smart watches | **Allowed — no alert** |
| `notes_paper` | Cheat sheets / notes | NOTES_PAPER |
| `suspicious_object` | Other prohibited items | SUSPICIOUS_OBJECT |

Include varied ordinary watches (worn + held), phones, smartwatches,
classroom backgrounds, angles, distances, lighting, and partial occlusions.
Split train/val/test **by recording session** to avoid adjacent-frame leakage.

## Enable custom weights

```powershell
# After a successful train_yolo.py run:
$env:YOLO_USE_CUSTOM="1"
uvicorn main:app --reload
```

Without `YOLO_USE_CUSTOM=1`, live monitoring uses COCO by default.

## Threshold overrides (optional)

```text
UFM_CONF_MOBILE_PHONE_CONFIRM=0.72
UFM_CONF_MOBILE_PHONE_REVIEW=0.45
UFM_CONFIRM_FRAMES=6
UFM_REVIEW_FRAMES=4
UFM_PERSIST_COOLDOWN_SEC=90
```

These are mitigations — retune on your own exam footage.
