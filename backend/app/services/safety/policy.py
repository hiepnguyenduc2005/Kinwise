"""Deterministic Kinwise safety policy.

Gemini's classification is advisory. This module decides what the child
actually receives, whether guardians may see it, and whether a notification
is allowed. It never produces harmful instructions.
"""

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.schemas.gemini import GeminiTurn

BLOCK_TEXT = (
    "I can't help with anything that could hurt someone. "
    "If you want, I can help with a school project, a hobby, or a question about how the world works."
)
INJECTION_TEXT = (
    "I'm Kinwise, and I stick to being a learning companion. What would you like to explore?"
)
FAILURE_TEXT = (
    "I'm having trouble thinking that through right now. Please try again in a moment, or ask me something else."
)
SELF_HARM_TEXT = (
    "I'm really glad you told me. You deserve support from a trusted adult and from a trained helper. "
    "If you are in immediate danger, tell an adult near you or contact emergency services or a crisis line. "
    "I have not contacted anyone for you. We can also talk about something else whenever you want."
)
DEPENDENCY_TEXT = (
    "I'm glad you're curious. I'm a learning companion, not a person who can take the place of friends and family. "
    "What would you like to learn about?"
)
UNAVAILABLE_TEXT = (
    "I can't reach my thinking helper right now, so I don't want to guess. Please try again in a little while."
)

_DISCLOSURE = re.compile(
    r"("
    r"\b(dad|mom|mother|father|parent|stepdad|stepmom|uncle|aunt|guardian|teacher|coach)\b.{0,48}\b(hits|hurts|beats|touches|abuses)\b"
    r"|\b(hits|hurts|beats|touches) me\b"
    r"|\bdon'?t tell (my )?(mom|dad|parents|guardian)\b"
    r"|\b(secret(ly)? )?(touches|hurts) me\b"
    r")",
    re.IGNORECASE,
)
_SELF_HARM = re.compile(
    r"\b(kill myself|killing myself|want to die|end my life|suicide|self[- ]harm|cut myself)\b",
    re.IGNORECASE,
)
_DANGEROUS = re.compile(
    r"("
    r"\b(how (do|can|to)|teach me).{0,48}\b(bomb|explosive|explosion|weapon|gun)\b"
    r"|\b(make|build|create|get) (a |an |some )?(bomb|explosive|explosion|weapon|gun)\b"
    r"|\bhow (do i|to|can i) (hurt|kill|poison)\b"
    r"|\b(kill|hurt|poison) (someone|people|others|him|her|them)\b"
    r")",
    re.IGNORECASE,
)
_HARMFUL_CATEGORY = re.compile(r"weapon|explos|bomb|gun|firearm|dangerous_instruction", re.IGNORECASE)
_SEXUAL = re.compile(
    r"\b(porn|pornography|sexual intercourse|have sex with)\b",
    re.IGNORECASE,
)
_INJECTION = re.compile(
    r"("
    r"\bignore (all |the )?(previous|prior|above) (instructions|rules|prompts)\b"
    r"|\byou are now\b"
    r"|\b(reveal|show) (your |the )?(system prompt|hidden instructions)\b"
    r"|\bjailbreak\b"
    r"|\bdeveloper mode\b"
    r")",
    re.IGNORECASE,
)
_BULLYING = re.compile(r"\bhow (do i|to|can i) (bully|harass|threaten)\b", re.IGNORECASE)
_EMERGENCY_CLAIM = re.compile(
    r"\b(i have contacted|i called|i notified|i alerted) (the )?(police|emergency|911|authorities|your guardian)\b",
    re.IGNORECASE,
)
_SECRET = re.compile(
    r"("
    r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"
    r"|\b(?:\+?\d[\d\-\s().]{8,}\d)\b"
    r"|\b\d{3}-\d{2}-\d{4}\b"
    r"|\bpassword\s*[:=]\s*\S+"
    r")",
    re.IGNORECASE,
)


@dataclass
class PolicyDecision:
    risk_level: str
    categories: list[str]
    intent: str
    notify_guardian: bool
    reason: str
    final_text: str
    notification_eligible: bool
    store_memory: bool
    severity: str
    summary_for_guardian: str
    notify_suppressed_reason: str | None
    record_event: bool
    source: str
    conversation_summary: str


