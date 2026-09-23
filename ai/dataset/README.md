# Custom UFM YOLO dataset

Place annotated exam-scene images here before training.

## Layout

```text
ai/dataset/ufm/
  data.yaml           # class list
  images/train/       # training frames
  images/val/         # validation frames
  labels/train/       # YOLO .txt labels
  labels/val/
  dataset/            # optional Roboflow exports (imported via script)
```

## Current training classes

Target vocabulary for a custom detector (see also `WATCH_PHONE_TRAINING.md`):

| ID | Class | Portal |
|----|--------|--------|
| 0 | mobile_phone | MOBILE_PHONE |
| 1 | smart_watch | SMART_WATCH |
| 2 | normal_watch | **Allowed (no alert)** |
| 3 | notes_paper | NOTES_PAPER |
| 4 | suspicious_object | SUSPICIOUS_OBJECT |

Imported Roboflow folders may use a slightly different id map in `data.yaml` —
re-align before training. COCO fallback cannot distinguish ordinary watches
from phones; use custom weights + `YOLO_USE_CUSTOM=1` after training.

## Import Roboflow export

```powershell
python ai/import_roboflow_dataset.py --source "ai/dataset/ufm/dataset/<export-folder>"
python ai/import_roboflow_dataset.py --source "ai/dataset/ufm/dataset/wrist-watch" --merge --prefix sw
```

## Train (low-RAM CPU)

```powershell
python ai/train_yolo.py --epochs 15 --batch 1 --imgsz 416 --mosaic 0 --workers 0
python ai/test_detector.py --source ai/samples/phone_under_desk.jpg
```

Weights land at `ai/runs/train/ufm_custom/weights/best.pt`. If missing, detectors fall back to COCO `yolov8n.pt`.

## YOLO label format

```text
<class_id> <x_center> <y_center> <width> <height>
```

Coordinates normalized 0–1.
