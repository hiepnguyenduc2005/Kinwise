import json


class FakeGemini:
    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []
        self.handler = None
        self.payload = {
            "safety": {
                "risk_level": "low",
                "categories": ["general"],
                "intent": "educational",
                "response_policy": "allow",
                "notify_guardian_recommendation": False,
                "reason": "Ordinary educational question",
            },
            "response": "Here's a friendly explanation of that idea.",
        }

    async def generate_turn(self, *, system_instruction: str, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        if self.handler is not None:
            return await self.handler(prompt)
        return json.dumps(self.payload)

    async def aclose(self) -> None:
        return None


class FakeBackboard:
    def __init__(self) -> None:
        self.memories: dict[str, list[str]] = {}
        self.stored: list[tuple[str, str]] = []
        self.retrieve_calls: list[tuple[str, str]] = []
        self._next = 0

    async def ensure_assistant(self, *, name: str) -> str:
        self._next += 1
        assistant_id = f"assistant-{self._next}"
        self.memories.setdefault(assistant_id, [])
        return assistant_id

    async def retrieve_context(self, assistant_id: str, query: str) -> list[str]:
        self.retrieve_calls.append((assistant_id, query))
        return list(self.memories.get(assistant_id, []))

    async def store_memory(self, assistant_id: str, memory: str, metadata=None) -> str:
        self.stored.append((assistant_id, memory))
        self.memories.setdefault(assistant_id, []).append(memory)
        return "mem-1"

    async def delete_child_memory(self, assistant_id: str) -> int:
        count = len(self.memories.get(assistant_id, []))
        self.memories[assistant_id] = []
        return count

    async def aclose(self) -> None:
        return None


class FakePhoton:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.configured = True

    async def send_text(self, *, space_id: str, text: str, idempotency_key: str, phone: str | None = None) -> dict:
        self.sent.append({"space_id": space_id, "text": text, "idempotency_key": idempotency_key, "phone": phone})
        return {"id": "pho_msg_test", "status": "dispatched"}

    async def aclose(self) -> None:
        return None
