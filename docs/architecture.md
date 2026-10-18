# Architecture

Kinwise keeps one server-side decision path for every child message.

```text
Child message
  -> authenticate the child session
  -> confirm the conversation belongs to that child
  -> reject if paused or over the daily limit (no Gemini call)
  -> read that child's Backboard memories
  -> one Gemini generateContent call
       structured safety assessment + proposed reply
  -> validate JSON
  -> deterministic policy (the model does not decide)
  -> re-read pause state
  -> if paused, withhold the reply
  -> save the approved reply in PostgreSQL
  -> store a safe memory only after approval
  -> notify guardians with a saved phone and messaging on, only when the policy allows it
```

Raw model text is not returned until that policy finishes. Generation failures, malformed JSON, timeouts, and Gemini safety blocks become a fixed fallback. The backend does not retry the model.

## Accounts

Guardians and children are rows in `users` with independent sessions. A guardian registers with email. A child is created only by an authenticated guardian, in the same transaction as the first active `guardian_child_links` row and the `child_access_state` row. If the link insert fails, the child account is rolled back.

Links are many-to-many and status is `pending`, `active`, or `revoked`. There is no primary guardian column. `child_profiles.created_by_guardian_id` is audit metadata. Any active guardian can view, pause, resume, invite, and remove another guardian. Removing the last active link is rejected.

Invitations are single-use, hashed, and expire in 24 hours. Accepting a code creates a pending link. The inviting guardian confirms it with their current password before it becomes active.

Access tokens are short-lived JWTs. The `sid` claim is checked against `auth_sessions` on every request, so logout and refresh rotation revoke the previous token immediately. Refresh tokens are random secrets stored as SHA-256 hashes. The iOS app keeps the refresh token in the Keychain.

Roles and user ids from the client are ignored. Routes derive both from the session.

## Providers

Gemini uses the Google Gen AI SDK: `models.generate_content` with `response_mime_type=application/json` and `response_schema` set to the Pydantic `GeminiTurn` model. That is one generation call. There is no second safety-classifier call.

Backboard uses the documented HTTP API at `https://app.backboard.io/api` with `X-API-Key`:

- `POST /assistants`
- `POST /assistants/{assistant_id}/memories/search`
- `POST /assistants/{assistant_id}/memories`
- `GET /assistants/{assistant_id}/memories`
- `DELETE /assistants/{assistant_id}/memories/{memory_id}`

Each child gets their own assistant id. Memory text is filtered before storage. Retrieved memories are placed in the prompt as untrusted data, not as instructions. Tiger Data remains the conversation record. If Backboard is down, chat continues without memory.

iMessage uses the Spectrum project from the Photon dashboard. A small Node process in `spectrum/` runs `spectrum-ts` with `SPECTRUM_PROJECT_ID` and `SPECTRUM_PROJECT_SECRET`. It listens on `app.messages` and posts each inbound text to FastAPI at `/api/v1/webhooks/spectrum`, using `SPECTRUM_BRIDGE_TOKEN`. FastAPI sends replies and safety alerts back to `http://127.0.0.1:8787/send`, and the Spectrum process calls `space.send`. This does not use a Photon OAuth app or redirect URI.

The sender phone on an inbound message is matched to the phone saved on the guardian account. That phone must also be added under Spectrum users, because a shared iMessage line only answers numbers that were added. An unknown number cannot pause anyone. `PAUSE` and `RESUME` take effect on that text. If the guardian has several children, the command must name a username.

A guardian phone is an optional `users.phone` field. The API accepts 10 to 15 digits, with an optional leading `+`, and ignores spaces, dashes, dots, and parentheses. There is no SMS verification step.

## Realtime

`WS /api/v1/realtime/child-access` requires the child access token. The server sends the current pause snapshot, then pushes newer versions after a guardian pause or resume. The child app also refetches access on launch and when returning to the foreground. The connection manager is in-process. More than one API instance needs a shared pub/sub bus, which this MVP does not include.

## Guardian visibility

Ordinary transcripts, summaries, usage counts, and safety categories are available to every active guardian. On a closed safeguarding chat, guardians see the original messages and an italic note of the sentence the child sees. The child API returns only that closed-chat sentence, and the conversation accepts no further messages. Internal model reasons, system prompts, and raw Backboard memories are not guardian APIs.
