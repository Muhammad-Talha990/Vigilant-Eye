"""Force password-capable auth for API tests without changing production Compose.

Valid AUTH_MODE values are demo | google | both (not \"hybrid\").
Compose may set AUTH_MODE=google for the live API process; pytest must override
that for in-process TestClient suites that exercise password login.
"""

from __future__ import annotations

import os

# Force (do not setdefault) so Google-only Compose env does not break pytest.
os.environ["APP_ENV"] = "development"
os.environ["AUTH_MODE"] = "both"
os.environ["PASSWORD_LOGIN_ENABLED"] = "1"
os.environ["EMAIL_ENABLED"] = "0"
os.environ["ENABLE_DEMO_SEED"] = "0"
os.environ["ENABLE_API_DOCS"] = "1"
