from pydantic import BaseModel, Field


class NarrativeOutput(BaseModel):
    R_narr: float = Field(..., ge=-1.0, le=1.0, description="Direction from panic to euphoria")
    omega_narr: float = Field(..., ge=0.0, le=1.0, description="Uncertainty and agent disagreement")
    dominant_theme: str
    confidence: float = Field(..., ge=0.0, le=1.0, description="Current narrative confidence, not historical accuracy")
    sources_used: int = Field(..., ge=0)
    reasoning: str = Field(..., max_length=1000)
    evidence: list[str] = Field(default_factory=list)
    account_implications: list[str] = Field(default_factory=list)
    alternative_scenario: str = ""
    invalidation_conditions: list[str] = Field(default_factory=list)
