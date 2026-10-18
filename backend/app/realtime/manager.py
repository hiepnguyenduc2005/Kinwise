import logging
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """In-process WebSocket fan-out. One backend process only.

    Production multi-instance deployment needs shared pub/sub. This manager
    does not cross process boundaries.
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}

    async def connect(self, child_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(child_id, set()).add(websocket)

    def disconnect(self, child_id: uuid.UUID, websocket: WebSocket) -> None:
        sockets = self._connections.get(child_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(child_id, None)

    async def publish(self, child_id: uuid.UUID, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self._connections.get(child_id, set())):
            try:
                await websocket.send_json(payload)
            except Exception:
                logger.info("dropping closed child websocket")
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(child_id, websocket)
