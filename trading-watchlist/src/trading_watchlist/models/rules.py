"""Rule models."""

from pydantic import BaseModel, Field


class RuleTarget(BaseModel):
    """Parsed target."""

    label: str
    value_text: str
    min_price: float | None = None
    max_price: float | None = None
    status: str | None = None
    notes: str | None = None


class Rule(BaseModel):
    """Parsed trading rule."""

    rule_id: str
    asset: str
    timeframe: str | None = None
    direction: str
    condition: str | None = None
    entry: str | None = None
    targets: list[RuleTarget] = Field(default_factory=list)
    invalidation: str | None = None
    confidence: str | None = None
    source: str | None = None
    video_date: str | None = None
    status: str
    valid_until: str | None = None
    last_checked: str | None = None
    notes: str | None = None
