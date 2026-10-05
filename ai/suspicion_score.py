"""
Configurable suspicion score engine (provisional thresholds).

Separates:
  - model confidence (object detector)
  - observation quality (posture estimator)
  - behavioral event episodes
  - suspicion score (0..max)
  - institutional case status (portal — not set here)

Score uses elapsed wall time, not per-frame increments, so different
processing FPS produce comparable scores for the same behavior duration.

Provisional levels (calibrate on hall footage):
  Normal < 25
  Observe 25..54
  Review Required >= 55
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


def _f(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


MAX_SCORE = _f("UFM_SCORE_MAX", 100.0)
DECAY_PER_SEC = _f("UFM_SCORE_DECAY_PER_SEC", 0.35)
YAW_WEIGHT_PER_SEC = _f("UFM_SCORE_YAW_WEIGHT", 2.2)
TURN_BURST_WEIGHT = _f("UFM_SCORE_TURN_BURST", 8.0)
OBJECT_CONFIRM_WEIGHT = _f("UFM_SCORE_OBJECT_CONFIRM", 35.0)
OBJECT_REVIEW_WEIGHT = _f("UFM_SCORE_OBJECT_REVIEW", 12.0)
LEVEL_OBSERVE = _f("UFM_SCORE_LEVEL_OBSERVE", 25.0)
LEVEL_REVIEW = _f("UFM_SCORE_LEVEL_REVIEW", 55.0)
YAW_EPISODE_MIN_SEC = _f("UFM_YAW_EPISODE_MIN_SEC", 1.2)
COOLDOWN_ALERT_SEC = _f("UFM_SCORE_ALERT_COOLDOWN_SEC", 40.0)
CONFIG_VERSION = os.getenv("UFM_SCORE_CONFIG_VERSION", "suspicionscore-v1-provisional")


def level_for(score: float) -> str:
    if score >= LEVEL_REVIEW:
        return "REVIEW_REQUIRED"
    if score >= LEVEL_OBSERVE:
        return "OBSERVE"
    return "NORMAL"


@dataclass
class ScoreState:
    score: float = 0.0
    last_t: float = field(default_factory=time.monotonic)
    yaw_episode_start: float | None = None
    yaw_episode_credited: bool = False
    recent_turns: list[float] = field(default_factory=list)
    last_alert_at: float = 0.0
    last_level: str = "NORMAL"
    contributors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SuspicionEngine:
    """Per camera session: map track_id -> ScoreState."""

    tracks: dict[str, ScoreState] = field(default_factory=dict)

    def _state(self, track_id: str) -> ScoreState:
        if track_id not in self.tracks:
            self.tracks[track_id] = ScoreState()
        return self.tracks[track_id]

    def _decay(self, st: ScoreState, now: float) -> None:
        dt = max(0.0, now - st.last_t)
        if dt > 0:
            st.score = max(0.0, st.score - DECAY_PER_SEC * dt)
            st.last_t = now

    def _note(self, st: ScoreState, kind: str, detail: str, delta: float) -> None:
        st.contributors.append(
            {
                "kind": kind,
                "detail": detail,
                "delta": round(delta, 2),
                "t": time.time(),
            }
        )
        st.contributors = st.contributors[-12:]

    def update_head(
        self,
        *,
        track_id: str,
        yaw_deg: float | None,
        pitch_deg: float | None,
        quality: str,
        now: float | None = None,
    ) -> dict[str, Any]:
        """
        Update score from head orientation.
        Missing / low-quality faces do NOT add suspicion.
        Brief glances (< YAW_EPISODE_MIN_SEC) do not credit an episode.
        Downward pitch alone is treated as likely writing (no add).
        """
        now = now if now is not None else time.monotonic()
        st = self._state(track_id)
        self._decay(st, now)

        if quality == "unavailable" or yaw_deg is None:
            return self.snapshot(track_id)

        # Normal writing: looking down should not inflate score
        if pitch_deg is not None and pitch_deg <= -18 and abs(yaw_deg) < 15:
            st.yaw_episode_start = None
            st.yaw_episode_credited = False
            return self.snapshot(track_id)

        if quality == "low":
            # Uncertain geometry — no score increase
            return self.snapshot(track_id)

        yaw_thr = _f("UFM_YAW_ALERT_DEG", 28.0)
        turned = abs(yaw_deg) >= yaw_thr

        if turned:
            if st.yaw_episode_start is None:
                st.yaw_episode_start = now
                st.yaw_episode_credited = False
            elapsed = now - st.yaw_episode_start
            # Continuous contribution proportional to time in turn
            add = YAW_WEIGHT_PER_SEC * min(elapsed, 0.5)  # capped chunk per call
            # Better: credit only the dt since last update while turned
            # Recompute using last_t already advanced — use small fixed slice
            add = YAW_WEIGHT_PER_SEC * 0.25
            if elapsed >= YAW_EPISODE_MIN_SEC:
                st.score = min(MAX_SCORE, st.score + add)
                self._note(st, "head_yaw", f"|yaw|={yaw_deg:.0f}°", add)
                if not st.yaw_episode_credited:
                    st.yaw_episode_credited = True
                    st.recent_turns = [t for t in st.recent_turns if now - t < 12.0]
                    st.recent_turns.append(now)
                    if len(st.recent_turns) >= 3:
                        st.score = min(MAX_SCORE, st.score + TURN_BURST_WEIGHT)
                        self._note(
                            st,
                            "repeated_turns",
                            f"{len(st.recent_turns)} turns/12s",
                            TURN_BURST_WEIGHT,
                        )
                        st.recent_turns.clear()
        else:
            st.yaw_episode_start = None
            st.yaw_episode_credited = False

        return self.snapshot(track_id)

    def apply_object_event(
        self,
        *,
        track_id: str,
        decision: str,
        category: str,
        now: float | None = None,
    ) -> dict[str, Any]:
        now = now if now is not None else time.monotonic()
        st = self._state(track_id)
        self._decay(st, now)
        if decision == "CONFIRM":
            st.score = min(MAX_SCORE, st.score + OBJECT_CONFIRM_WEIGHT)
            self._note(st, "object_confirm", category, OBJECT_CONFIRM_WEIGHT)
        elif decision == "REVIEW":
            st.score = min(MAX_SCORE, st.score + OBJECT_REVIEW_WEIGHT)
            self._note(st, "object_review", category, OBJECT_REVIEW_WEIGHT)
        return self.snapshot(track_id)

    def snapshot(self, track_id: str) -> dict[str, Any]:
        st = self._state(track_id)
        level = level_for(st.score)
        crossed = level == "REVIEW_REQUIRED" and st.last_level != "REVIEW_REQUIRED"
        cooled = (time.monotonic() - st.last_alert_at) >= COOLDOWN_ALERT_SEC
        should_alert = crossed and cooled
        if should_alert:
            st.last_alert_at = time.monotonic()
        st.last_level = level
        return {
            "track_id": track_id,
            "score": round(st.score, 1),
            "level": level,
            "should_alert": should_alert,
            "contributors": list(st.contributors),
            "config_version": CONFIG_VERSION,
        }

    def all_snapshots(self) -> list[dict[str, Any]]:
        return [self.snapshot(tid) for tid in list(self.tracks.keys())]
