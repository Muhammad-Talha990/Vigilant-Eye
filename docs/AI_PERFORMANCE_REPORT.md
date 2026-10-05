# AI Performance Report — VigilantEye

**Status:** PRIOR CHECKPOINTS MEASURED — re-bench required after placed 15-epoch `best.pt` finalizes  
**Date:** 2026-10-04  

---

## 1. Definitions

| Term | Meaning |
|------|---------|
| MODEL INFERENCE LATENCY | Time for one `YOLO.predict` call |
| END-TO-END MONITORING LATENCY | Camera frame → detect → streak → persist → WS alert (not equal to model latency) |

Live sampling: `LIVE_DETECT_EVERY` (default 2), `LIVE_IMGSZ` (default 640).

---

## 2. Benchmark command

```powershell
python ai/benchmark_inference.py --weights ai/weights/yolov8n.pt --imgsz 640 --device cpu --runs 20
python ai/benchmark_inference.py --weights ai/runs/train/ufm_custom/weights/best.pt --imgsz 416 --device cpu --runs 20
```

Artifact: `ai/runs/bench/bench_report.json`

---

## 3. Measured results

Source: `ai/runs/bench/bench_report.json` (2026-10-03 UTC runs on this workstation).

| Weights | imgsz | Device | Mean ms | Median ms | p95 ms | Theoretical FPS |
|---------|-------|--------|---------|-----------|--------|-----------------|
| `yolov8n.pt` (COCO) | 640 | CPU | **721.1** | 685.2 | 1155.67 | **1.39** |
| `ufm_custom/best.pt` | 416 | CPU | **473.21** | 370.18 | 878.52 | **2.11** |

Hardware/software: Windows 10, Python 3.14.3, torch 2.13.0+cpu, CUDA unavailable, sample `phone_under_desk.jpg` 1280×720.

**Interpretation:** On this CPU host, neither checkpoint is “hard real-time” at full frame rate without sampling. Live pipeline mitigates via `LIVE_DETECT_EVERY` and box reuse between inference frames. GPU deployment would need separate measurement.

Live UI also exposes last `infer_latency_ms` / `infer_fps` per session when monitoring is active.

---

## 4. Deployment hardware note

| Environment | Device |
|-------------|--------|
| This workstation | CPU (CUDA unavailable in measured env) |
| Docker image | CPU PyTorch wheels; `YOLO_DEVICE=cpu` |

Do not claim “real-time” without measured latency on the target machine.
