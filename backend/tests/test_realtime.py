from starlette.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.fakes import FakeBackboard, FakeGemini, FakePhoton


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_pause_resume_and_reconnect_restore_server_state(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/realtime.db",
        jwt_secret="test-secret-test-secret-test-secret",
        environment="test",
        auth_rate_limit_enabled=False,
        auto_create_schema=True,
        spectrum_bridge_token="bridge-test-token",
    )
    app = create_app(
        settings,
        gemini=FakeGemini(),
        backboard=FakeBackboard(),
        photon=FakePhoton(),
    )
    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/guardian/register",
            json={"email": "ws@example.com", "password": "guardian-pass", "display_name": "Wes"},
        )
        assert registered.status_code == 200, registered.text
        guardian_token = registered.json()["access_token"]
        created = client.post(
            "/api/v1/guardian/children",
            headers=_headers(guardian_token),
            json={"username": "wskid", "password": "child-pass", "display_name": "Wynn", "age_band": "9-11"},
        )
        assert created.status_code == 200, created.text
        child_id = created.json()["id"]
        logged = client.post("/api/v1/auth/login", json={"username": "wskid", "password": "child-pass"})
        child_token = logged.json()["access_token"]

        with client.websocket_connect(
            "/api/v1/realtime/child-access",
            headers={"Authorization": f"Bearer {child_token}"},
        ) as websocket:
            initial = websocket.receive_json()
            assert initial["is_paused"] is False
            paused = client.post(f"/api/v1/guardian/children/{child_id}/pause", headers=_headers(guardian_token))
            assert paused.status_code == 200, paused.text
            update = websocket.receive_json()
            assert update["is_paused"] is True
            assert update["state_version"] > initial["state_version"]
            resumed = client.post(f"/api/v1/guardian/children/{child_id}/resume", headers=_headers(guardian_token))
            assert resumed.status_code == 200, resumed.text
            resumed_event = websocket.receive_json()
            assert resumed_event["is_paused"] is False

        with client.websocket_connect(
            "/api/v1/realtime/child-access",
            headers={"Authorization": f"Bearer {child_token}"},
        ) as again:
            snapshot = again.receive_json()
            assert snapshot["is_paused"] is False
            assert snapshot["state_version"] == resumed_event["state_version"]
