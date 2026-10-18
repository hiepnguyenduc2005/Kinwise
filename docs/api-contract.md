# API contract

Base path: `/api/v1`. Authenticated routes use `Authorization: Bearer <access token>`. Errors use:

```json
{ "detail": { "code": "forbidden", "message": "You are not a guardian for this child." } }
```

The server decides the role. A child token cannot call `/guardian` routes. A guardian token cannot read another family's child.

## Auth

| Method | Path | Body |
|---|---|---|
| POST | `/auth/guardian/register` | `email`, `password`, `display_name`, optional `phone` |
| POST | `/auth/login` | `password` and exactly one of `email` or `username` |
| POST | `/auth/refresh` | `refresh_token` |
| POST | `/auth/logout` | `refresh_token` |
| GET | `/auth/me` |  |
| PATCH | `/auth/me` | `display_name` |
| POST | `/auth/change-password` | `current_password`, `new_password` |

Login and register return `access_token`, `refresh_token`, `expires_in`, and `user`. Refresh revokes the presented refresh token and returns a new pair. There is no child registration route.

## Guardian and children

| Method | Path | Notes |
|---|---|---|
| GET | `/guardian/children` | Active links, pause state, messages today |
| POST | `/guardian/children` | `username`, `password`, `display_name`, `age_band` |
| GET | `/guardian/children/{child_id}/overview` | Profile, usage, recent safety, recent conversations |
| GET | `/guardian/children/{child_id}/conversations` | Policy-filtered titles and summaries |
| GET | `/guardian/children/{child_id}/conversations/{conversation_id}/messages` | Guardians receive the original `content` plus `child_facing_text` when a message was closed for the child |
| GET | `/guardian/children/{child_id}/safety-events` | Category, severity, summary, recommended action |
| GET | `/guardian/children/{child_id}/usage` | Counts from stored messages and events |
| POST | `/guardian/children/{child_id}/pause` | Increments `state_version` and publishes |
| POST | `/guardian/children/{child_id}/resume` | Same |
| PATCH | `/guardian/children/{child_id}/settings` | `display_name`, `age_band` |
| POST | `/guardian/children/{child_id}/credentials` | Guardian `current_password`, child `new_password` |
| POST | `/guardian/children/{child_id}/invitations` | Returns the plaintext code once |
| GET | `/guardian/children/{child_id}/invitations` | Pending and historical invites for this child |
| POST | `/guardian/invitations/accept` | `{ "code": "..." }` |
| POST | `/guardian/invitations/{invitation_id}/confirm` | Inviting guardian's `current_password` |
| GET | `/guardian/children/{child_id}/guardians` | Equal active guardians. `created_by_audit` is informational |
| DELETE | `/guardian/children/{child_id}/guardians/{guardian_id}` | Body: `current_password`. Rejects the last guardian |
| DELETE | `/guardian/children/{child_id}/memory` | Deletes that child's Backboard memories |
| POST | `/guardian/safety-events/{event_id}/acknowledge` |  |
| GET | `/guardian/commands` | Photon commands for the signed-in guardian |
| POST | `/guardian/commands/{command_id}/select` | Password plus `child_id` when several children match |

Age bands: `6-8`, `9-11`, `12-14`, `15-17`.

## Phone

| Method | Path | Notes |
|---|---|---|
| GET | `/guardian/phone` | Returns `phone`, `messaging_enabled`, `photon_space_id` |
| PATCH | `/guardian/phone` | `phone`. Empty clears it. Checked with `^\+?[0-9]{10,15}$` after stripping separators. |
| PATCH | `/guardian/phone/preferences` | `messaging_enabled`, optional `photon_space_id` |

Messaging cannot be enabled until a phone is saved. There is no verification code.

## Child

| Method | Path | Notes |
|---|---|---|
| GET | `/children/me` | Includes the supervision notice |
| GET | `/children/me/access` | `is_paused`, `state_version`, `updated_at` |
| GET | `/conversations/` | Owned by the session child |
| POST | `/conversations/` | Optional `title` |
| GET | `/conversations/{conversation_id}/messages` |  |
| POST | `/conversations/{conversation_id}/messages` | `{ "content": "..." }` |

A paused child receives `409 access_paused` and Gemini is not called. If a pause lands while generation is in flight, the response is `409 response_withheld` and the model text is not included.

A successful send returns `user_message`, `assistant_message`, and `access`. Assistant content is the policy result, which may be a fixed fallback.

## Integrations and realtime

| Method | Path |
|---|---|
| POST | `/webhooks/spectrum` |
| GET | `/health` |
| WS | `/realtime/child-access` |

The Spectrum webhook requires `Authorization: Bearer` matching `SPECTRUM_BRIDGE_TOKEN`. A mismatch returns 401. Duplicate message ids do not run the command again.

The socket sends:

```json
{
  "type": "access_state",
  "child_id": "...",
  "is_paused": true,
  "state_version": 4,
  "updated_at": "2026-10-17T00:00:00+00:00"
}
```

Clients should ignore versions older than the one they already applied.
