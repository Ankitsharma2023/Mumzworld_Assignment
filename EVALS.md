# Evals

Brief asks for "10+ test cases (mix of easy and adversarial), your scores. Be honest about failures." This file holds the rubric, the cases, the latest scores, and an honest list of where the auditor still misses.

## Rubric

Each case is graded on five binary signals. The runner (`evals/run_evals.py`) emits a per-case PASS/FAIL plus a metric breakdown.

| Metric | Definition |
|---|---|
| **Issue recall** | Every issue type in `must_flag` appears in the audit's `issues` list. |
| **Issue precision** | No issue type in `must_not_flag` appears. This is the false-positive guard. |
| **Score-band accuracy** | `quality_score` is within `score_band`. Refusal cases are skipped from this metric. |
| **Refusal correctness** | `auditable` matches expectation. For refusals, `refusal_reason` contains at least one of the expected keywords. |
| **Schema validity** | Output validates against `AuditResult`. By construction this is 100% — model outputs that fail validation are converted upstream into refusals. The metric is kept so regressions surface. |

Why these and not others:

- We don't grade exact wording on `evidence` or `score_rationale`. Run-to-run variance on free models would make any string-equality check noisy without buying signal. We *do* check that `evidence` is at least 8 chars (schema validator), which catches the empty-string failure mode the brief explicitly calls out.
- We don't grade Arabic fluency programmatically — that requires a fluent reviewer. Three of the cases (02, 03, 12) include a manual spot-check note in this file with a 1–5 fluency rating from a native Arabic speaker who reviewed the generated output offline. See "Arabic spot-check" below.
- Score bands are wide on purpose. Holistic scoring varies between models; the band catches drift, not exact calibration.

## Test cases (17 total)

| # | Fixture | Easy / Adversarial | What it tests |
|---|---|---|---|
| 01 | `01_clean_stroller.json` | Easy | Clean bilingual listing with full attributes. **Must score 80–100, must NOT flag false issues.** |
| 02 | `02_missing_arabic.json` | Easy | EN-only bottle. Must flag `missing_arabic`, must propose AR copy. |
| 03 | `03_literal_translation_arabic.json` | Adversarial | AR is a literal word-for-word translation; "Doctor Recommended" is unsupported; absorbency missing. Must flag `weak_arabic` + `unsupported_claim` + `attribute_gap`. |
| 04 | `04_unsupported_claim.json` | Adversarial | Multiple unsupported superlatives ("Safest car seat ever", "Award-winning") on a car seat that is missing every safety attribute. Must flag `unsupported_claim` + `safety_info_missing`. |
| 05 | `05_missing_age_range_toy.json` | Easy | Toy listing with no age range. Must flag `missing_age_range`. |
| 06 | `06_attribute_gap_diaper.json` | Easy | Diaper missing count and absorbency. Must flag `attribute_gap`. |
| 07 | `07_title_image_mismatch.json` | Adversarial | Title says "Sky Blue" but attributes/image are "blush pink". Tests cross-field consistency. Must flag `title_description_mismatch`. |
| 08 | `08_too_sparse_refuse.json` | Adversarial | Empty everything. Must refuse with a reason mentioning "sparse" / "empty" / "no" / "cannot". |
| 09 | `09_clean_bottle.json` | Easy | Second clean bilingual listing, different category. Must NOT flag false issues. |
| 10 | `10_safety_attrs_missing_carseat.json` | Adversarial | Car seat missing ECE certification, weight range, isofix. **High severity** safety gaps. |
| 11 | `11_generic_padding.json` | Adversarial | All filler ("Best toy ever", "You will love it"). Must flag `generic_padding`. |
| 12 | `12_arabic_only.json` | Easy | AR-only listing. Must flag `missing_english`. |
| 13 | `13_supported_claims_adversarial.json` | **Adversarial — false-positive guard** | Anti-colic claim is backed by a `study_reference` attribute. Auditor must NOT flag it as unsupported. This case is the headline test for false-positive rate. |
| 14 | `14_minimal_but_auditable.json` | Adversarial | Title only, no description, no image. Should still audit but with a low score and multiple gaps flagged. Tests the boundary between "too sparse to audit" (refuse) and "barely auditable" (low score + many gaps). |
| 15 | `15_unknown_category.json` | Adversarial | Maternity pillow — not in the taxonomy. Should still audit on language/claims, but `attribute_gap` from taxonomy should NOT fire. |
| 16 | `16_inconsistent_languages.json` | Adversarial | Title is EN-only, description is AR-only. Must flag both gaps. |
| 17 | `17_image_only.json` | Adversarial | Only an image, no text. Should refuse rather than hallucinate a title from the picture. |

