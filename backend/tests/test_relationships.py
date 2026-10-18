from sqlalchemy import func, select

from app.models import GuardianChildLink, User
from tests.conftest import auth, create_child, login, register_guardian


async def test_guardian_creates_child_atomically(world):
    client = world["client"]
    guardian = await register_guardian(client)
    child = await create_child(client, guardian["access_token"])
    assert child["username"] == "alex"
    assert "password" not in child
    logged_in = await login(client, username="alex", password="child-pass")
    assert logged_in["user"]["role"] == "child"

    duplicate = await client.post(
        "/api/v1/guardian/children",
        headers=auth(guardian["access_token"]),
        json={"username": "alex", "password": "child-pass", "display_name": "Other", "age_band": "9-11"},
    )
    assert duplicate.status_code == 409
    async with world["app"].state.sessionmaker() as session:
        users = await session.scalar(select(func.count()).select_from(User).where(User.username == "alex"))
        links = await session.scalar(select(func.count()).select_from(GuardianChildLink))
    assert users == 1
    assert links == 1


async def test_many_to_many_and_last_guardian(world):
    client = world["client"]
    ada = await register_guardian(client, "ada@example.com", "Ada")
    sam = await register_guardian(client, "sam@example.com", "Sam")
    alex = await create_child(client, ada["access_token"], "alex", "Alex")
    riley = await create_child(client, ada["access_token"], "riley", "Riley")
    children = await client.get("/api/v1/guardian/children", headers=auth(ada["access_token"]))
    assert len(children.json()) == 2

    invite = await client.post(f"/api/v1/guardian/children/{alex['id']}/invitations", headers=auth(ada["access_token"]))
    assert invite.status_code == 200, invite.text
    code = invite.json()["code"]
    accepted = await client.post(
        "/api/v1/guardian/invitations/accept",
        headers=auth(sam["access_token"]),
        json={"code": code},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "pending_confirmation"
    hidden = await client.get(f"/api/v1/guardian/children/{alex['id']}/overview", headers=auth(sam["access_token"]))
    assert hidden.status_code == 403

    confirmed = await client.post(
        f"/api/v1/guardian/invitations/{accepted.json()['invitation_id']}/confirm",
        headers=auth(ada["access_token"]),
        json={"current_password": "guardian-pass"},
    )
    assert confirmed.status_code == 200, confirmed.text
    reused = await client.post(
        "/api/v1/guardian/invitations/accept",
        headers=auth(sam["access_token"]),
        json={"code": code},
    )
    assert reused.status_code == 400

    sam_children = await client.get("/api/v1/guardian/children", headers=auth(sam["access_token"]))
    assert [item["username"] for item in sam_children.json()] == ["alex"]
    guardians = await client.get(f"/api/v1/guardian/children/{alex['id']}/guardians", headers=auth(sam["access_token"]))
    assert len(guardians.json()) == 2
    assert sum(1 for item in guardians.json() if item["created_by_audit"]) == 1

    paused = await client.post(f"/api/v1/guardian/children/{alex['id']}/pause", headers=auth(sam["access_token"]))
    assert paused.status_code == 200
    assert paused.json()["is_paused"] is True
    resumed = await client.post(f"/api/v1/guardian/children/{alex['id']}/resume", headers=auth(ada["access_token"]))
    assert resumed.json()["is_paused"] is False

    stranger = await register_guardian(client, "nope@example.com", "Nope")
    blocked = await client.post(
        f"/api/v1/guardian/children/{alex['id']}/invitations",
        headers=auth(stranger["access_token"]),
    )
    assert blocked.status_code == 403
    child_token = (await login(client, username="alex"))["access_token"]
    child_invite = await client.post(
        f"/api/v1/guardian/children/{alex['id']}/invitations",
        headers=auth(child_token),
    )
    assert child_invite.status_code == 403

    duplicate_invite = await client.post(
        f"/api/v1/guardian/children/{alex['id']}/invitations",
        headers=auth(ada["access_token"]),
    )
    again = await client.post(
        "/api/v1/guardian/invitations/accept",
        headers=auth(sam["access_token"]),
        json={"code": duplicate_invite.json()["code"]},
    )
    assert again.status_code == 409

    removed = await client.request(
        "DELETE",
        f"/api/v1/guardian/children/{alex['id']}/guardians/{sam['user']['id']}",
        headers=auth(ada["access_token"]),
        json={"current_password": "guardian-pass"},
    )
    assert removed.status_code == 200, removed.text
    last = await client.request(
        "DELETE",
        f"/api/v1/guardian/children/{alex['id']}/guardians/{ada['user']['id']}",
        headers=auth(ada["access_token"]),
        json={"current_password": "guardian-pass"},
    )
    assert last.status_code == 409
    assert last.json()["detail"]["code"] == "last_guardian"
    untouched = await client.get(f"/api/v1/guardian/children/{riley['id']}/overview", headers=auth(sam["access_token"]))
    assert untouched.status_code == 403