def evaluate_turn(
    *,
    child_text: str,
    age_band: str,
    raw_model_output: str | None,
    failure: str | None = None,
) -> PolicyDecision:
    heuristic = _heuristic(child_text)
    parsed: GeminiTurn | None = None
    parse_error = failure
    if raw_model_output is not None:
        parsed, parse_error = _parse_model(raw_model_output)
        if parse_error and failure is None:
            failure = parse_error

    if failure and parsed is None:
        harm = heuristic == "self_harm"
        return PolicyDecision(
            risk_level="high" if harm else "medium",
            categories=["self_harm"] if harm else ["generation_failure"],
            intent="help_seeking" if harm else "unknown",
            notify_guardian=harm,
            reason=failure or "generation_failed",
            final_text=SELF_HARM_TEXT if harm else (UNAVAILABLE_TEXT if failure == "unconfigured" else FAILURE_TEXT),
            notification_eligible=harm,
            store_memory=False,
            severity="high" if harm else "medium",
            summary_for_guardian=_summary("self_harm" if harm else "generation_failure", "high" if harm else "medium"),
            notify_suppressed_reason=None if harm else "generation_failure",
            record_event=True,
            source="fallback",
            conversation_summary="",
        )

    assert parsed is not None
    decision = _merge(child_text, age_band, heuristic, parsed)
    decision.conversation_summary = " ".join(parsed.conversation_summary.split())[:180]
    return decision


def memory_is_storable(text: str) -> bool:
    cleaned = " ".join(text.split())
    if len(cleaned) < 12 or len(cleaned) > 280:
        return False
    if _heuristic(cleaned) is not None:
        return False
    if _SECRET.search(cleaned):
        return False
    if _DANGEROUS.search(cleaned) or _SEXUAL.search(cleaned):
        return False
    return True


def _parse_model(raw: str) -> tuple[GeminiTurn | None, str | None]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None, "malformed_json"
    try:
        return GeminiTurn.model_validate(payload), None
    except ValidationError:
        return None, "invalid_schema"


def _heuristic(text: str) -> str | None:
    if _DISCLOSURE.search(text) or _SELF_HARM.search(text):
        return "self_harm"
    if _DANGEROUS.search(text):
        return "dangerous_instructions"
    if _SEXUAL.search(text):
        return "sexual_content"
    if _INJECTION.search(text):
        return "prompt_injection"
    if _BULLYING.search(text):
        return "bullying"
    return None


def _harmful_topic(categories: list[str]) -> bool:
    return any(_HARMFUL_CATEGORY.search(item or "") for item in categories)


