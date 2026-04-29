# Tradeoffs

This is the "why" doc. The README explains what the auditor does and how to run it; this one explains the choices behind it.

## 1. Why this problem (and what I rejected)

The brief gives ten example problems, says "a well-defended novel problem beats a strong execution of a listed one," and weights problem selection at 20%. So I started by trying to find a problem that maps to a *Mumzworld-specific* number rather than a generic e-commerce pain point.

Two facts shaped the pick:

- **70% of GMV is third-party marketplace** (1P is 30%). On ~250K SKUs, that means most of Mumzworld's revenue rides on listings the central team did not write and cannot manually QA.
- **2026 growth is flat** (~$36M revenue) and the parent company (Tamer Group, post-acquisition) is squeezing for efficiency. Operational AI that compresses cost-per-SKU has more leverage in this moment than another customer-facing chat feature.

Combine those and the highest-leverage AI engineering problem is *automated catalog quality* — a tool that turns the 200K+ unwatched 3P listings into something a small ops team can supervise rather than personally rewrite.

### Alternatives I considered and rejected

| Idea | Why I didn't pick it |
|---|---|
| Bilingual customer-service triage + reply drafter | Maps directly to the #1 Trustpilot complaint theme (poor CS replies). Tempting. Rejected because (a) it's a listed example in the brief, so less novelty points, and (b) it is text-only, so it stacks fewer of the brief's required capabilities than a multimodal auditor. |
| "Moms Verdict" review synthesizer | Clean problem, clean evals. But the leverage is on a downstream content surface (reviews summary on the PDP), not on the structural catalog problem upstream. Same effort, narrower impact. |
| Duplicate-listing detector with embeddings | Strong fit for the marketplace problem and listed in the brief. Rejected because pure embedding similarity is a single capability, while a quality auditor stacks vision + structured output + multilingual + RAG-over-taxonomy + evals. The brief explicitly asks for at least two; auditor gets five. |
| Voice-memo to shopping list (listed example) | Cute, demos well, but harder to defend as "high-leverage for Mumzworld in 2026" than an operational catalog tool. |
| Pediatric symptom triage with deferral | Best on the 15% uncertainty-handling rubric (refusal is the whole point). Rejected because the medical framing requires careful disclaimers and a public-guidelines RAG corpus that I couldn't ground confidently in 5 hours, plus Mumzworld would (rightly) need a clinical reviewer in the loop before shipping. The risk of looking flippant on safety outweighed the rubric upside. |

If I were given a second 5-hour block I would build the CS triage tool as a complementary piece — together they cover the upstream (catalog quality, this project) and downstream (CS load) sides of the same root cause.

## 2. Architecture choices

### LLM-driven core, deterministic safety net

The auditor isn't a single prompt-wrapped script. It's:

```
pre-flight refusal → LLM (vision + JSON) → schema validation → deterministic taxonomy enrichment → return
```

The first and last steps exist to handle two failure modes that pure LLM pipelines hit reliably on this kind of task:

- **Pre-flight refusal** (cheap, deterministic): if there is literally no content, return a refusal without spending an API call. Cheaper, faster, and avoids the model trying to be helpful on a blank input.
- **Taxonomy enrichment** (after the LLM): the LLM is inconsistent at remembering long required-attribute lists, especially when also generating Arabic copy. After the LLM returns, we deterministically scan the input attributes against the taxonomy and merge any missing-attribute issues the LLM forgot. We only ever *add* issues, never remove them, so the LLM's other judgements are preserved.

This is the kind of split that the brief calls out as "real engineering on top of an AI piece."

### Refusals as first-class outputs

`AuditResult.auditable: bool` is a primary field. A refusal is a successful output, not an exception. The schema's `model_validator` enforces consistency: refusals must have a reason and must NOT have a quality_score; non-refusals must have a score and a rationale. This makes the brief's "Output is grounded in the input. The model says 'I don't know'" requirement testable rather than aspirational — the eval suite has cases (08, 17) where the only correct answer is to refuse, and the rubric grades that explicitly.

### Schema before prompt

I wrote `schema.py` before `prompts.py`. The system prompt then describes the schema in plain English (not JSON Schema syntax — small open-source models follow English-described shapes more reliably). This made iterating on the audit logic cheap: change the schema, the prompt's "Output JSON shape" block changes once, and the eval harness picks up the new types automatically.

### Image as optional, not mandatory

The pipeline runs without an image (lower confidence on image-related issues, but still produces a useful audit). This matters because not all 3P listings have images uploaded yet at audit time, and forcing image presence would either drop the throughput or force a second pipeline path. One pipeline that gracefully degrades is simpler than two.

## 3. Model choice

### Primary: `google/gemini-2.0-flash-exp:free`

Picked for three reasons:

1. **Free** via OpenRouter — the brief explicitly encourages free models and notes that paid keys are not required to score well.
2. **Multimodal** — vision is needed for the `title_image_mismatch` and image-quality checks.
3. **Strong Arabic** — the brief penalises Arabic-that-reads-like-translation more sharply than weak reasoning. Gemini family handles Arabic well, including Gulf register. Llama 3.x is competitive on reasoning but visibly worse on AR fluency.

### Fallback: `meta-llama/llama-3.2-11b-vision-instruct:free`

Wired into `client.LLMClient` as automatic fallback on rate-limit or 5xx. Used only as redundancy. Notably weaker on Arabic; the eval harness will surface that as a regression on the AR-quality cases if it kicks in for the whole run.

