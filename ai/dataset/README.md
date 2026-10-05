# VigilantEye datasets

**Authoritative gate:** `docs/AI_ANNOTATION_READINESS_REPORT.md`  
**License manifest:** `ai/dataset/LICENSE_MANIFEST.md`  
**Taxonomy:** `ufm-od-taxonomy-v1`  
**Target version:** `ufm-od-v0.1` (not ready until annotation + gate PASS)

## Layout

```text
ai/dataset/
  LICENSE_MANIFEST.md
  README.md
  ufm/
    data.yaml              # active YOLO config (must match taxonomy when training)
    images/{train,val,test}/
    labels/{train,val,test}/
    dataset/               # raw Roboflow / placed exports (gitignored media)
    experimental/          # quarantined weak labels (do not train)
```

Placed CCTV + cheating videos currently live primarily under the FYP tree:

`C:\Users\KING\Desktop\FYP\Vigilant Eye\ai\dataset\ufm\dataset`

## Rules

1. Do not train on weak COCO bootstrap labels.  
2. Do not enable rejected `best.pt`.  
3. Session-aware splits only (`ai/session_aware_split.py`).  
4. External data only if listed as included in `LICENSE_MANIFEST.md`.  
5. Temporal behaviors are not YOLO classes.

## Mapping

See `ai/dataset_mapping.py`.
