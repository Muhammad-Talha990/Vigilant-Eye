"""
Formal class mappings from license-cleared external exports → VigilantEye OD taxonomy.

Taxonomy version: ufm-od-taxonomy-v1
Dataset version target: ufm-od-v0.1

NO TRAINING. This module documents and optionally remaps label files when
building the final dataset (future phase).

VigilantEye object classes (fixed unless documented change):
  0 mobile_phone
  1 smart_watch
  2 normal_watch
  3 notes_paper
  4 electronic_gadget

Temporal (NOT mapped to YOLO classes):
  paper_exchange, peer_looking, posture
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal["include", "exclude", "negative_only"]


VE_CLASS_NAMES = [
    "mobile_phone",
    "smart_watch",
    "normal_watch",
    "notes_paper",
    "electronic_gadget",
]

VE_CLASS_TO_ID = {n: i for i, n in enumerate(VE_CLASS_NAMES)}


@dataclass(frozen=True)
class SourceMapping:
    dataset_id: str
    source_class: str
    source_id: int | None
    ve_class: str | None
    action: Action
    reason: str


# ---------------------------------------------------------------------------
# offline-exam-monitoring-4 (CC BY 4.0 per local data.yaml + README.dataset.txt)
# ---------------------------------------------------------------------------
OFFLINE_EXAM_MONITORING_4: list[SourceMapping] = [
    SourceMapping(
        "offline-exam-monitoring-4",
        "phone",
        4,
        "mobile_phone",
        "include",
        "Direct object class; maps cleanly to mobile_phone.",
    ),
    SourceMapping(
        "offline-exam-monitoring-4",
        "cheating-paper",
        3,
        "notes_paper",
        "include",
        "Unauthorized paper/cheat material proxy → notes_paper after visual QA.",
    ),
    SourceMapping(
        "offline-exam-monitoring-4",
        "Cheating",
        0,
        None,
        "exclude",
        "Behavior/activity label, not a single object class.",
    ),
    SourceMapping(
        "offline-exam-monitoring-4",
        "Non-Cheating",
        2,
        None,
        "negative_only",
        "Use images as negatives if no other included boxes remain after remap.",
    ),
    SourceMapping(
        "offline-exam-monitoring-4",
        "Hand-Normalmove",
        1,
        None,
        "exclude",
        "Hand/motion behavior; not an OD prohibited-object class.",
    ),
]


# ---------------------------------------------------------------------------
# wrist-watch (CC BY 4.0 per local data.yaml + README.dataset.txt)
# ---------------------------------------------------------------------------
WRIST_WATCH: list[SourceMapping] = [
    SourceMapping(
        "wrist-watch",
        "wrist watch",
        0,
        None,
        "exclude",
        "Cannot distinguish smart_watch vs normal_watch from a single class name. "
        "Do not map all watches to smart_watch (would poison allowed-class learning). "
        "Optional future: manual re-label subset into smart_watch / normal_watch.",
    ),
]


# ---------------------------------------------------------------------------
# Exam cheating v1 — CORRUPT names in local data.yaml; EXCLUDE from final set
# ---------------------------------------------------------------------------
EXAM_CHEATING_V1: list[SourceMapping] = [
    SourceMapping(
        "exam-cheating-v1",
        "<corrupt yaml names>",
        None,
        None,
        "exclude",
        "Local data.yaml names are README fragments, not class labels. "
        "IDs 0–7 exist in .txt files but mapping cannot be proven without "
        "authoritative class list. Exclude until reconstructed from verified metadata.",
    ),
]


ALL_MAPPINGS: list[SourceMapping] = (
    OFFLINE_EXAM_MONITORING_4 + WRIST_WATCH + EXAM_CHEATING_V1
)


def included_source_to_ve() -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for m in ALL_MAPPINGS:
        if m.action == "include" and m.ve_class:
            out[(m.dataset_id, m.source_class)] = m.ve_class
    return out


def remap_class_id(dataset_id: str, source_id: int) -> int | None:
    """Return VigilantEye class id, or None to drop the box."""
    for m in ALL_MAPPINGS:
        if m.dataset_id != dataset_id:
            continue
        if m.source_id is None:
            continue
        if m.source_id != source_id:
            continue
        if m.action != "include" or not m.ve_class:
            return None
        return VE_CLASS_TO_ID[m.ve_class]
    return None


if __name__ == "__main__":
    print("VigilantEye taxonomy:", VE_CLASS_NAMES)
    print("Include mappings:")
    for (ds, src), ve in included_source_to_ve().items():
        print(f"  {ds} :: {src} -> {ve}")
    print("Excluded / special:")
    for m in ALL_MAPPINGS:
        if m.action != "include":
            print(f"  [{m.action}] {m.dataset_id} :: {m.source_class} - {m.reason}")