### What I tested and didn't pick

- `deepseek/deepseek-chat:free` for the audit reasoning step — competitive on text-only inputs, lacks vision endpoint, would have required splitting into two pipelines.
- `qwen/qwen-2-vl-7b-instruct:free` — strong on Chinese, weaker on Arabic, dropped early.

If I had a paid key I'd swap to `anthropic/claude-3.5-haiku` (cheap, strong on structured output and AR), but the brief's grading rubric doesn't reward that decision and free models are sufficient.

## 4. Uncertainty handling

The brief weights this at 15%. Three places it surfaces:

1. **Confidences are required floats** on every issue and every suggested fix. The schema rejects implicit "100% sure" defaults — the model has to commit a number. Low-confidence fixes are kept in the output (they're useful as starting drafts) rather than silently dropped.
2. **Refusal is a typed output**, not an exception. The eval suite has dedicated refusal cases. Models that don't know how to refuse score lower on this rubric.
3. **Schema validation failures become refusals**, not silent passes. If the model returns malformed JSON, missing required fields, or empty strings (the brief calls these out explicitly: "Malformed JSON, or fields filled with empty strings to 'pass'"), the pipeline converts them to a refusal with a reason. This is the difference between "the auditor failed" and "the auditor lied about success".
4. **Native Arabic generation is allowed to return null**. The AR generation prompt explicitly tells the model: if you can't write good Gulf-register Arabic for this product, return null instead of producing weak copy. This trades coverage for honesty — the brief flags weak AR more harshly than missing AR.

## 5. What I cut

In rough priority order; cuts I'd reverse first are at the top.

- **Citation extraction for `unsupported_claim`**. Right now the LLM judges whether a claim is supported by attributes. A more rigorous version would extract claim phrases, look them up against attribute keys, and only flag when no key matches. Would lower the false-positive rate on case 13.
- **Vector-indexed taxonomy.** The 5-category dict is enough for the prototype but Mumzworld's real category tree is much larger. `taxonomy.get_requirements(category)` is the only entry point; swapping for a vector lookup is a 20-line change and doesn't touch the rest of the pipeline.
- **Per-claim citation back to attributes.** Suggested fixes don't currently cite *which attribute* they were derived from. Worth adding for human reviewers.
- **Streaming UI** in the Streamlit app. Audits take a few seconds; users would appreciate a streaming view. Not material for a 3-min Loom.
- **A small fine-tuned classifier for `weak_arabic`**. This is the single most-fired issue type in production scale; an LLM call per listing for one classifier is wasteful. A small classifier would let us reserve LLM budget for the harder issues. Out of scope for 5 hours.
- **Persistent batch mode + cost report.** The CLI does one PDP at a time. A real ops pipeline would batch and report cost-per-audit + cost-saved-vs-human-edit. Easy to add.

## 6. Failure modes I know about

Listed in EVALS.md → "Honest list of failure modes." The headline ones:

- Case 07 (title/image colour mismatch) is flaky on free vision models — the model frequently calls blush-pink "blueish".
- Case 11 (generic padding) sometimes scores 55, just above the "must-rewrite" threshold of 50.
- Case 13 (false-positive guard for supported claims) trips ~10% of runs because the model treats string attribute references less rigorously than URLs.

I left these visible in the eval rubric instead of writing around them.

## 7. What I'd build next

In strict order, given more time:

1. **Citation extractor for claims** (described above). Biggest reduction in false-positive rate.
2. **Real Mumzworld category taxonomy via vector lookup.** Plug into the existing `get_requirements()` interface. Unlocks the rest of the catalog.
3. **Edit-feedback loop**: when a merchant edits a flagged listing, capture the diff as a new eval case automatically. Eval suite grows with usage.
4. **Cost-per-audit telemetry + a budget guardrail.** Free-tier rate limits on OpenRouter are real; a production version would need budget-aware fallbacks.
5. **Fine-tuned `weak_arabic` classifier** (described above) to cut LLM cost on the highest-volume issue type.

## 8. Where the time went (rough log)

- 0:00–0:30 — Read brief twice. Researched Mumzworld (publicly available company data, Trustpilot themes, GMV split). Decided on the auditor angle.
- 0:30–1:00 — Wrote schema first, then taxonomy, then the OpenRouter client wrapper. Schema-first kept the prompt cheap to iterate on later.
- 1:00–1:45 — Wrote the audit and AR-generation prompts. Hand-tuned the two-shot examples after a first run flagged a clean listing for "missing absorbency" that was actually present.
- 1:45–2:30 — Generated 17 synthetic PDP fixtures. Tried to cover both must-flag and must-NOT-flag cases (case 13 took two passes to make appropriately adversarial).
- 2:30–3:15 — Built the eval harness. Settled on must_flag / must_not_flag / score_band / refusal-correctness as the four orthogonal signals. Score-band is wide because run-to-run variance on free models is real.
- 3:15–4:00 — Streamlit UI + CLI + .env handling + provider switching. Kept the UI deliberately minimal — the demo is about the output, not the framing.
- 4:00–4:45 — Documentation: README, EVALS.md, this file. Spent more time here than I expected; the brief weights tooling transparency at part of the 10% code-clarity line and I wanted the provenance section to be specific rather than generic.
- 4:45–5:00 — Sanity pass. Re-ran the eval suite, fixed two prompt regressions, recorded the Loom.

Total: ~5 hours, no overflow. I went over by 15 minutes on the documentation phase and trimmed by skipping the streaming UI work.
