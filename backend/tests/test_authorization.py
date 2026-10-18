from tests.conftest import auth, create_child, login, open_chat, register_guardian


async def test_guardian_cannot_access_unrelated_child(world):
    client = world["client"]
    ada = await register_guardian(client, "ada@example.com", "Ada")
    sam = await register_guardian(client, "sam@example.com", "Sam")
    alex = await create_child(client, ada["access_token"])
    denied = await client.get(f"/api/v1/guardian/children/{alex['id']}/overview", headers=auth(sam["access_token"]))
    assert denied.status_code == 403


async def test_child_cannot_read_another_child_or_call_guardian_routes(world):
    client = world["client"]
    ada = await register_guardian(client)
    alex = await create_child(client, ada["access_token"], "alex", "Alex")
    await create_child(client, ada["access_token"], "riley", "Riley")
    alex_token = (await login(client, username="alex"))["access_token"]
    riley_token = (await login(client, username="riley"))["access_token"]
    conversation_id = await open_chat(client, alex_token)
    stolen = await client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=auth(riley_token))
    assert stolen.status_code == 404
    guardian_route = await client.get("/api/v1/guardian/children", headers=auth(alex_token))
    assert guardian_route.status_code == 403
    assert alex["id"] != riley_token
