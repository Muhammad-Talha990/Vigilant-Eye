# Dataset register (research — downloads not claimed unless performed)

| Source | URL | License | Classes / use | Status | Limitations |
|--------|-----|---------|---------------|--------|-------------|
| COCO 2017 (via Ultralytics) | https://cocodataset.org | CC / see COCO | cell phone, book, laptop (proxies) | **Used as runtime baseline** (`yolov8n.pt`) | No smartwatch/normal_watch/chit; book≠cheat sheet |
| Roboflow Universe (phone/exam search) | https://universe.roboflow.com | Per-dataset | Varies | Import script: `ai/import_roboflow_dataset.py` | Must verify license per project; not auto-downloaded here |
| Controlled AU lab recordings | Local | Institutional | Phones, watches, paper | **Plan** — collect under consent | Privacy; not in repo |
| Hard negatives (watches, blank pages, pens) | Local capture | Own | normal_watch, sheets | See `ai/dataset/WATCH_PHONE_TRAINING.md` | Manual labeling required |

## Collection plan (when public data insufficient)
1. Record 3+ hall cameras (wide + aisle) with consent forms.
2. Annotate YOLO boxes: mobile_phone, smart_watch, normal_watch, notes_paper (slip vs sheet), electronic_gadget.
3. Temporal labels for paper_exchange and sustained head_turn episodes (separate CSV).
4. Split by recording session (no adjacent-frame leakage).
5. Train `ai/train_yolo.py` → `ai/runs/train/ufm_custom/weights/best.pt`.

**This session:** no new paid/public bulk dataset download was completed (network/license diligence). Runtime continues on COCO + policy mitigations.
