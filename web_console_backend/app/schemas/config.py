from typing import Any

from pydantic import BaseModel, Field


class ConfigPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class ConfigValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
