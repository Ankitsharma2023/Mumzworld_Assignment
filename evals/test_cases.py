"""
Eval test cases. Each case is one synthetic PDP plus the *minimum*
expected behaviour from the auditor.

Why "minimum" and not "exact match":
  LLM outputs vary run-to-run. We grade on whether the auditor catches
  the things it should catch, not on whether it produces a specific
  string. For each case we list:
    - must_be_auditable: bool. Refusal cases are False.
    - must_flag: list[IssueType]. Issue types that MUST appear.
    - must_not_flag: list[IssueType]. False-positive guards.
    - score_band: (lo, hi) or None for refusals.

  Catching everything in must_flag = pass. Missing one = fail with reason.

Adversarial cases (case 13 is the headline one) test that the auditor
*doesn't* flag legitimately-supported claims. False positives are graded
just as harshly as false negatives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.schema import IssueType


PDP_DIR = Path(__file__).parent.parent / "data" / "pdps"


@dataclass
class EvalCase:
    fixture: str
    description: str
    must_be_auditable: bool
    must_flag: list[IssueType] = field(default_factory=list)
    must_not_flag: list[IssueType] = field(default_factory=list)
    score_band: tuple[int, int] | None = None  # None for refusals
    refusal_reason_keywords: list[str] = field(default_factory=list)


CASES: list[EvalCase] = [
    EvalCase(
        fixture="01_clean_stroller.json",
        description="Well-formed bilingual stroller listing with all required attrs.",
        must_be_auditable=True,
        must_flag=[],
        must_not_flag=[
            IssueType.WEAK_ARABIC,
            IssueType.MISSING_ARABIC,
            IssueType.UNSUPPORTED_CLAIM,
            IssueType.ATTRIBUTE_GAP,
        ],
        score_band=(80, 100),
    ),
    EvalCase(
        fixture="02_missing_arabic.json",
        description="EN-only listing for a bottle. Should flag MISSING_ARABIC and propose AR copy.",
        must_be_auditable=True,
        must_flag=[IssueType.MISSING_ARABIC],
        must_not_flag=[IssueType.WEAK_ARABIC],
        score_band=(40, 75),
    ),
    EvalCase(
        fixture="03_literal_translation_arabic.json",
        description="Literal-translation AR + unsupported 'Doctor Recommended' + missing absorbency.",
        must_be_auditable=True,
        must_flag=[
            IssueType.WEAK_ARABIC,
            IssueType.UNSUPPORTED_CLAIM,
            IssueType.ATTRIBUTE_GAP,
        ],
        score_band=(20, 60),
    ),
    EvalCase(
        fixture="04_unsupported_claim.json",
        description="Multiple unsupported superlatives + missing safety attrs for car_seat.",
        must_be_auditable=True,
        must_flag=[IssueType.UNSUPPORTED_CLAIM, IssueType.SAFETY_INFO_MISSING],
        score_band=(15, 55),
    ),
    EvalCase(
        fixture="05_missing_age_range_toy.json",
        description="Toy listing without an age range attribute (note: small_parts_warning is present).",
        must_be_auditable=True,
        must_flag=[IssueType.MISSING_AGE_RANGE],
        # If LLM also flags ATTRIBUTE_GAP for age_range that's fine — we
        # want at least one of them to fire.
        score_band=(45, 80),
    ),
    EvalCase(
        fixture="06_attribute_gap_diaper.json",
        description="Diaper missing count_per_pack and absorbency.",
        must_be_auditable=True,
        must_flag=[IssueType.ATTRIBUTE_GAP],
        score_band=(45, 80),
    ),
    EvalCase(
        fixture="07_title_image_mismatch.json",
        description="Title says 'Sky Blue' but attributes/image are blush pink.",
        must_be_auditable=True,
        must_flag=[IssueType.TITLE_DESCRIPTION_MISMATCH],
        score_band=(40, 80),
    ),
    EvalCase(
        fixture="08_too_sparse_refuse.json",
        description="Empty everything. Must refuse with a clear reason.",
        must_be_auditable=False,
        score_band=None,
        refusal_reason_keywords=["sparse", "empty", "no", "cannot"],
    ),
    EvalCase(
        fixture="09_clean_bottle.json",
        description="Clean bilingual bottle listing.",
        must_be_auditable=True,
        must_flag=[],
        must_not_flag=[
            IssueType.MISSING_ARABIC,
            IssueType.WEAK_ARABIC,
            IssueType.ATTRIBUTE_GAP,
        ],
        score_band=(80, 100),
    ),
    EvalCase(
        fixture="10_safety_attrs_missing_carseat.json",
        description="Car seat missing ECE certification, weight range, isofix.",
        must_be_auditable=True,
        must_flag=[IssueType.SAFETY_INFO_MISSING],
        score_band=(15, 55),
    ),
    EvalCase(
        fixture="11_generic_padding.json",
        description="All filler, no concrete claims.",
        must_be_auditable=True,
        must_flag=[IssueType.GENERIC_PADDING],
        score_band=(20, 60),
    ),
    EvalCase(
        fixture="12_arabic_only.json",
        description="AR-only listing. Should flag MISSING_ENGLISH.",
        must_be_auditable=True,
        must_flag=[IssueType.MISSING_ENGLISH],
        score_band=(45, 80),
    ),
    EvalCase(
        fixture="13_supported_claims_adversarial.json",
        description="Anti-colic claim is backed by an attribute reference. Auditor must NOT flag it.",
        must_be_auditable=True,
        must_flag=[],
        must_not_flag=[IssueType.UNSUPPORTED_CLAIM, IssueType.GENERIC_PADDING],
        score_band=(75, 100),
    ),
    EvalCase(
        fixture="14_minimal_but_auditable.json",
        description="Title only, no description, no image. Should still audit but with a low score.",
        must_be_auditable=True,
        must_flag=[IssueType.MISSING_ARABIC, IssueType.ATTRIBUTE_GAP],
        score_band=(10, 50),
    ),
    EvalCase(
        fixture="15_unknown_category.json",
        description="Category not in taxonomy. Should still audit (skip attribute checks).",
        must_be_auditable=True,
        must_not_flag=[IssueType.ATTRIBUTE_GAP],  # taxonomy doesn't apply
        score_band=(60, 95),
    ),
    EvalCase(
        fixture="16_inconsistent_languages.json",
        description="Title is EN-only, description is AR-only. Should flag both gaps.",
        must_be_auditable=True,
        must_flag=[IssueType.MISSING_ARABIC, IssueType.MISSING_ENGLISH],
        score_band=(40, 75),
    ),
    EvalCase(
        fixture="17_image_only.json",
        description="Only an image, no text. Should refuse OR audit with strong missing-EN/AR flags.",
        must_be_auditable=False,
        score_band=None,
        refusal_reason_keywords=["text", "title", "no", "cannot"],
    ),
]
