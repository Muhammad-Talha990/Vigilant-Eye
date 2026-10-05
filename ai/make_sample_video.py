"""
Build a short sample MP4 from UFM-relevant stills (phone / smartwatch exam scenes).

Usage:
  python ai/make_sample_video.py
"""

from __future__ import annotations

from pathlib import Path

import cv2


def main() -> None:
    root = Path(__file__).resolve().parent
    samples = root / "samples"
    out = samples / "sample_exam_clip.mp4"

    # Prefer clear phone/watch frames first (better for YOLO live demo)
    preferred = [
        samples / "phone_closeup.jpg",
        samples / "phone_on_desk.jpg",
        samples / "phone_under_desk.jpg",
        samples / "phone_in_lap.jpg",
        samples / "smartwatch_closeup.jpg",
        samples / "smartwatch.jpg",
        samples / "exam_hall.jpg",
    ]
    images = [p for p in preferred if p.exists()]
    if not images:
        images = sorted(samples.glob("*.jpg"))
    if not images:
        raise FileNotFoundError("No sample images found in ai/samples")

    width, height = 1280, 720
    fps = 5
    # Longer dwell on clear phone frames so live persist can confirm
    dwell = {
        "phone_closeup.jpg": 25,
        "phone_on_desk.jpg": 20,
        "smartwatch_closeup.jpg": 15,
    }

    writer = cv2.VideoWriter(
        str(out),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError("Failed to open VideoWriter")

    total_frames = 0
    for path in images:
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        frame = cv2.resize(frame, (width, height))
        n = dwell.get(path.name, 12)
        for _ in range(n):
            writer.write(frame)
            total_frames += 1

    writer.release()
    print(f"Created {out}")
    print(f"scenes={[p.name for p in images]}")
    print(f"frames={total_frames}, fps={fps}, duration~{total_frames / fps:.1f}s")


if __name__ == "__main__":
    main()
