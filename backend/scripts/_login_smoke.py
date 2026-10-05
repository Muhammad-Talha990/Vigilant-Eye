import json
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8000/auth/login",
    data=json.dumps(
        {"email": "invigilator@demo.com", "password": "Demo@123"}
    ).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode())
        print("status", resp.status)
        print("role", body.get("user", {}).get("role") or body.get("role"))
        print("has_token", bool(body.get("access_token") or body.get("token")))
except Exception as e:
    print("ERR", type(e).__name__, e)
    if hasattr(e, "read"):
        print(e.read().decode()[:500])
