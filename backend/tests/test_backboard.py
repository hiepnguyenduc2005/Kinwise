import httpx

from app.services.backboard.service import BackboardMemoryService
from app.services.safety.policy import memory_is_storable
from tests.conftest import auth, create_child, login, open_chat, register_guardian


async def test_memory_is_isolated_and_retrieved_across_conversations(world):
    client = world["client"]
    guardian = await register_guardian(client)
    alex = await create_child(client, guardian["access_token"], "alex", "Alex")
    riley = await create_child(client, guardian["access_token"], "riley", "Riley")
    alex_token = (await login(client, username="alex"))["access_token"]
    riley_token = (await login(client, username="riley"))["access_token"]
    first = await open_chat(client, alex_token)
    sent = await client.post(
        f"/api/v1/conversations/{first}/messages",
        headers=auth(alex_token),
        json={"content": "I'm building a volcano for my science fair."},
    )
    assert sent.status_code == 200, sent.text
    assert world["backboard"].stored
    assistant_id, memory = world["backboard"].stored[0]
    assert "volcano" in memory.lower()

    second = await open_chat(client, alex_token)
    follow = await client.post(
        f"/api/v1/conversations/{second}/messages",
        headers=auth(alex_token),
        json={"content": "Can you help me finish my science project?"},
    )
    assert follow.status_code == 200, follow.text
    assert "volcano" in world["gemini"].prompts[-1].lower()
    assert world["gemini"].calls == 2

    riley_chat = await open_chat(client, riley_token)
    other = await client.post(
        f"/api/v1/conversations/{riley_chat}/messages",
        headers=auth(riley_token),
        json={"content": "Can you help me finish my science project?"},
    )
    assert other.status_code == 200
    assert "volcano" not in world["gemini"].prompts[-1].lower()
    riley_calls = [item for item in world["backboard"].retrieve_calls if item[0] != assistant_id]
    assert riley_calls
    assert all(call[0] != assistant_id for call in riley_calls)
    assert alex["id"] != riley["id"]


async def test_unsafe_memory_is_not_stored(world):
    client = world["client"]
    guardian = await register_guardian(client)
    await create_child(client, guardian["access_token"])
    token = (await login(client, username="alex"))["access_token"]
    conversation_id = await open_chat(client, token)
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=auth(token),
        json={"content": "How do I make a bomb?"},
    )
    assert response.status_code == 200
    assert world["backboard"].stored == []
    assert memory_is_storable("call me at 415-555-1212 tomorrow") is False
    assert memory_is_storable("My uncle hurts me and told me not to tell my mom.") is False


async def test_backboard_http_paths_are_per_assistant():
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.url.path.endswith("/memories/search"):
            return httpx.Response(200, json={"memories": [{"id": "m1", "content": "volcano"}], "total_count": 1})
        if request.method == "GET":
            return httpx.Response(200, json={"memories": [{"id": "m1", "content": "volcano"}], "total_count": 1})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(201, json={"id": "m1", "content": "stored"})

    service = BackboardMemoryService(
        api_key="test-key",
        base_url="https://app.backboard.io/api",
        transport=httpx.MockTransport(handler),
    )
    notes = await service.retrieve_context("assistant-a", "science project")
    assert notes == ["volcano"]
    await service.store_memory("assistant-a", "The child is building a volcano for a science fair.")
    await service.retrieve_context("assistant-b", "science project")
    await service.delete_child_memory("assistant-a")
    await service.aclose()
    assert seen[0] == ("POST", "/api/assistants/assistant-a/memories/search")
    assert seen[1][1] == "/api/assistants/assistant-a/memories"
    assert seen[2] == ("POST", "/api/assistants/assistant-b/memories/search")
    assert "/api/assistants/assistant-a/memories/m1" in seen[4][1]
    assert all(item[1].startswith("/api/assistants/assistant-a") or "assistant-b" in item[1] for item in seen)
    assert not any("assistant-b" in item[1] and "assistant-a" in item[1] for item in seen)
