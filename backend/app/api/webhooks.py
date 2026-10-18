import hmac

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.services.commands import process_inbound_message

router = APIRouter()


class SpectrumInbound(BaseModel):
    message_id: str = Field(alias="messageId")
    text: str
    sender_id: str = Field(alias="senderId")
    space_id: str = Field(alias="spaceId")

    model_config = {"populate_by_name": True}


@router.post("/spectrum")
async def spectrum_inbound(body: SpectrumInbound, request: Request) -> JSONResponse:
    """Inbound texts from the local spectrum-ts process. Not a Photon OAuth callback."""
    expected = f"Bearer {request.app.state.settings.spectrum_bridge_token}"
    offered = request.headers.get("authorization", "")
    if not request.app.state.settings.spectrum_bridge_token or len(offered) != len(expected) or not hmac.compare_digest(offered, expected):
        raise AppError(401, "invalid_signature", "The Spectrum bridge token did not match.")
    payload = {
        "event": "messages",
        "space": {"id": body.space_id, "platform": "imessage"},
        "message": {
            "id": body.message_id,
            "direction": "inbound",
            "sender": {"id": body.sender_id, "platform": "imessage"},
            "content": {"type": "text", "text": body.text},
        },
    }
    async with request.app.state.sessionmaker() as session:
        try:
            result = await process_inbound_message(
                session,
                photon=request.app.state.photon,
                manager=request.app.state.manager,
                payload=payload,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return JSONResponse({"status": result.get("status", "ok")})
