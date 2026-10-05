"""In-process WebSocket alert fan-out for Invigilator / HOD dashboards."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from fastapi import WebSocket

_lock = threading.Lock()
_clients: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    global _loop
    _loop = loop


async def register(ws: WebSocket, *, already_accepted: bool = False) -> None:
    if not already_accepted:
        await ws.accept()
    with _lock:
        _clients.add(ws)


async def unregister(ws: WebSocket) -> None:
    with _lock:
        _clients.discard(ws)


def broadcast_alert(payload: dict[str, Any]) -> None:
    """Thread-safe broadcast from live_stream worker threads."""
    data = json.dumps(payload, default=str)
    with _lock:
        clients = list(_clients)
    if not clients:
        return

    async def _send_all() -> None:
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        if dead:
            with _lock:
                for ws in dead:
                    _clients.discard(ws)

    loop = _loop
    if loop is not None and loop.is_running():
        asyncio.run_coroutine_threadsafe(_send_all(), loop)
    else:
        # Best-effort when called from async context without stored loop
        try:
            running = asyncio.get_running_loop()
            running.create_task(_send_all())
        except RuntimeError:
            pass
