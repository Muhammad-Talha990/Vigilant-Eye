# Optional learned posture classifier (scope Tools section)

The scope mentions a Python classifier/regressor on MediaPipe-derived angles
("Correct" / "Incorrect" posture).

## Status: INCOMPLETE (honest)

Delivered instead:
- Rule-based `ai/suspicion_score.py` (time-based, configurable, explainable).
- Angle extraction via `ai/posture_analysis.py` (MediaPipe when available, else OpenCV fallback).

## Why not claimed as trained
Training on labels generated solely from the same yaw/pitch thresholds would
circularly validate the rule engine — forbidden by the submission prompt.

## To complete later
1. Collect sequences: `(yaw, pitch, roll, dt)` with human labels Observe/Review.
2. Store under `ai/dataset/posture_sequences/`.
3. Train a small sklearn/MLP regressor; save `ai/weights/posture_clf.joblib`.
4. Compare against rule baseline on a held-out recording (report both).

Do not enable a "trained" flag in the portal until steps 1–4 exist.
