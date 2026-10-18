import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token, utcnow
from app.models import AuthSession, ChildAccessState, User
from app.services.present import access_payload

router = APIRouter()


@router.websocket("/child-access")
async def child_access(websocket: WebSocket) -> None:
    token = ""
    header = websocket.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
    if not token:
        token = websocket.query_params.get("access_token", "")
    settings = websocket.app.state.settings
    try:
        payload = decode_access_token(token, settings.jwt_secret)
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
    except Exception:
        await websocket.close(code=4401)
        return

    async with websocket.app.state.sessionmaker() as session:
        auth_session = await session.get(AuthSession, session_id)
        user = await session.get(User, user_id)
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at < utcnow()
            or user is None
            or user.role != "child"
            or user.id != auth_session.user_id
        ):
            await websocket.close(code=4401)
            return
        state = await session.get(ChildAccessState, user.id)
        if state is None:
            await websocket.close(code=4404)
            return
        snapshot = access_payload(user.id, state)
        child_id = user.id

    await websocket.app.state.manager.connect(child_id, websocket)
    try:
        await websocket.send_json(snapshot)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        websocket.app.state.manager.disconnect(child_id, websocket)
