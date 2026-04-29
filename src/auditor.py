"""
The auditor pipeline.

Flow:

    PDPInput
       │
       ▼
   pre-flight: empty content?  ─── yes ──▶ AuditResult(auditable=false, reason="too sparse")
       │ no
       ▼
   build prompt with input + (optional) image
       │
       ▼
   LLM call (vision + JSON)
       │
       ▼
   parse JSON   ─── ParseError ──▶ AuditResult(auditable=false, reason="model returned malformed JSON")
       │ ok
       ▼
   pydantic-validate AuditResult ─── ValidationError ──▶ AuditResult(auditable=false, reason="model output failed schema validation")
       │ ok
       ▼
   post-process: enrich with deterministic taxonomy checks the LLM may have missed
       │
       ▼
   return AuditResult

The post-processing pass is the "engineering on top of a prompt" piece.
LLMs are inconsistent at remembering long required-attribute lists, so
after the LLM returns we deterministically scan the input attributes
against the taxonomy and merge any missing-attribute issues the LLM
forgot. This is conservative — we only ADD issues, never remove them.
"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import ValidationError

from .client import LLMClient, parse_json_strict
from .prompts import AUDIT_SYSTEM
from .schema import (
    AuditIssue,
    AuditResult,
    IssueType,
    PDPInput,
    Severity,
    SuggestedFix,
)
from .taxonomy import get_requirements


class Auditor:
    def __init__(self, client: Optional[LLMClient] = None) -> None:
        self.client = client or LLMClient()

    def audit(self, pdp: PDPInput) -> AuditResult:
        # ----- Pre-flight: cheap deterministic refusals -----
        if not pdp.has_any_content:
            return _refuse(
                pdp.sku,
                "Input has no title, description, or image. Cannot audit.",
                model_used="(no LLM call)",
            )

        # ----- LLM call -----
        user_payload = json.dumps(_pdp_to_user_dict(pdp), ensure_ascii=False, indent=2)

        try:
            resp = self.client.complete(
                system=AUDIT_SYSTEM,
                user=user_payload,
                image_path=pdp.image_path,
                image_url=pdp.image_url,
                json_mode=True,
                temperature=0.2,
            )
        except Exception as e:  # pragma: no cover — network errors at runtime only
            return _refuse(
                pdp.sku,
                f"LLM call failed after retries: {type(e).__name__}",
                model_used="(error)",
            )

        # ----- Parse + validate -----
        try:
            raw = parse_json_strict(resp.text)
        except json.JSONDecodeError as e:
            return _refuse(
                pdp.sku,
                f"Model returned malformed JSON: {e.msg}",
                model_used=resp.model,
            )

        # The LLM may omit model_used / audit_version; we stamp them.
        raw.setdefault("sku", pdp.sku)
        raw["model_used"] = resp.model

        try:
            result = AuditResult.model_validate(raw)
        except ValidationError as e:
            return _refuse(
                pdp.sku,
                f"Model output failed schema validation: {e.errors()[:2]}",
                model_used=resp.model,
            )

        # ----- Post-process: deterministic attribute-gap pass -----
        if result.auditable:
            result = _enrich_with_attribute_gaps(result, pdp)

        return result


# ---------- helpers ----------

def _pdp_to_user_dict(pdp: PDPInput) -> dict:
    """Strip out fields we send via image, keep the rest verbatim."""
    d = pdp.model_dump(exclude={"image_path"})  # image goes via image_url block
    if pdp.image_path and not pdp.image_url:
        d["_image_attached"] = True
    return d


def _enrich_with_attribute_gaps(result: AuditResult, pdp: PDPInput) -> AuditResult:
    """Deterministic safety-net for required attributes the LLM may have skipped.

    We only ADD issues, never remove them. This protects against the most
    common LLM regression on this task: the model gets distracted writing
    Arabic and forgets to scan attributes.
    """
    spec = get_requirements(pdp.category)
    if spec is None:
        return result

    present = {k for k, v in pdp.attributes.items() if v not in (None, "", [])}
    flagged_fields = {i.field for i in result.issues if i.field}

    new_issues: list[AuditIssue] = []
    for required in spec.required_attributes:
        field_id = f"attributes.{required}"
        if required in present:
            continue
        if field_id in flagged_fields:
            continue  # LLM already caught this
        sev = Severity.HIGH if required in spec.safety_attributes else Severity.MEDIUM
        new_issues.append(
            AuditIssue(
                type=IssueType.SAFETY_INFO_MISSING
                if required in spec.safety_attributes
                else IssueType.ATTRIBUTE_GAP,
                severity=sev,
                field=field_id,
                evidence=(
                    f"Required attribute '{required}' for category "
                    f"'{spec.name}' is missing from the listing."
                ),
                confidence=1.0,
            )
        )

    if not new_issues:
        return result

    # Re-build the result with merged issues. Quality score is left
    # unchanged because the LLM already scored holistically — we don't
    # want to double-penalize.
    merged_issues = list(result.issues) + new_issues
    return result.model_copy(update={"issues": merged_issues})


def _refuse(sku: str, reason: str, *, model_used: str) -> AuditResult:
    return AuditResult(
        sku=sku,
        auditable=False,
        refusal_reason=reason,
        quality_score=None,
        score_rationale=None,
        issues=[],
        suggested_fixes=[],
        generated_ar_title=None,
        generated_ar_description=None,
        model_used=model_used,
    )
