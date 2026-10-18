from tests.conftest import auth, login, register_guardian


async def test_guardian_register_and_login(world):
    client = world["client"]
    created = await register_guardian(client)
    assert created["user"]["role"] == "guardian"
    assert "password" not in created["user"]

    bad = await client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401

    good = await login(client, email="ada@example.com", password="guardian-pass")
    assert good["user"]["id"] == created["user"]["id"]

    me = await client.get("/api/v1/auth/me", headers=auth(good["access_token"]))
    assert me.status_code == 200
    assert me.json()["role"] == "guardian"


async def test_child_cannot_self_register(world):
    response = await world["client"].post(
        "/api/v1/auth/child/register",
        json={"username": "alex", "password": "child-pass"},
    )
    assert response.status_code == 404


async def test_refresh_rotation_and_logout(world):
    client = world["client"]
    created = await register_guardian(client)
    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": created["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != created["refresh_token"]

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": created["refresh_token"]})
    assert reused.status_code == 401

    me = await client.get("/api/v1/auth/me", headers=auth(created["access_token"]))
    assert me.status_code == 401

    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout.status_code == 200
    revoked = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert revoked.status_code == 401
    current = await client.get("/api/v1/auth/me", headers=auth(new_tokens["access_token"]))
    assert current.status_code == 401
