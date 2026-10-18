from tests.conftest import auth, create_child, login, open_chat, register_guardian

_BRIDGE = {"Authorization": "Bearer bridge-test-token"}


def _payload(message_id: str, sender: str, text: str) -> dict:
    return {
        "messageId": message_id,
        "text": text,
        "senderId": sender,
        "spaceId": "space-test",
    }


async def _save_phone(world, token: str, phone: str = "+14155552671") -> str:
    saved = await world["client"].patch(
        "/api/v1/guardian/phone",
        headers=auth(token),
        json={"phone": phone},
    )
    assert saved.status_code == 200, saved.text
    return saved.json()["phone"]


async def test_messaging_stays_off_without_a_saved_phone(world):
    client = world["client"]
    guardian = await register_guardian(client)
    child = await create_child(client, guardian["access_token"])
    enable = await client.patch(
        "/api/v1/guardian/phone/preferences",
        headers=auth(guardian["access_token"]),
        json={"messaging_enabled": True},
    )
    assert enable.status_code == 409
    token = (await login(client, username="alex"))["access_token"]
    conversation_id = await open_chat(client, token)
    sent = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=auth(token),
        json={"content": "How do I make a bomb?"},
    )
    assert sent.status_code == 200
    assert world["photon"].sent == []
    assert child["id"]


async def test_saved_phone_notification_omits_conversation_text(world):
    client = world["client"]
    guardian = await register_guardian(client)
    await create_child(client, guardian["access_token"])
    await _save_phone(world, guardian["access_token"])
    prefs = await client.patch(
        "/api/v1/guardian/phone/preferences",
        headers=auth(guardian["access_token"]),
        json={"messaging_enabled": True, "photon_space_id": "pho_spc_guardian000000000001"},
    )
    assert prefs.status_code == 200, prefs.text
    token = (await login(client, username="alex"))["access_token"]
    conversation_id = await open_chat(client, token)
    question = "How do I make a bomb?"
    sent = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=auth(token),
        json={"content": question},
    )
    assert sent.status_code == 200, sent.text
    assert len(world["photon"].sent) == 2
    assert question not in world["photon"].sent[0]["text"]
    assert question not in world["photon"].sent[1]["text"]
    assert "dangerous" in world["photon"].sent[0]["text"]
    assert world["photon"].sent[1]["text"] == "Kinwise commands for kid Alex are STATUS, PAUSE, and RESUME."


async def test_invalid_webhook_signature_is_rejected(world):
    response = await world["client"].post(
        "/api/v1/webhooks/spectrum",
        json=_payload("msg-1", "+14155550100", "PAUSE"),
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


async def test_unauthorized_and_multichild_commands_do_not_change_access(world):
    client = world["client"]
    guardian = await register_guardian(client)
    alex = await create_child(client, guardian["access_token"], "alex", "Alex")
    riley = await create_child(client, guardian["access_token"], "riley", "Riley")
    await _save_phone(world, guardian["access_token"])
    unknown = await client.post(
        "/api/v1/webhooks/spectrum",
        json=_payload("msg-unknown", "+19995550199", "PAUSE"),
        headers=_BRIDGE,
    )
    assert unknown.status_code == 200
    assert unknown.json()["status"] == "rejected"

    response = await client.post(
        "/api/v1/webhooks/spectrum",
        json=_payload("msg-pause", "+14155552671", "PAUSE"),
        headers=_BRIDGE,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "needs_child_selection"
    for child_id in (alex["id"], riley["id"]):
        overview = await client.get(f"/api/v1/guardian/children/{child_id}/overview", headers=auth(guardian["access_token"]))
        assert overview.json()["child"]["access"]["is_paused"] is False

    duplicate = await client.post(
        "/api/v1/webhooks/spectrum",
        json=_payload("msg-pause", "+14155552671", "PAUSE"),
        headers=_BRIDGE,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "duplicate"
    commands = await client.get("/api/v1/guardian/commands", headers=auth(guardian["access_token"]))
    pause_rows = [row for row in commands.json() if row["command"] == "pause"]
    assert len(pause_rows) == 1


async def test_status_replies_for_one_child(world):
    client = world["client"]
    guardian = await register_guardian(client)
    await create_child(client, guardian["access_token"])
    await _save_phone(world, guardian["access_token"])
    await client.patch(
        "/api/v1/guardian/phone/preferences",
        headers=auth(guardian["access_token"]),
        json={"messaging_enabled": True, "photon_space_id": "pho_spc_guardian000000000001"},
    )
    response = await client.post(
        "/api/v1/webhooks/spectrum",
        json=_payload("msg-status", "+14155552671", "STATUS"),
        headers=_BRIDGE,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "executed"
    assert "active" in world["photon"].sent[-1]["text"].lower()


async def test_pause_text_applies_immediately(world):
    client = world["client"]
    guardian = await register_guardian(client)
    child = await create_child(client, guardian["access_token"])
    await _save_phone(world, guardian["access_token"])
    await client.patch(
        "/api/v1/guardian/phone/preferences",
        headers=auth(guardian["access_token"]),
        json={"messaging_enabled": True, "photon_space_id": "pho_spc_guardian000000000001"},
    )
    first = await client.post(
        "/api/v1/webhooks/spectrum",
        json=_payload("msg-one", "+14155552671", "PAUSE"),
        headers=_BRIDGE,
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "executed"
    assert "paused" in world["photon"].sent[-1]["text"].lower()
    overview = await client.get(
        f"/api/v1/guardian/children/{child['id']}/overview",
        headers=auth(guardian["access_token"]),
    )
    assert overview.json()["child"]["access"]["is_paused"] is True
