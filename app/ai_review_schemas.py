from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Category(str, Enum):
    SECURITY = "SECURITY"
    BUG = "BUG"
    PERFORMANCE = "PERFORMANCE"
    MAINTAINABILITY = "MAINTAINABILITY"
    QUALITY = "QUALITY"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    severity: Severity
    category: Category
    file: str = Field(min_length=1)
    line: int | None = Field(default=None, gt=0)
    problem: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @field_validator("file", "problem", "recommendation")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    findings: list[Finding]
