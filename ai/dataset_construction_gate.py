"""
AI-4 Dataset Construction Gate — strict PASS/FAIL (NO TRAINING).

Orchestrates annotation QA, license checks, leakage checks, and refuses to
promote a final train/val/test dataset when critical conditions fail.

Usage:
  python ai/dataset_construction_gate.py
  python ai/dataset_construction_gate.py --construct-if-pass   # will no-op if FAIL
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent
GATE_DIR = AI_ROOT / "runs" / "dataset_gate"
TAXONOMY = [
    "mobile_phone",
    "smart_watch",
    "normal_watch",
    "notes_paper",
    "electronic_gadget",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Strict dataset construction gate")
    p.add_argument(
        "--candidates",
        type=str,
        default=str(AI_ROOT / "annotation" / "candidates" / "annotation_candidates.json"),
    )
    p.add_argument(
        "--prepared",
        type=str,
        default=str(AI_ROOT / "dataset" / "ufm"),
        help="Existing prepared YOLO root (for leakage/taxonomy inspection only)",
    )
    p.add_argument("--out", type=str, default=str(GATE_DIR))
    p.add_argument(
        "--construct-if-pass",
        action="store_true",
        help="Only construct canonical final/ if gate PASSes (will not invent labels)",
    )
    return p.parse_args()


def run_annotation_qa(candidates: str, out: Path) -> dict:
    cmd = [
        sys.executable,
        str(AI_ROOT / "annotation_qa.py"),
        "--candidates",
        candidates,
        "--out",
        str(out),
        "--fail-on-incomplete",
    ]
    subprocess.run(cmd, check=False)
    path = out / "annotation_completion.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"status": "FAIL", "critical": ["annotation_qa did not produce report"]}


def run_training_ready(prepared: str, out: Path) -> dict:
    cmd = [
        sys.executable,
        str(AI_ROOT / "dataset_quality_gate.py"),
        "--prepared",
        prepared,
        "--training-ready",
        "--out",
        str(out / "training_ready_gate.json"),
    ]
    subprocess.run(cmd, check=False)
    path = out / "training_ready_gate.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"gate_pass": False, "critical": ["training_ready gate missing output"]}


def license_check() -> dict:
    man = AI_ROOT / "dataset" / "LICENSE_MANIFEST.md"
    mapping = AI_ROOT / "dataset_mapping.py"
    critical = []
    warnings = []
    if not man.is_file():
        critical.append("LICENSE_MANIFEST.md missing")
        text = ""
    else:
        text = man.read_text(encoding="utf-8", errors="replace")
    allowed_includes = []
    excluded = []
    if "offline-exam-monitoring-4" in text and "CC BY 4.0" in text:
        allowed_includes.append(
            {
                "dataset": "offline-exam-monitoring-4",
                "license": "CC BY 4.0",
                "include_classes": ["phone->mobile_phone", "cheating-paper->notes_paper"],
            }
        )
    else:
        critical.append("offline-exam-monitoring-4 license not confirmed in manifest")
    if "Exam cheating" in text or "exam-cheating" in text.lower():
        excluded.append(
            {
                "dataset": "Exam cheating v1",
                "reason": "corrupt/unprovable class names — excluded",
            }
        )
    if "wrist-watch" in text:
        excluded.append(
            {
                "dataset": "wrist-watch",
                "reason": "no smart vs normal distinction — auto-map excluded",
            }
        )
    if "NOT VERIFIED" in text and "Hashemite" in text:
        excluded.append(
            {
                "dataset": "Dataset_cheating / Hashemite MOV",
                "reason": "license NOT VERIFIED",
            }
        )
    if not mapping.is_file():
        critical.append("dataset_mapping.py missing")
    return {
        "critical": critical,
        "warnings": warnings,
        "allowed_includes": allowed_includes,
        "excluded": excluded,
        "manifest": str(man) if man.is_file() else None,
    }


def provenance_stub(ann: dict) -> dict:
    return {
        "manual_cctv_candidates": {
            "planned": (ann.get("completion") or {}).get("total_candidates"),
            "annotated": (ann.get("completion") or {}).get("manually_annotated_files"),
            "source": "FYP CCTV-Exam -Monitor -Dataset via annotation_candidates.json",
        },
        "external_included_in_final": [],
        "note": (
            "No final dataset constructed while annotation incomplete. "
            "External remaps must not be promoted without gate PASS."
        ),
    }


def hard_negative_assessment(ann: dict) -> dict:
    comp = ann.get("completion") or {}
    empty = comp.get("empty_negative_labels") or 0
    missing = comp.get("missing_annotations") or 0
    total = comp.get("total_candidates") or 0
    critical = []
    warnings = []
    if total and missing == total:
        critical.append(
            "No annotated negatives yet — hard-negative coverage cannot be verified"
        )
    elif empty < max(20, int(0.1 * max(1, (comp.get("manually_annotated_files") or 0)))):
        warnings.append(
            "Few explicit empty/negative label files relative to annotated set"
        )
    return {
        "critical": critical,
        "warnings": warnings,
        "empty_negative_labels": empty,
        "pending_unlabeled_candidates": missing,
        "confusable_categories_to_cover": [
            "bags / backpacks (not electronic_gadget)",
            "classroom monitors / PCs (not electronic_gadget)",
            "official answer booklets (not notes_paper by default)",
            "ordinary watches (normal_watch vs smart_watch)",
            "hands / pens / bottles",
        ],
        "sufficient_hard_negatives": False if missing == total else empty >= 20,
    }


def source_domination(ann: dict) -> dict:
    # Until annotations exist, report unknown / blocked
    comp = ann.get("completion") or {}
    annotated = comp.get("manually_annotated_files") or 0
    return {
        "annotated_images": annotated,
        "per_class_source_mix": {},
        "warning": (
            "Cannot compute source domination until manual labels exist. "
            "Risk: external phone/paper domain may dominate CCTV if merged early."
        ),
        "fail_if_single_source_class": True,
    }


def main() -> int:
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ann = run_annotation_qa(args.candidates, out)
    tr = run_training_ready(args.prepared, out)
    lic = license_check()
    hn = hard_negative_assessment(ann)
    prov = provenance_stub(ann)
    dom = source_domination(ann)

    critical: list[str] = []
    warnings: list[str] = []
    critical.extend(ann.get("critical") or [])
    critical.extend(lic.get("critical") or [])
    critical.extend(hn.get("critical") or [])
    # prepared root training-ready failures are expected until construction;
    # treat as blockers for "A — TRAINING READY" but record separately
    prepared_blockers = list(tr.get("critical") or [])
    if not tr.get("gate_pass"):
        prepared_blockers.append("prepared YOLO root is not training-ready")

    # Hard construction rules
    comp = ann.get("completion") or {}
    annotated = comp.get("manually_annotated_files") or 0
    total = comp.get("total_candidates") or 0
    if annotated == 0:
        critical.append(
            "BLOCKED — MORE DATA REQUIRED: zero manual candidate annotations; "
            "cannot build meaningful session-aware test set"
        )

    # Do not construct final dataset
    constructed = False
    if args.construct_if_pass and not critical and annotated > 0:
        # Placeholder: construction would run here in a later iteration
        critical.append(
            "Construction path not entered: remaining prepared-root blockers "
            + str(prepared_blockers[:3])
        )
    else:
        warnings.append(
            "Canonical ai/dataset/ufm train/val/test NOT overwritten "
            "(gate failed or --construct-if-pass not satisfied)"
        )

    gate_pass = len(critical) == 0
    # Even with no critical from licenses alone, zero annotations => fail
    if annotated < max(1, int(0.5 * total)) if total else True:
        gate_pass = False
        if "ANNOTATION INCOMPLETE" not in " ".join(critical):
            critical.append(
                f"Insufficient annotation coverage: {annotated}/{total} candidates labeled"
            )

    status = "FAIL"
    final_status = "C — BLOCKED"
    if gate_pass:
        status = "PASS"
        final_status = "A — TRAINING READY"
    elif annotated == 0:
        final_status = "B — ANNOTATION/DATA COLLECTION STILL REQUIRED"
        status = "FAIL"
    else:
        final_status = "B — ANNOTATION/DATA COLLECTION STILL REQUIRED"
        status = "FAIL"

    # Statistics summary
    stats = {
        "candidates_total": total,
        "annotated_images": annotated,
        "missing_annotations": comp.get("missing_annotations"),
        "empty_negative_images": comp.get("empty_negative_labels"),
        "nonempty_labeled": comp.get("nonempty_labeled"),
        "objects_per_class": {
            k: v.get("object_count")
            for k, v in (comp.get("class_stats") or {}).items()
        },
        "sessions_in_candidates": (ann.get("duplicates") or {}).get("candidate_sessions"),
        "train_val_test": {
            "note": "Final session-aware splits NOT constructed — annotation incomplete",
            "train": None,
            "val": None,
            "test": None,
        },
        "prepared_root_inspection": {
            "gate_pass": tr.get("gate_pass"),
            "critical": prepared_blockers[:20],
        },
    }

    leakage = {
        "final_dataset_leakage_check": "NOT_RUN — final splits not constructed",
        "prepared_root_leakage": (tr.get("training_ready_checks") or {}).get("leakage"),
        "requirement": "intersection of train/val/test sessions must be empty",
        "result": "FAIL_PENDING_CONSTRUCTION",
    }

    dataset_gate = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "taxonomy": TAXONOMY,
        "gate_status": status,
        "gate_pass": gate_pass,
        "final_status": final_status,
        "critical": critical,
        "warnings": warnings + (lic.get("warnings") or []) + (hn.get("warnings") or []),
        "constructed_final_dataset": constructed,
        "coco_baseline_untouched": True,
        "custom_best_pt_not_enabled": True,
        "training_executed": False,
        "next_action": (
            "Manually annotate ai/annotation/candidates (LabelImg + classes.txt). "
            "Prioritize phone/watch/notes/gadget positives and true negatives. "
            "Re-run python ai/dataset_construction_gate.py after labels exist."
        ),
    }

    (out / "dataset_gate.json").write_text(json.dumps(dataset_gate, indent=2), encoding="utf-8")
    (out / "dataset_statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (out / "leakage_report.json").write_text(json.dumps(leakage, indent=2), encoding="utf-8")
    (out / "provenance_report.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    (out / "license_integration.json").write_text(json.dumps(lic, indent=2), encoding="utf-8")
    (out / "hard_negative_report.json").write_text(json.dumps(hn, indent=2), encoding="utf-8")
    (out / "source_domination.json").write_text(json.dumps(dom, indent=2), encoding="utf-8")

    # class_balance + duplicate already from annotation_qa
    print(json.dumps(dataset_gate, indent=2))
    print(f"GATE={status} FINAL={final_status}")
    return 0 if gate_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
