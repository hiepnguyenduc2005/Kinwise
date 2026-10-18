# Kinwise

Curiosity, with care.

Kinwise is a native iOS learning companion for children, with equal guardian supervision. A child can talk with the assistant. The backend calls Gemini **once** for each eligible message, checks that reply with a deterministic safety policy, stores the conversation in Tiger Data (PostgreSQL), and can remember safe facts in Backboard. A guardian can pause access, and the child app updates over an authenticated WebSocket.

This is a DubHacks 2026 MVP. It is **not** a production child-safety product and it is **not** a legal determination of guardianship.

## What works

- Guardian registration and login with email and password.
- Guardian-created child accounts. Children cannot self-register and sign in with a username.
- Many-to-many guardian–child links. No primary guardian. The creating guardian is audit metadata only.
- Invitation codes that stay pending until the inviting guardian confirms with their password.
- The last active guardian cannot be removed.
- Child chat that persists in PostgreSQL.
- One Gemini structured-output call per eligible message. Paused children cause zero calls. A pause during generation withholds the reply.
- Deterministic policy for dangerous requests, distress, and sensitive disclosures. High and critical events text guardians without including the child's words.
- Backboard memory isolated per child assistant, used on later conversations.
- Guardian dashboard metrics computed from saved rows.
- Real-time pause and resume on a single backend process.
- Spectrum iMessage. A Node bridge receives texts and FastAPI decides the reply. `PAUSE` and `RESUME` take effect on that text. Several children require a username.

## Stack

| Layer | Choice |
|---|---|
| iOS | Swift 6, SwiftUI, iOS 17+ |
| API | FastAPI, Pydantic v2 |
| Database | Tiger Data / PostgreSQL, SQLAlchemy 2, Alembic |
| Passwords | Argon2id |
| Sessions | Short-lived HS256 access tokens, rotating hashed refresh tokens, iOS Keychain |
| Model | Google Gemini `generateContent` with a JSON schema |
| Memory | Backboard assistants and memories |
| Messaging | Spectrum `spectrum-ts` bridge for the dashboard iMessage project |
| Guardian phone | Optional profile field. A short digit check, with no SMS verification. |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Put the Tiger Cloud URL in `DATABASE_URL`. The app accepts `postgres://` and `postgresql://` URLs and rewrites `sslmode` to the `ssl` parameter asyncpg expects.

```bash
cd backend
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

iMessage uses the Spectrum project you already created. In another terminal:

```bash
cd spectrum
npm install
npm start
```

`npm start` reads `SPECTRUM_PROJECT_ID`, `SPECTRUM_PROJECT_SECRET`, and `SPECTRUM_BRIDGE_TOKEN` from the repo `.env`.

`SPECTRUM_PROJECT_ID` is the UUID on the getting-started page. `SPECTRUM_PROJECT_SECRET` is the secret on that page. Leave the Photon OAuth app, redirect URIs, and scopes unused. Add the guardian's phone under Spectrum users, because the shared line only answers numbers that were added.

Health check: `GET /api/v1/health`. It reports which provider credentials are present. It does not print secrets.

Open `ios/Kinwise.xcodeproj` in Xcode 16 or newer, select an iOS 17 simulator, and run. The API base URL is `KINWISE_API_BASE_URL` in `ios/Kinwise/Resources/Info.plist` and defaults to `http://127.0.0.1:8000`.

This workspace was built with Command Line Tools only, so the iOS target was not launched in Simulator here.

## Demo accounts

`python backend/scripts/seed_demo.py` creates synthetic accounts. The password is `DemoPass123` for all three.

- Ada, guardian: `ada@kinwise.demo`
- Sam, guardian: `sam@kinwise.demo`
- Alex, child: `alex`

Seeded history includes an ordinary volcano conversation and one restricted disclosure so the guardian view can be checked without using a real child's information.

## Tests

```bash
cd backend
pytest
```

Tests use SQLite and fake Gemini, Backboard, and Photon adapters. They do not call paid providers.

## Not implemented on purpose

- Email verification and email password recovery. No email provider is configured. Guardians can change their own password while signed in, and can reset a child's password after re-entering their own password.
- Multi-instance WebSocket fan-out. Pause events stay in process. Production needs shared pub/sub.
- A claim that emergency services were contacted. The product never does that.

## Documents

- [Architecture](docs/architecture.md)
- [API contract](docs/api-contract.md)
- [Safety policy](docs/safety-policy.md)
- [Demo script](docs/demo-script.md)
