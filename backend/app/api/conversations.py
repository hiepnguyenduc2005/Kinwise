import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_child
from app.models import User
from app.schemas.api import ConversationCreateIn, ConversationSummaryOut, MessageOut, SendMessageIn, SendMessageOut
from app.services.chat import create_conversation, list_conversations, list_messages, owned_conversation, send_child_message
from app.services.present import conversation_out, message_out

router = APIRouter()


@router.get("/", response_model=list[ConversationSummaryOut])
async def get_conversations(
    session: AsyncSession = Depends(get_db),
    child: User = Depends(require_child),
) -> list[ConversationSummaryOut]:
    rows = await list_conversations(session, child.id)
    return [conversation_out(item, for_child=True) for item in rows]


@router.post("/", response_model=ConversationSummaryOut)
async def post_conversation(
    body: ConversationCreateIn,
    session: AsyncSession = Depends(get_db),
    child: User = Depends(require_child),
) -> ConversationSummaryOut:
    conversation = await create_conversation(session, child, body)
    return conversation_out(conversation, for_child=True)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    child: User = Depends(require_child),
) -> list[MessageOut]:
    await owned_conversation(session, child.id, conversation_id)
    rows = await list_messages(session, conversation_id)
    return [message_out(item, for_guardian=False) for item in rows]


@router.post("/{conversation_id}/messages", response_model=SendMessageOut)
async def post_message(
    conversation_id: uuid.UUID,
    body: SendMessageIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    child: User = Depends(require_child),
) -> SendMessageOut:
    return await send_child_message(
        session,
        settings=request.app.state.settings,
        gemini=request.app.state.gemini,
        backboard=request.app.state.backboard,
        photon=request.app.state.photon,
        child=child,
        conversation_id=conversation_id,
        body=body,
    )