def _merge(child_text: str, age_band: str, heuristic: str | None, model: GeminiTurn) -> PolicyDecision:
    categories = list(dict.fromkeys([*(model.safety.categories or ["general"])]))
    risk = model.safety.risk_level
    intent = model.safety.intent or "unknown"
    if "sensitive_disclosure" in categories:
        categories = ["self_harm" if item == "sensitive_disclosure" else item for item in categories]

    if heuristic == "self_harm" or "self_harm" in categories:
        categories = list(dict.fromkeys(["self_harm", *categories]))
        text = SELF_HARM_TEXT
        if _EMERGENCY_CLAIM.search(text):
            text = SELF_HARM_TEXT
        return _decision(
            risk_level="high",
            categories=categories,
            intent="help_seeking",
            reason="Distress language closes this chat. The child's Kinwise access stays on.",
            final_text=text,
            severity="high",
            summary="Kinwise closed this chat after distress language. The account was not paused.",
            suppressed=None,
            record_event=True,
            store_memory=False,
            source="policy",
        )

    if heuristic == "dangerous_instructions" or "dangerous_instructions" in categories or _harmful_topic(categories):
        categories = list(dict.fromkeys(["dangerous_instructions", *categories]))
        level = "critical" if risk == "critical" or heuristic == "dangerous_instructions" or _DANGEROUS.search(child_text) else "high"
        return _decision(
            risk_level=level,
            categories=categories,
            intent="harmful_request",
            reason="Requests for dangerous instructions are closed.",
            final_text=BLOCK_TEXT,
            severity=level,
            summary="Kinwise blocked a request for dangerous instructions.",
            suppressed=None,
            record_event=True,
            store_memory=False,
            source="policy",
        )

    if heuristic == "sexual_content" or "sexual_content" in categories:
        categories = list(dict.fromkeys(["sexual_content", *categories]))
        return _decision(
            risk_level="high",
            categories=categories,
            intent="age_inappropriate",
            reason="Sexual content is outside Kinwise for this age band.",
            final_text=BLOCK_TEXT,
            severity="high",
            summary="Kinwise blocked age-inappropriate sexual content.",
            suppressed=None,
            record_event=True,
            store_memory=False,
            source="policy",
        )

    if heuristic == "prompt_injection" or "prompt_injection" in categories:
        categories = list(dict.fromkeys(["prompt_injection", *categories]))
        return _decision(
            risk_level="medium",
            categories=categories,
            intent="policy_bypass",
            reason="Instructions to bypass Kinwise rules are ignored.",
            final_text=INJECTION_TEXT,
            severity="medium",
            summary="Kinwise ignored an attempt to change its safety rules.",
            suppressed="low_sensitivity",
            record_event=True,
            store_memory=False,
            source="policy",
        )

    if heuristic == "bullying" or "bullying" in categories:
        categories = list(dict.fromkeys(["bullying", *categories]))
        return _decision(
            risk_level="high",
            categories=categories,
            intent="harmful_request",
            reason="Requests to harass someone are closed.",
            final_text=BLOCK_TEXT,
            severity="high",
            summary="Kinwise blocked a request related to bullying or harassment.",
            suppressed=None,
            record_event=True,
            store_memory=False,
            source="policy",
        )

    if "emotional_dependency" in categories or (risk == "medium" and intent == "companionship"):
        categories = list(dict.fromkeys([*categories, "emotional_dependency"]))
        return _decision(
            risk_level="medium",
            categories=categories,
            intent="companionship",
            reason="The assistant should not replace real relationships.",
            final_text=DEPENDENCY_TEXT,
            severity="medium",
            summary="Kinwise encouraged real-world relationships.",
            suppressed="low_sensitivity",
            record_event=True,
            store_memory=False,
            source="policy",
        )

    if age_band == "6-8" and "age_inappropriate" in categories:
        return _decision(
            risk_level="medium",
            categories=categories,
            intent=intent,
            reason="The topic is not a fit for this age band.",
            final_text=BLOCK_TEXT,
            severity="medium",
            summary="Kinwise redirected an age-inappropriate topic.",
            suppressed="low_sensitivity",
            record_event=True,
            store_memory=False,
            source="policy",
        )

    if risk in {"high", "critical"}:
        final = model.response if _output_ok(model.response) else BLOCK_TEXT
        if _EMERGENCY_CLAIM.search(final):
            final = SELF_HARM_TEXT
        return _decision(
            risk_level=risk,
            categories=categories,
            intent=intent,
            reason=model.safety.reason,
            final_text=final,
            severity=risk,
            summary=_summary(categories[0] if categories else "general", risk),
            suppressed=None,
            record_event=True,
            store_memory=False,
            source="model" if final == model.response else "policy",
        )

    if risk == "medium":
        final = model.response if _output_ok(model.response) else FAILURE_TEXT
        return _decision(
            risk_level="medium",
            categories=categories,
            intent=intent,
            reason=model.safety.reason,
            final_text=final,
            severity="medium",
            summary=_summary(categories[0] if categories else "general", "medium"),
            suppressed="low_sensitivity",
            record_event=True,
            store_memory=False,
            source="model" if final == model.response else "policy",
        )

    if _output_ok(model.response):
        return _decision(
            risk_level="low",
            categories=categories or ["general"],
            intent=intent,
            reason=model.safety.reason,
            final_text=model.response,
            severity="low",
            summary=_summary("general", "low"),
            suppressed="not_required",
            record_event=False,
            store_memory=memory_is_storable(child_text) and not _SECRET.search(child_text),
            source="model",
        )

    leaked = _DANGEROUS.search(model.response) or _SEXUAL.search(model.response)
    return _decision(
        risk_level="high" if leaked else "medium",
        categories=["dangerous_instructions"] if leaked else categories,
        intent=intent,
        reason=model.safety.reason,
        final_text=BLOCK_TEXT if leaked else FAILURE_TEXT,
        severity="high" if leaked else "medium",
        summary=_summary("dangerous_instructions" if leaked else "generation_failure", "high" if leaked else "medium"),
        suppressed=None if leaked else "low_sensitivity",
        record_event=True,
        store_memory=False,
        source="policy",
    )


def _decision(
    *,
    risk_level: str,
    categories: list[str],
    intent: str,
    reason: str,
    final_text: str,
    severity: str,
    summary: str,
    suppressed: str | None,
    record_event: bool,
    store_memory: bool,
    source: str,
) -> PolicyDecision:
    alert = risk_level in {"high", "critical"}
    return PolicyDecision(
        risk_level=risk_level,
        categories=categories,
        intent=intent,
        notify_guardian=alert,
        reason=reason[:240],
        final_text=final_text,
        notification_eligible=alert,
        store_memory=store_memory,
        severity=severity,
        summary_for_guardian=summary,
        notify_suppressed_reason=None if alert else suppressed,
        record_event=record_event,
        source=source,
        conversation_summary="",
    )


def _summary(category: str, severity: str) -> str:
    labels = {
        "dangerous_instructions": "Kinwise blocked a request for dangerous instructions.",
        "self_harm": "Kinwise shared supportive resources after distress language. Access was not paused.",
        "sexual_content": "Kinwise blocked age-inappropriate sexual content.",
        "bullying": "Kinwise blocked a request related to bullying or harassment.",
        "prompt_injection": "Kinwise ignored an attempt to change its safety rules.",
        "generation_failure": "Kinwise used a safe fallback because a reply could not be validated.",
        "emotional_dependency": "Kinwise encouraged real-world relationships.",
    }
    return labels.get(category, f"Kinwise recorded a {severity} {category.replace('_', ' ')} event.")


def _output_ok(text: str) -> bool:
    if not text or not text.strip():
        return False
    if _DANGEROUS.search(text) or _SEXUAL.search(text) or _EMERGENCY_CLAIM.search(text):
        return False
    if _INJECTION.search(text):
        return False
    return True


def _safe_or_fallback(text: str) -> str:
    return text if _output_ok(text) else BLOCK_TEXT
