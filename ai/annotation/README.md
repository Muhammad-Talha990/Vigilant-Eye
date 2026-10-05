# Annotation workspace (AI-3)

**No training from this folder.**

## Contents

| Path | Purpose |
|------|---------|
| `classes.txt` | LabelImg / YOLO class order (`ufm-od-taxonomy-v1`) |
| `candidates/annotation_candidates.json` | Session-aware CCTV sample (650) + video plans |
| `candidates/annotation_candidates.txt` | Absolute paths for import |
| `temporal_events.schema.json` | Schema for future temporal labels |
| `prelabels/` | Optional staging for remapped external labels (empty by default) |

## Tooling

1. **LabelImg** — open `classes.txt`, YOLO format, label candidate stills.  
2. **CVAT** — video review / temporal intervals / second-pass QA.  

Guidelines: `docs/AI_ANNOTATION_GUIDELINES.md`  
Plan: `docs/AI_ANNOTATION_PLAN.md`

## After labeling

```powershell
python ai/dataset_quality_gate.py --prepared ai/dataset/ufm --training-ready --require-license-manifest
```

Do not run `train_yolo.py` until the gate prints PASS.
