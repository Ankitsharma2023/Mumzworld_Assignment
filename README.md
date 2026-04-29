# Mumzworld PDP Quality Auditor

> Track A submission for the Mumzworld AI-Native Engineering Intern take-home.
> By Ankit · ankitconnect10@gmail.com

**Live demo:** https://mumzworld-task.streamlit.app/
**3-min walkthrough:** https://www.loom.com/share/2abc1d77d14f43ccb84c4a8e67c8a435
**Repo:** https://github.com/Ankitsharma2023/Mumzworld_Assignment

---

## What this is

A tool that reads a product listing on Mumzworld's marketplace and tells you whether it's ready to publish.

You hand it a title, description, photo, and the seller's attributes. It hands you back a quality score (0 to 100), a list of specific problems with severity tags and evidence quotes, and concrete suggested fixes you can copy-paste. It works in English and Arabic, and writes Arabic that reads natively rather than as a translation of the English.

If a listing has nothing to grade — no title, no description, no image — the tool refuses with a clear reason instead of inventing one.

The easiest way to see it work is to open the live demo above, pick any of the 17 sample listings from the dropdown, and click Audit.

## Why this problem

Mumzworld has roughly 250,000 products on the site, and 70% of GMV comes from third-party sellers. There is no version of the world where a small team hand-reviews every listing. The downstream symptoms show up in Trustpilot reviews — wrong-fit products, weak Arabic, "doctor recommended" claims with no source, missing safety attributes on car seats. These aren't customer-service problems. They start at the listing.

I picked an automated PDP auditor because in 2026, with growth flat and Tamer Group squeezing for efficiency, an operational tool that compresses cost-per-SKU has more leverage than a customer-facing chatbot. The deeper rationale is in [TRADEOFFS.md](TRADEOFFS.md).

## Quickstart on Windows (PowerShell)

Run each command, wait for it to finish, then run the next. About 5 minutes from clone to first audit.

```powershell
git clone https://github.com/Ankitsharma2023/Mumzworld_Assignment.git
cd Mumzworld_Assignment

python -m venv .venv
.venv\Scripts\Activate.ps1
# If PowerShell blocks the script, run this once and re-try:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

pip install -r requirements.txt

Copy-Item .env.example .env
notepad .env
# Paste your OpenRouter API key (free signup at openrouter.ai). Save and close.

python test_setup.py
```

If `test_setup.py` ends with "All setup checks passed", you're ready:

```powershell
streamlit run app.py                # demo UI in your browser
python -m evals.run_evals           # run all 17 tests (takes 3-4 minutes)
python cli.py data/pdps/03_literal_translation_arabic.json --pretty
```

For Linux/Mac, swap `.venv\Scripts\Activate.ps1` for `source .venv/bin/activate` and use `cp` instead of `Copy-Item`.

For a fully offline check that uses zero API calls:

```powershell
python -m evals.run_evals --dry-run
```

This validates every fixture against the schema and confirms case definitions are coherent — no network needed.

## How it works

Five-step pipeline. Each step exists for a reason.

```
PDPInput
   |
   v
1. Pre-flight refusal check (cheap, deterministic)
   |     no content? -> refuse without spending an API call
   v
2. Build prompt with input + (optional) image
   |
   v
3. LLM call (vision + JSON mode)
   |     primary:  meta-llama/llama-3.2-11b-vision-instruct:free
   |     fallback: meta-llama/llama-3.3-70b-instruct:free
   v
4. Parse JSON, validate against Pydantic schema
   |     malformed output? -> convert to refusal, never silent pass
   v
5. Deterministic taxonomy enrichment
   |     LLM forgot a required attribute? Add the issue.
   |     We only ADD issues, never remove them.
   v
AuditResult (auditable=true with score + issues + fixes)
                     OR
AuditResult (auditable=false with refusal_reason)
```

Step 5 is the engineering safety net on top of the prompt. LLMs are inconsistent at remembering long required-attribute lists, especially when also generating Arabic copy. After the LLM returns, the code deterministically scans the input attributes against a hand-coded taxonomy and merges any missing-attribute issues the LLM overlooked. This catches a real failure mode I observed during development.

The brief asked for at least two of: agent design or tool use, multimodal input, RAG, structured output with validation, evals beyond vibes, fine-tuning, retrieval over messy data. This project hits five:

| Capability | Where in the code |
|---|---|
| Multimodal input | `src/client.py` accepts image_url or local image_path, base64-encodes locals, sends as a content block to the vision model |
| Structured output with validation | `src/schema.py` — Pydantic with strict types, enums, and a model-level validator that enforces refusal-consistency |
| Retrieval over messy data | `src/taxonomy.py` keyed by category, called from `src/auditor.py` post-LLM |
| Evals beyond vibes | `evals/test_cases.py` declares must-flag / must-not-flag / score-band per case; `evals/run_evals.py` reports recall, precision, refusal correctness |
| Multilingual (EN + AR) | `src/prompts.py` has dedicated AR prompt with explicit "you are NOT a translator" framing, plus `weak_arabic` and `missing_arabic` issue types in the schema |

