# Mumzworld PDP Quality Auditor

> Track A submission for the Mumzworld AI-Native Engineering Intern take-home.

## What this is

A multimodal AI auditor for marketplace product detail pages (PDPs) on Mumzworld. Given a 3P seller's listing — title, description, image, attributes, in any mix of English and Arabic — it returns a structured, citable audit:

- A 0–100 quality score with a one-sentence rationale.
- Specific, typed issues (missing AR, literal-translation AR, unsupported claims, attribute gaps, safety-info gaps, title/image mismatches, generic padding, etc.) with severity, evidence, and confidence.
- Concrete suggested fixes (rewritten title, native-Arabic copy, missing attribute values inferred from the image).
- A first-class refusal mode for inputs that are too sparse to audit.

Output is a Pydantic-validated JSON object. Malformed model output, missing required fields, and silent empty strings are all converted into explicit refusals — never returned as a "successful" audit.

## Why this problem

Mumzworld carries ~250K SKUs and **70% of GMV comes from third-party marketplace sellers** (1P is 30%). At that scale catalog quality cannot be hand-QA'd, and it shows up downstream — Trustpilot reviews repeatedly mention wrong-fit products, weak Arabic, missing safety info, and counterfeit listings, all of which trace back to PDP quality. Annual revenue is ~$36M and 2026 growth is flat; operational AI that compresses cost-per-SKU has more leverage right now than another customer-facing chat feature.

This auditor sits in the merchant-onboarding and ongoing-quality loops as an automated reviewer: a seller submits or edits a PDP, the auditor flags issues with concrete fixes, and a human only intervenes on the high-severity edge cases.

See [TRADEOFFS.md](TRADEOFFS.md) for the full problem-selection defence, alternatives considered, model choice, and what was cut.

## Quickstart (≤5 minutes)

```bash
git clone <this-repo>
cd mumzworld-pdp-auditor

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and paste an OpenRouter key. Free signup at openrouter.ai.
# Default model (google/gemini-2.0-flash-exp:free) is free.

# Run a single audit from the CLI
python cli.py data/pdps/03_literal_translation_arabic.json --pretty

# Or launch the demo UI
streamlit run app.py

# Run the eval suite
python -m evals.run_evals
```

If you don't want to spend an API call to validate the install, do a dry run first:

```bash
python -m evals.run_evals --dry-run
```

This validates every fixture against the schema and checks the case definitions are coherent — no network calls.

## Architecture

```
PDPInput  ──▶  pre-flight refusal check (empty content?)
                       │
                       ▼
              build prompt with image
                       │
                       ▼
   LLM (vision + JSON) — primary: google/gemini-2.0-flash-exp:free
                       │       fallback: meta-llama/llama-3.2-11b-vision-instruct:free
                       ▼
            parse JSON, strip fences
                       │
                       ▼
          Pydantic AuditResult validation
                       │
                       ▼
   deterministic taxonomy pass: add any missing-attribute issues
   the LLM forgot (engineering safety net on top of the prompt)
                       │
                       ▼
                AuditResult (auditable=true)
                                       OR
                AuditResult (auditable=false, refusal_reason=...)
```

Five capabilities from the brief are exercised:

| Capability | Where in the code |
|---|---|
| Multimodal input | `client.LLMClient.complete()` accepts `image_path` / `image_url`, base64-encodes locals, sends as a content block to a vision model. |
| Structured output with validation | `schema.AuditResult` with strict types, enums for issue/severity, model-level validator for refusal-consistency. Empty strings rejected. |
| Retrieval over messy data | `taxonomy.get_requirements()` keyed by category. Used in `auditor._enrich_with_attribute_gaps` as a deterministic safety net. |
| Evals beyond vibes | `evals/test_cases.py` declares must-flag / must-not-flag / score-band / refusal expectations per case. `run_evals.py` reports issue recall, issue precision, refusal correctness, score-band accuracy. |
| Multilingual (EN + AR) | Native Gulf-Arabic generation via `prompts.AR_GENERATION_SYSTEM`, plus dedicated `weak_arabic` / `missing_arabic` issue types. AR is generated, not translated. |

## File layout

