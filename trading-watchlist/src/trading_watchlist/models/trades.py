"""Position models."""

from pydantic import BaseModel, Field


class PositionTarget(BaseModel):
    """Parsed position target."""

    label: str
    price_text: str
    status: str | None = None
    notes: str | None = None


class Position(BaseModel):
    """Parsed position or pending setup."""

    title: str
    rule_id: str
    section: str
    direction: str | None = None
    asset: str | None = None
    status: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    targets: list[PositionTarget] = Field(default_factory=list)
