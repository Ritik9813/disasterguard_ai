"""Pydantic schemas for structured (JSON) Gemini output."""
from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["Low", "Moderate", "High", "Very High"]


class AlertPack(BaseModel):
    severity: Literal["Advisory", "Watch", "Warning", "Emergency"]
    headline: str = Field(description="At most 8 words, e.g. 'Heavy Rainfall & Flood Risk'")
    area: str = Field(description="Affected city and state")
    hazard: str
    expected: str = Field(description="One sentence: what is expected and when")
    risk_level: Level
    safety_instructions: list[str] = Field(description="4 to 6 short imperative actions")
    push_notification: str = Field(description="At most 120 characters")
    sms: str = Field(description="At most 160 characters, plain text, include helpline 112")
    whatsapp: str = Field(description="Friendly message with a few emojis and helpline numbers")
    siren_pattern: str = Field(description="Siren pattern and what it means, one or two sentences")
    tv_radio_script: str = Field(description="Broadcast script, at most 60 words")


class DamageAssessment(BaseModel):
    scene_type: str = Field(description="What the image shows, e.g. flooded street, collapsed building")
    damage_level: Literal["None", "Minor", "Moderate", "Severe", "Catastrophic"]
    hazards_visible: list[str] = Field(description="Dangers visible: deep water, live wires, cracks...")
    infrastructure_impacted: list[str]
    people_or_assets_at_risk: str
    immediate_actions: list[str] = Field(description="3 to 5 prioritised actions for responders")
    confidence: Literal["Low", "Medium", "High"]
    limitations: str = Field(description="What cannot be judged from a single photo")


class ReportTriage(BaseModel):
    category: Literal["Flooding", "Landslide", "Building damage", "Road blocked", "Medical need",
                      "Trapped people", "Supplies needed", "Fire", "Other"]
    urgency: Literal["Low", "Medium", "High", "Critical"]
    credibility: Literal["Low", "Medium", "High"]
    summary: str = Field(description="One sentence summary")
    recommended_action: str
    needs_verification: bool
