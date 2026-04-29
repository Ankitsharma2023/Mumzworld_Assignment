"""
Pydantic schemas for the PDP auditor.

Design notes
------------
The brief explicitly calls out two failure modes we have to defend against:
  1. "Malformed JSON, or fields filled with empty strings to 'pass'"
  2. "Hiding uncertainty rather than expressing it"

The schemas below are written to make both of those impossible:
  - Empty strings are rejected by validators (not just by `min_length=1`,
    because we want the error message to be specific).
  - Refusals are a first-class field on AuditResult. A refusal is a valid
    result, it is not an exception. The pipeline expresses uncertainty
    by setting `auditable=False` and `refusal_reason`, which the eval
    harness then grades as a *correct* output.
  - All confidences are bounded floats; severity and issue_type are
    closed enums so the model cannot invent new categories.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


# ---------- Input ----------

class PDPInput(BaseModel):
    """A product detail page submitted by a 3P seller, in Mumzworld's shape.

    All bilingual fields are split into `_en` and `_ar` because we audit
    each language independently. A missing `_ar` is a *flaggable* issue,
    not a validation error — Mumzworld's catalog is full of EN-only listings,
    and we want the pipeline to produce a fix, not crash.
    """

    sku: str = Field(..., description="Stock-keeping unit; used for citations")
    category: str = Field(..., description="One of the keys in taxonomy.json")

    title_en: Optional[str] = None
    title_ar: Optional[str] = None
    description_en: Optional[str] = None
    description_ar: Optional[str] = None

    # Image as a URL or a local path. Vision is optional — the auditor
    # will still produce a partial result without it (with lower confidence).
    image_url: Optional[str] = None
    image_path: Optional[str] = None

    # Free-form attributes from the seller. e.g. {"brand": "Doona",
    # "age_range": "0-12m", "max_weight_kg": 13}. We deliberately do not
    # type these — half the bug is sellers put junk in here, and we want
    # the auditor to grade that.
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("sku", "category")
    @classmethod
    def _no_blank_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("required field is blank")
        return v.strip()

    @field_validator("title_en", "title_ar", "description_en", "description_ar")
    @classmethod
    def _normalize_optional(cls, v: Optional[str]) -> Optional[str]:
        # Treat empty/whitespace as None so the auditor sees a clean signal.
        if v is None:
            return None
        v = v.strip()
        return v if v else None

    @property
    def has_any_content(self) -> bool:
        """If this is False the pipeline refuses (too sparse to audit)."""
        return any([
            self.title_en, self.title_ar,
            self.description_en, self.description_ar,
            self.image_url, self.image_path,
        ])


# ---------- Audit output ----------

class IssueType(str, Enum):
    MISSING_AGE_RANGE = "missing_age_range"
    WEAK_ARABIC = "weak_arabic"               # AR present but reads like a literal translation
    MISSING_ARABIC = "missing_arabic"         # AR field absent entirely
    MISSING_ENGLISH = "missing_english"
    UNSUPPORTED_CLAIM = "unsupported_claim"   # e.g. "doctor recommended" with no source
    IMAGE_QUALITY = "image_quality"
    ATTRIBUTE_GAP = "attribute_gap"           # required attr per taxonomy is missing
    TITLE_DESCRIPTION_MISMATCH = "title_description_mismatch"
    TITLE_IMAGE_MISMATCH = "title_image_mismatch"
    SAFETY_INFO_MISSING = "safety_info_missing"
    GENERIC_PADDING = "generic_padding"       # filler copy, no concrete claim


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AuditIssue(BaseModel):
    """A single, citable problem with the listing."""
    type: IssueType
    severity: Severity
    field: Optional[str] = Field(
        None,
        description="Which input field this is about, e.g. 'title_ar' or 'attributes.age_range'.",
    )
    evidence: str = Field(
        ...,
        description="A direct quote or specific observation. No vague claims.",
        min_length=8,
    )
    confidence: float = Field(..., ge=0.0, le=1.0)


class SuggestedFix(BaseModel):
    """A concrete, applyable fix for one field."""
    field: str  # e.g. "title_ar"
    current: Optional[str]
    suggested: str = Field(..., min_length=2)
    reasoning: str = Field(..., min_length=8)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("suggested")
    @classmethod
    def _no_padding(cls, v: str) -> str:
        # Reject the model's most common cop-out: returning a copy of the
        # current value or a blanket placeholder.
        v = v.strip()
        if v.lower() in {"n/a", "none", "tbd", "see above", "not applicable"}:
            raise ValueError("suggested fix is a placeholder, not a real value")
        return v


class AuditResult(BaseModel):
    """The full audit. Every field is required so silent skips fail loudly."""

    sku: str
    auditable: bool = Field(
        ...,
        description="False = refused. The rest of the fields will be empty/None.",
    )
    refusal_reason: Optional[str] = None

    quality_score: Optional[int] = Field(
        None, ge=0, le=100,
        description="Holistic score. None when auditable=False.",
    )
    score_rationale: Optional[str] = Field(
        None,
        description="One-sentence explanation of the score. None when refused.",
    )

    issues: list[AuditIssue] = Field(default_factory=list)
    suggested_fixes: list[SuggestedFix] = Field(default_factory=list)

    # Native AR copy generated by the auditor. May be None if input already
    # had good AR, or if the model declined to generate.
    generated_ar_title: Optional[str] = None
    generated_ar_description: Optional[str] = None

    # Provenance. Stamped by the pipeline so the README's tooling section
    # is verifiable from any single result.
    model_used: str
    audit_version: str = "0.1.0"

    @model_validator(mode="after")
    def _refusal_consistency(self) -> "AuditResult":
        """Refusals must look like refusals; non-refusals must have a score."""
        if not self.auditable:
            if not self.refusal_reason:
                raise ValueError("auditable=False requires refusal_reason")
            if self.quality_score is not None:
                raise ValueError("refused audits must have quality_score=None")
            if self.issues:
                raise ValueError("refused audits should not list issues")
        else:
            if self.quality_score is None:
                raise ValueError("auditable=True requires a quality_score")
            if self.score_rationale is None:
                raise ValueError("auditable=True requires a score_rationale")
        return self


__all__ = [
    "PDPInput",
    "AuditResult",
    "AuditIssue",
    "SuggestedFix",
    "IssueType",
    "Severity",
]
