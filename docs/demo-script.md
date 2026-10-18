# Demo script

Use the seeded accounts or create new ones during the demo. Do not type a real child's private information.

Start the API with Gemini, Backboard, and Photon credentials in `.env` if those beats need live providers. `GET /api/v1/health` shows which ones are configured. Without a key, chat still returns a safe fallback and the health payload says the provider is off. That fallback is not a live Gemini reply.

## A. Safety intervention

1. Sign in as Ada (`ada@kinwise.demo` / `DemoPass123`) on one simulator or device.
2. Open Alex.
3. Sign in as Alex (`alex` / `DemoPass123`) on a second session.
4. Ask a synthetic unsafe question, such as a request for dangerous instructions. Do not use a real harmful how-to.
5. The server makes one Gemini call and returns structured safety data plus a proposed reply.
6. The policy replaces an unsafe reply. Alex sees the fixed refusal, not the model's instructions.
7. The safety event is in Ada's Safety tab. The message text is not in the notification.
8. If Ada's phone is saved, messaging is on, and the Spectrum bridge is running, Kinwise texts a short alert. The phone must be added as a Spectrum user.
9. Ada taps Pause. Alex's screen shows the paused state without waiting for a refresh poll, through the WebSocket.
10. Alex's next message is rejected and Gemini is not called.
11. Ada taps Resume. Alex can send again.

## B. Backboard memory

1. As Alex, say: "I'm building a volcano for my science fair."
2. After the policy allows it, the backend stores that fact on Alex's Backboard assistant.
3. Start a new conversation.
4. Ask: "Can you help me finish my science project?"
5. The prompt for the single Gemini call includes the volcano memory.
6. The reply can refer to the volcano project.
7. A different child does not receive Alex's memory.

The seeded volcano conversation is stored in PostgreSQL so the dashboard is populated even before this live path.

## C. Many-to-many guardians

1. Ada creates a child, or uses Alex.
2. Ada chooses Invite another guardian and reads the code once.
3. Sam signs in, enters the code, and waits.
4. Ada confirms with her password.
5. Both Ada and Sam see the child.
6. Either one can pause and resume. The creator badge is audit only.
7. Removing Sam works. Removing the last remaining guardian is rejected.

## D. A child says someone is hurting them

1. As Alex, enter a synthetic line such as a relative causing harm and asking the child not to tell.
2. Gemini may mislabel it. The backend still treats that wording as `self_harm` at high.
3. Alex sees the closed-chat sentence. Ada sees the original line and a supportive reply that says nobody was contacted.
4. Because the risk is high, a text is sent. It does not include Alex's words.
5. Access stays on. The chat is closed, and the account is not paused.

## Photon remote command

From the phone saved on the guardian account, text `STATUS`. For one child, `PAUSE` pauses immediately and replies that Kinwise paused them. With two children, the text must name a username, such as `PAUSE alex`. An invalid webhook signature is rejected.
