"""Shared models."""

from pydantic import BaseModel, Field


class PriceSnapshot(BaseModel):
    """Normalized price map."""

    prices: dict[str, float] = Field(default_factory=dict)


class PriceResponse(PriceSnapshot):
    """Normalized prices with lightweight source metadata."""

    sources: dict[str, str] = Field(default_factory=dict)


class EvaluateRequest(BaseModel):
    """Evaluation request."""

    prices: dict[str, float] = Field(default_factory=dict)


class EvaluationSummary(BaseModel):
    """Computed rule state."""

    rule_id: str
    asset: str
    direction: str
    status: str
    current_price: float | None = None
    entry_reference: float | None = None
    invalidation_reference: float | None = None
    nearest_target: float | None = None
    state: str
    distance_to_entry_pct: float | None = None
    distance_to_invalidation_pct: float | None = None
    distance_to_target_pct: float | None = None
    target_progress_pct: float | None = None
    notes: list[str] = Field(default_factory=list)


class EvaluateResponse(BaseModel):
    """Evaluation response."""

    prices: dict[str, float]
    evaluations: list[EvaluationSummary]