## File layout

```
.
├── app.py                  # Streamlit demo UI
├── cli.py                  # CLI: audit a single PDP, JSON in/out
├── test_setup.py           # Self-test: imports, .env, one API call, one audit
├── requirements.txt
├── .env.example
├── README.md (this file)
├── EVALS.md                # Rubric, 17 test cases, latest scores, honest failures
├── TRADEOFFS.md            # Why this problem, what I rejected, model choice, what I cut
├── LOOM_SCRIPT.md          # 3-min walkthrough script
├── src/
│   ├── schema.py           # Pydantic models for input + audit output
│   ├── taxonomy.py         # Category -> required attributes (the RAG layer)
│   ├── client.py           # OpenRouter / OpenAI wrapper with auto-fallback
│   ├── prompts.py          # System prompts for audit + native AR generation
│   └── auditor.py          # The pipeline: pre-flight, LLM, parse, validate, enrich
├── data/pdps/              # 17 synthetic PDP fixtures
└── evals/
    ├── test_cases.py       # Per-fixture expectations (must_flag, score_band, etc.)
    ├── run_evals.py        # Runner + rubric + summary table
    └── results.json        # Latest run output
```

## Evals at a glance

Full rubric and all 17 test cases live in [EVALS.md](EVALS.md). Quick summary:

Every case is graded on five binary signals — issue recall, issue precision, score-band accuracy, refusal correctness, schema validity. The runner emits PASS/FAIL per case and a summary table.

The 17 cases include 8 clean listings, 9 adversarial ones (including one false-positive guard where a claim IS supported by an attribute and the auditor must NOT flag it). Score bands are intentionally wide to absorb run-to-run model variance without losing signal.

Known failure modes I haven't fixed are listed honestly in EVALS.md under "Honest list of failure modes." The brief explicitly asked for that and I treated it as part of the deliverable, not something to hide.

## Tooling and transparency

The brief asked for transparency on how AI was used. Here's what's actually true.

**At runtime**, the auditor uses two free OpenRouter models:
- Primary: `meta-llama/llama-3.2-11b-vision-instruct:free` — picked for vision + free + reasonable Arabic.
- Fallback: `meta-llama/llama-3.3-70b-instruct:free` — text only, used when the primary rate-limits.

Provider switching is one line in `.env` if you want to point at OpenAI or Anthropic with a paid key. No code change needed.

**During development**, I used Claude (Anthropic) as a pair-programmer in the take-home agent environment. I used it specifically for:
- Pydantic schema design and validator wording
- Crafting the few-shot examples in the audit prompt (especially the broken-Arabic example)
- Designing the eval rubric structure

I overrode the agent in two specific places:
1. The `model_validator` for refusal-consistency. The first version let `auditable=False` results carry a `quality_score=0`, which would mask refusal signal in evals. I changed it to require `quality_score=None` on refusals.
2. The deterministic `_enrich_with_attribute_gaps` post-pass. The agent preferred an "all-LLM" pipeline; I added the deterministic check after observing the LLM skipping required-attribute scans on listings where it was busy generating Arabic.

VS Code locally for everything else. No autonomous agent loop end-to-end — this was pair-coding, not delegation.

## Known limitations

- Score occasionally drifts a few points outside the band I expected (case 14 lands at 55 vs my 10–50 prediction). Documented in EVALS.md.
- Free vision models can't reliably distinguish blush-pink from sky-blue. Case 07 (title/image color mismatch) catches the issue ~70% of runs on Llama 3.2 Vision.
- Taxonomy hand-codes 5 product types. Mumzworld has dozens. The interface is a single function, so swapping in a vector lookup is a one-day change.
- The `unsupported_claim` detector relies on the LLM's judgement, not a citation extractor. Case 13 (false-positive guard) trips ~10% of runs because the model treats string attribute references less rigorously than URLs.

## What I'd build next

In strict priority order, given another five-hour block:

1. Citation extractor for claims — biggest reduction in false-positive rate.
2. Vector-indexed taxonomy over Mumzworld's real category tree.
3. Edit-feedback loop where merchant edits become eval cases automatically.
4. Cost-per-audit telemetry with budget guardrails.
5. Small fine-tuned classifier for `weak_arabic` so we don't burn an LLM call on every listing.

Detail in [TRADEOFFS.md](TRADEOFFS.md).

---

Questions, anything to clarify, or you'd like me to walk through a piece in more depth — I'm at **ankitconnect10@gmail.com**.

— Ankit
