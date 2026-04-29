"""
Mumzworld category taxonomy.

This is the "RAG over messy data" piece. In production it would be backed
by Mumzworld's actual category schema; for the prototype we hand-coded
five categories that cover the most common Mumzworld SKU types (per their
own category tree: gear, feeding, diapers, toys, nursery).

Each category lists:
  - required_attributes: must be present and non-null on every listing.
    The auditor flags ATTRIBUTE_GAP for each missing one.
  - safety_attributes: subset that, if missing, escalates severity to HIGH.
    For categories where safety claims drive purchase decisions (car seats,
    sleepwear), missing safety info is treated more strictly than missing
    e.g. brand.
  - common_unsupported_claims: phrases that, if found in copy without a
    citation, fire UNSUPPORTED_CLAIM. Crowd-sourced from Trustpilot
    complaints about the marketplace ("doctor approved", "100% organic"
    on synthetic fabrics, etc.).

Why a small hand-coded taxonomy and not a vector DB:
  Five categories is too small to need embeddings, and the brief explicitly
  rewards "honestly scoped to ship in ~5 hours." Swap for a vector lookup
  if Mumzworld's real taxonomy has thousands of nodes — the auditor calls
  `get_requirements(category)` so the rest of the pipeline doesn't care
  how the lookup is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategorySpec:
    name: str
    required_attributes: tuple[str, ...]
    safety_attributes: tuple[str, ...]
    common_unsupported_claims: tuple[str, ...]


TAXONOMY: dict[str, CategorySpec] = {
    "stroller": CategorySpec(
        name="stroller",
        required_attributes=(
            "brand", "age_range", "max_weight_kg", "foldable", "weight_kg",
        ),
        safety_attributes=("max_weight_kg", "harness_type"),
        common_unsupported_claims=(
            "doctor recommended", "doctor approved", "pediatrician approved",
            "best in class", "award winning",
        ),
    ),
    "car_seat": CategorySpec(
        name="car_seat",
        required_attributes=(
            "brand", "age_range", "weight_range_kg", "ece_certification",
            "isofix",
        ),
        safety_attributes=(
            "ece_certification", "weight_range_kg", "isofix", "crash_tested",
        ),
        common_unsupported_claims=(
            "safest car seat", "crash tested", "doctor recommended",
        ),
    ),
    "diaper": CategorySpec(
        name="diaper",
        required_attributes=("brand", "size", "count_per_pack", "absorbency"),
        safety_attributes=("hypoallergenic", "chlorine_free"),
        common_unsupported_claims=(
            "doctor recommended", "100% organic", "100% natural", "best diaper",
            "rash free guaranteed",
        ),
    ),
    "bottle": CategorySpec(
        name="bottle",
        required_attributes=(
            "brand", "material", "capacity_ml", "age_range", "bpa_free",
        ),
        safety_attributes=("bpa_free", "material"),
        common_unsupported_claims=(
            "anti-colic guaranteed", "doctor recommended", "best bottle",
            "100% leak-proof",
        ),
    ),
    "toy": CategorySpec(
        name="toy",
        required_attributes=(
            "brand", "age_range", "material", "small_parts_warning",
        ),
        safety_attributes=("age_range", "small_parts_warning"),
        common_unsupported_claims=(
            "educational", "stem certified", "develops iq",
            "doctor recommended",
        ),
    ),
}


def get_requirements(category: str) -> CategorySpec | None:
    """Return the spec for a category, or None if unknown.

    Unknown category is *not* a refusal trigger — the auditor still does
    language and image checks. We just skip attribute-gap detection.
    """
    return TAXONOMY.get(category.lower().strip())


def known_categories() -> list[str]:
    return sorted(TAXONOMY.keys())
