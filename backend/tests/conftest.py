import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app
from tests.fakes import FakeBackboard, FakeGemini, FakePhoton


@pytest.fixture
async def world(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/kinwise.db",
        jwt_secret="test-secret-test-secret-test-secret",
        environment="test",
        auth_rate_limit_enabled=False,
        spectrum_bridge_token="bridge-test-token",
        auto_create_schema=False,
    )
    gemini = FakeGemini()
    backboard = FakeBackboard()
    photon = FakePhoton()
    app = create_app(settings, gemini=gemini, backboard=backboard, photon=photon)
    async with app.state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "app": app,
            "gemini": gemini,
            "backboard": backboard,
            "photon": photon,
            "settings": settings,
        }
    await app.state.engine.dispose()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register_guardian(client: AsyncClient, email: str = "ada@example.com", name: str = "Ada") -> dict:
    response = await client.post(
        "/api/v1/auth/guardian/register",
        json={"email": email, "password": "guardian-pass", "display_name": name},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def create_child(client: AsyncClient, token: str, username: str = "alex", name: str = "Alex") -> dict:
    response = await client.post(
        "/api/v1/guardian/children",
        headers=auth(token),
        json={"username": username, "password": "child-pass", "display_name": name, "age_band": "9-11"},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def login(client: AsyncClient, **identifier) -> dict:
    payload = {"password": identifier.pop("password", "child-pass"), **identifier}
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


async def open_chat(client: AsyncClient, token: str) -> str:
    response = await client.post("/api/v1/conversations/", headers=auth(token), json={})
    assert response.status_code == 200, response.text
    return response.json()["id"]
