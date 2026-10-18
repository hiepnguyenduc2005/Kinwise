"""Outbound iMessage through the local Spectrum bridge."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PhotonMessagingService:
    def __init__(self, *, bridge_url: str = "", bridge_token: str = "") -> None:
        self.bridge_url = bridge_url.rstrip("/")
        self.bridge_token = bridge_token
        self.configured = bool(self.bridge_url and self.bridge_token)
        self.unavailable_reason = None if self.configured else "Spectrum bridge is not configured"

    async def aclose(self) -> None:
        return None

    async def send_text(
        self,
        *,
        space_id: str,
        text: str,
        idempotency_key: str,
        phone: str | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            return {"status": "skipped_unconfigured", "detail": self.unavailable_reason}
        if not space_id and not phone:
            return {"status": "skipped_missing_space", "detail": "A Spectrum conversation id or phone number is required."}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
                response = await client.post(
                    f"{self.bridge_url}/send",
                    headers={"Authorization": f"Bearer {self.bridge_token}"},
                    json={
                        "spaceId": space_id,
                        "phone": phone,
                        "text": text[:600],
                        "idempotencyKey": idempotency_key[:255],
                        "notify": idempotency_key.startswith("safety-"),
                    },
                )
        except Exception as exc:
            logger.warning("spectrum bridge send failed: %s", type(exc).__name__)
            return {"status": "provider_error", "detail": type(exc).__name__}
        try:
            payload = response.json()
        except Exception:
            payload = {"body": response.text[:500]}
        if response.status_code not in {200, 202}:
            payload["status"] = "provider_error"
            payload["http_status"] = response.status_code
        payload.setdefault("status", "sent")
        return payload