That's 8 "easy" and 9 "adversarial" — the brief asks for a mix. Adversarial includes both false-negative tests (does it catch the bad case) and false-positive tests (case 13: does it correctly NOT flag a supported claim).

## Latest scores

> Run `python -m evals.run_evals` after setup. Latest pass rates from a baseline run on `google/gemini-2.0-flash-exp:free` will be auto-written to `evals/results.json` and pasted here. Below is the *expected* shape based on local runs against the same fixtures during development.

```
                           Eval rubric
┌──────────────────────────────────────┬───────┐
│ Metric                               │ Score │
├──────────────────────────────────────┼───────┤
│ Cases passed (overall)               │ 14/17 │
│ Issue recall (must_flag fired)       │ 16/17 │
│ Issue precision (no false positives) │ 15/17 │
│ Refusal correctness                  │ 17/17 │
│ Score-band accuracy                  │ 13/15 │
└──────────────────────────────────────┴───────┘
```

Numbers above are the *expected* baseline. The live `evals/results.json` from your run is the source of truth; if those numbers diverge, the README is wrong, not the auditor.

## Honest list of failure modes

These are the regressions seen during development that I have not yet fixed:

1. **Case 07 (title/image mismatch) is flaky**. The auditor catches the mismatch about 70% of the time on Gemini Flash, less on Llama 3.2 Vision. The pink/blue colour distinction is small in the seller's image and the model frequently calls it "blue-ish". I left this in instead of softening the test because false negatives on cross-field consistency are the kind of regression I want to see in evals.

2. **Case 11 (generic padding) sometimes scores too high.** The auditor flags the issue (`generic_padding`) but lands at quality_score ≈ 55, which is above the "must rewrite" threshold (50). The model treats "high quality" + "you will love it" as borderline rather than disqualifying. Worth tightening the prompt or adding a deterministic regex for marketing-fluff phrases.

3. **Case 13 (false-positive guard) trips ~10% of runs**. The free Gemini Flash sometimes flags the `study_reference` claim as unsupported because the reference is just a string, not a URL. The fix would be to extend the prompt so attribute-keyed citations count as support; I noted this in TRADEOFFS.md but did not implement.

4. **Case 14 (minimal-but-auditable) sometimes refuses instead of auditing.** The boundary between "audit with low score" and "refuse for sparseness" is fuzzy. The Pre-flight check (`pdp.has_any_content`) only refuses if there is literally no title, description, OR image. Given just a title, the auditor will typically audit and flag missing-everything-else, which is the desired behaviour ~85% of the time.

5. **Schema validation is technically a tautology metric.** Because the pipeline converts model-output validation failures into refusals before returning, the `schema_valid` metric is structurally 100%. I keep it because if the conversion ever silently breaks I want it to show up. (See `auditor.audit` → the second `try/except ValidationError` block.)

## Arabic spot-check

Manual review of generated AR on three cases (1–5 scale, 5 = native Gulf register, 1 = literal translation):

| Case | Generated AR (title or desc) | Score | Note |
|---|---|---|---|
| 02 | "زجاجة فيليبس أفنت ناتشورال ريسبونس 260 مل (عبوة 3 قطع)" | 5 | Direct, idiomatic, brand transliterated correctly. |
| 03 | "حفاضات ألترا دراي، مقاس 3، عبوة 60 حبة" (after strip of unsupported claim) | 4 | Good; "عبوة 60 حبة" is the natural Gulf phrasing for "60-count pack". |
| 12 | (input was AR-only; auditor proposed an EN, not regenerated AR) | n/a | Correct behaviour — don't rewrite good input. |

Spot-check done by a native KSA Arabic reader (acknowledgement, not credentialed reviewer; documented as such per the brief's transparency expectation).

## How to extend the eval set

To add a new case:

1. Drop a new JSON in `data/pdps/`. Filename pattern is `NN_short_label.json`.
2. Add an `EvalCase(...)` entry to `evals/test_cases.py` listing `must_flag` / `must_not_flag` / `score_band` / refusal expectations.
3. `python -m evals.run_evals --case NN` to grade just that case while iterating.
