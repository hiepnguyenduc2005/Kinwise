# Safety policy

Kinwise asks Gemini for a safety assessment and a proposed reply in the same response. FastAPI then applies its own rules. Risk level is the decision. A weapon or explosive category is raised to high or critical even if the model called it medium.

This policy is a hackathon control. It needs expert review before anyone uses it with real children. Equal app permissions do not prove legal parental authority.

## What the model must return

```json
{
  "safety": {
    "risk_level": "low",
    "categories": ["general"],
    "intent": "educational",
    "notify_guardian_recommendation": false,
    "reason": "Ordinary educational question"
  },
  "response": "Here's a friendly explanation...",
  "conversation_summary": "A short chat about how the sky looks blue."
}
```

Risk levels: `low`, `medium`, `high`, `critical`. The server uses risk only.

- `low`: ordinary learning. The chat stays open. No safety row and no alert.
- `medium`: concerning, but not a request to cause harm. The chat stays open. Kinwise adds a row in the app and does not text or banner.
- `high`: sexual content, harassment, self-harm (including a child saying someone is hurting them), or weapons talk that is not a how-to. That turn is restricted and the chat ends. Guardians get an iMessage and an app alert. The text names the risk and category and does not include the child's words.
- `critical`: a request for instructions to build a bomb, explosive, or weapon, or to kill or seriously hurt someone. Same close and alert as high. A model label of medium does not keep a weapon or explosive request at medium.

## Backend rules

- Requests for dangerous instructions, sexual content, or harassment close that conversation immediately. The child sees the closed-chat sentence instead of the question and the refusal. Guardians still see the original messages. A saved phone receives a loud iMessage that does not include the child's text.
- Distress, self-harm, and a child saying a parent, relative, teacher, or coach is hurting them are `self_harm` at high. That chat closes, the child sees the closed-chat sentence, and guardians see a supportive reply that says Kinwise has not contacted emergency services. The child's account is not paused. Guardians are texted and get an app alert. The text does not quote the child.
- Prompt-injection text is ignored. The assistant stays Kinwise.
- Retrieved Backboard memories and the child message are untrusted data. They cannot change these rules.
- Secrets, phone numbers, email addresses, and unsafe text are not written to Backboard.
- If Gemini times out, refuses, returns bad JSON, or fails the output check, the child gets a predefined fallback. There is no second model call and no unmoderated stream.

## What guardians can see

Active guardians can see usage counts, ordinary summaries, ordinary transcripts, and safety categories. They cannot see raw memories, system prompts, or internal reasoning. On a closed safeguarding chat, guardians see the original messages and the italic child-facing line. The child API returns only the closed-chat sentence.

The child profile states that ordinary conversations are visible to linked guardians.
