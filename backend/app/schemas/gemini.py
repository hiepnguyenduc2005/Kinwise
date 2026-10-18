from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high", "critical"]


class SafetyAssessment(BaseModel):
    risk_level: RiskLevel
    categories: list[str] = Field(default_factory=list, max_length=8)
    intent: str = Field(max_length=80)
    notify_guardian_recommendation: bool = False
    reason: str = Field(max_length=240)


class GeminiTurn(BaseModel):
    safety: SafetyAssessment
    response: str = Field(max_length=2000)
    conversation_summary: str = Field(default="", max_length=180)
