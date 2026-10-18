import asyncio
import logging

from app.schemas.gemini import GeminiTurn

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class GoogleGeminiClient:
    """One generateContent call per generate_turn invocation.

    Uses the Google Gen AI SDK structured-output config:
    response_mime_type=application/json and response_schema=GeminiTurn.
    """

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 12.0) -> None:
        self.calls = 0
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._client = None

    def _sdk(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def generate_turn(self, *, system_instruction: str, prompt: str) -> str:
        if not self._api_key:
            raise GeminiError("unconfigured")
        self.calls += 1
        from google.genai import types

        try:
            response = await asyncio.wait_for(
                self._sdk().aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=GeminiTurn,
                        max_output_tokens=800,
                    ),
                ),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            raise GeminiError("timeout") from exc
        except GeminiError:
            raise
        except Exception as exc:
            logger.warning("gemini generation failed: %s", type(exc).__name__)
            raise GeminiError("provider_error") from exc

        feedback = getattr(response, "prompt_feedback", None)
        block = getattr(feedback, "block_reason", None) if feedback else None
        if block:
            raise GeminiError("safety_filter")
        text = getattr(response, "text", None)
        if not text:
            raise GeminiError("incomplete")
        return text
