import pytest
from pydantic import ValidationError

from app.ai_review_schemas import Category, Finding, ReviewResult, Severity


def valid_finding(**overrides: object) -> dict[str, object]:
    finding: dict[str, object] = {
        "severity": Severity.HIGH,
        "category": Category.BUG,
        "file": "app/service.py",
        "line": 12,
        "problem": "The error path drops the original exception.",
        "recommendation": "Preserve the original exception when re-raising.",
        "confidence": 0.9,
    }
    finding.update(overrides)
    return finding


def test_valid_finding() -> None:
    finding = Finding(**valid_finding())

    assert finding.severity is Severity.HIGH
    assert finding.category is Category.BUG
    assert finding.line == 12


def test_valid_finding_without_line_number() -> None:
    finding = Finding(**valid_finding(line=None))

    assert finding.line is None


def test_confidence_zero_is_valid() -> None:
    assert Finding(**valid_finding(confidence=0)).confidence == 0


def test_confidence_one_is_valid() -> None:
    assert Finding(**valid_finding(confidence=1)).confidence == 1


def test_multiple_findings() -> None:
    result = ReviewResult(
        findings=[
            valid_finding(),
            valid_finding(severity=Severity.LOW, category=Category.QUALITY),
        ]
    )

    assert len(result.findings) == 2


def test_empty_findings_is_valid() -> None:
    assert ReviewResult(findings=[]).findings == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("severity", "URGENT"),
        ("category", "STYLE"),
        ("confidence", -0.1),
        ("confidence", 1.1),
        ("line", 0),
        ("line", -3),
    ],
)
def test_invalid_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Finding(**valid_finding(**{field: value}))


def test_missing_required_field_is_rejected() -> None:
    finding = valid_finding()
    del finding["problem"]

    with pytest.raises(ValidationError):
        Finding(**finding)


@pytest.mark.parametrize("field", ["file", "problem", "recommendation"])
def test_empty_required_text_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        Finding(**valid_finding(**{field: ""}))


def test_whitespace_only_required_text_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Finding(**valid_finding(file="   "))


def test_unexpected_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Finding(**valid_finding(extra_context="not allowed"))


def test_strict_fields_reject_string_line_and_confidence() -> None:
    with pytest.raises(ValidationError):
        Finding(**valid_finding(line="12"))
    with pytest.raises(ValidationError):
        Finding(**valid_finding(confidence="0.9"))