```
.
├── app.py                  # Streamlit demo UI
├── cli.py                  # CLI: audit a single PDP
├── requirements.txt
├── .env.example
├── README.md, EVALS.md, TRADEOFFS.md
├── src/
│   ├── schema.py           # Pydantic input + output schemas
│   ├── taxonomy.py         # Category → required attributes
│   ├── client.py           # OpenRouter / OpenAI wrapper with fallback
│   ├── prompts.py          # System prompts (audit + AR generation)
│   └── auditor.py          # Pipeline: pre-flight, LLM call, parse, validate, enrich
├── data/pdps/              # 17 synthetic PDP fixtures (clean, broken, refusal cases)
└── evals/
    ├── test_cases.py       # Eval expectations per fixture
    ├── run_evals.py        # Runner + rubric
    └── results.json        # Latest run output
```

## Evals

See [EVALS.md](EVALS.md) for the full rubric, all 17 cases, and the latest scores.

Quick summary of the rubric (per case, then averaged):

1. Issue recall — every issue type in `must_flag` fires.
2. Issue precision — no issue type in `must_not_flag` fires (false-positive guard, especially case 13).
3. Score-band accuracy — `quality_score` is inside the expected band.
4. Refusal correctness — `auditable` flag matches expectation; refusal-reason contains expected keywords.
5. Schema validity — output validates against `AuditResult` (any model output that fails this is converted to a refusal upstream, so this is graded as 100% by construction; the metric is kept to make regressions visible).

## Tooling

The brief asks for transparency on how AI was used to build this; here is what the README needs to disclose.

**Models used at runtime**
- Primary: `google/gemini-2.0-flash-exp:free` via OpenRouter. Picked because it's free, multimodal (handles the product image), and Gemini family handles Arabic well — the brief explicitly penalises Arabic-that-reads-like-translation, so AR fluency mattered more than reasoning depth.
- Fallback: `meta-llama/llama-3.2-11b-vision-instruct:free` via OpenRouter. Wired as automatic fallback on rate-limit or 5xx; used for redundancy, not primary.
- I also tested `deepseek/deepseek-chat:free` for the audit reasoning step on text-only inputs and it was competitive but lacked a vision endpoint, so I stayed on Gemini for a single-model-path in the prototype.

**AI assistants used to write the code**
- Claude (Anthropic) for pair-programming via the agent in this take-home environment. Specifically: schema design, validator wording, prompt few-shot construction (especially the Arabic example), and the eval rubric. I edited the prompts manually after the first pass to add the explicit "do not translate" rule and the worked Example B — the model's first prompt draft caught literal-translation cases inconsistently and the few-shot fixed it.
- VS Code locally for everything else. No agent-loop coding harness used end-to-end; this was pair-coding, not autonomous generation.

**Where I overrode the agent**
- The schema's `model_validator` for refusal-consistency was added after I noticed the agent's first version let `auditable=False` results carry a `quality_score` of 0, which is not the same as None and would have masked the "did it refuse" signal in evals.
- The deterministic `_enrich_with_attribute_gaps` post-pass was something I added against the agent's preference for an "all-LLM" pipeline, after eyeballing a few audits where the LLM had clearly skimmed the attribute list. The taxonomy check costs nothing and catches a real failure mode.

**Prompts that mattered**
- `prompts.AUDIT_SYSTEM`, especially the two-shot examples and the "Hard rules" block. The `NEVER pad an issue list to look thorough` rule cut a clear pattern of the model inventing issues to look diligent on clean listings.
- `prompts.AR_GENERATION_SYSTEM`, especially the explicit "you are NOT a translator" framing. Smaller models (the Llama 3.2 fallback) regress to translation without that line.

## Limitations and known failure modes

These are documented in EVALS.md too, but worth surfacing here:

- The auditor cannot reliably infer brand or model from images alone. For image-only inputs (case 17) it correctly refuses rather than hallucinating.
- AR-quality grading depends on the underlying model's Arabic fluency. Gemini 2.0 Flash is good; the Llama 3.2 fallback is noticeably worse and will sometimes mis-flag good AR as weak.
- The `unsupported_claim` detector is conservative — it relies on the LLM's judgement, not a citation extractor. Case 13 (claim with attribute reference) is the adversarial test that the false-positive rate is acceptable.
- The taxonomy covers 5 categories. Unknown categories (case 15) are still audited for language and image quality but skip attribute-gap detection.

## How I'd extend this beyond 5 hours

Spelled out in TRADEOFFS.md → "What I'd build next." TL;DR: real Mumzworld category taxonomy (vector-indexed), a faithfulness eval that grounds claims in attribute citations, a feedback loop where merchant edits become eval cases, and a small fine-tuned classifier for the high-volume `weak_arabic` detection so we can drop the LLM call cost there.
#   M u m z w o r l d _ A s s i g n m e n t  
 