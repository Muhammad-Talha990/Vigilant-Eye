"""
Container entrypoint: bootstrap DB, then exec uvicorn.
Python entrypoint avoids Windows CRLF issues with .sh scripts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
os.chdir(BACKEND)
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import dev_bootstrap  # noqa: E402

print("=== VigilantEye API entrypoint ===")
dev_bootstrap.main()

print("Backend: starting uvicorn…")
os.execvp(
    sys.executable,
    [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ],
)
