"""Authenticated WebSocket endpoint for real-time detection / suspicion alerts."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from case_access import DETECTION_STAFF_ROLES
from database import SessionLocal
from models.user import User
from security import decode_access_token
import ws_hub

router = APIRouter(tags=["websocket"])

_ALLOWED = set(DETECTION_STAFF_ROLES)


@router.websocket("/ws/alerts")
async def alerts_socket(websocket: WebSocket) -> None:
    """
    Accept the socket first so clients get close codes (not opaque HTTP 403),
    then authenticate. Unauthorized clients are closed with 4401/4403.
    """
    await websocket.accept()

    token = websocket.query_params.get("token") or ""
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except Exception:  # noqa: BLE001
        await websocket.close(code=4401, reason="invalid token")
        return

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        role = (getattr(user, "role", None) or "").strip().upper() if user else ""
        active = bool(getattr(user, "is_active", False)) if user else False
        if user is None or not active or role not in _ALLOWED:
            await websocket.close(code=4403, reason="forbidden role")
            return
    finally:
        db.close()

    await ws_hub.register(websocket, already_accepted=True)
    try:
        await websocket.send_json(
            {"type": "CONNECTED", "role": role, "message": "alert stream ready"}
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_hub.unregister(websocket)
