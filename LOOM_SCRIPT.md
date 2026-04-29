# 3-Minute Loom Script

The brief asks for "5 inputs going through end to end, including at least one where the model correctly refuses or expresses uncertainty." Here's a beat-by-beat 3-minute walkthrough.

**Before recording**
- Run `streamlit run app.py` in one terminal.
- Have a second terminal open at the project root for the CLI demo at the end.
- Have this script in a separate window.
- Pre-test that the audit on case 03 finishes in <12 seconds; if it's slower, consider mentioning model latency upfront.

**Recording style**
- Show your face in the corner if Loom allows — graders said "we want to see how you think." Talking-head adds signal.
- Speak slightly faster than feels natural. 3 minutes is tight.

---

## Beat 1 — 0:00 to 0:25 (25s) — The pitch

> "Hi, I'm Ankit. This is my Track A submission: a PDP Quality Auditor for Mumzworld's marketplace listings.
>
> Quick context for why this. Mumzworld has roughly 250,000 SKUs and 70% of GMV comes from third-party sellers. At that scale they cannot manually QA the catalog, and that's traceable in Trustpilot complaints — wrong items, weak Arabic, missing safety info. So I built an automated reviewer that grades a single PDP, returns specific issues, and proposes concrete fixes — including native Gulf-Arabic copy when the seller's AR is missing or literal."

**On screen:** Streamlit homepage already loaded with case 01 selected.

---

## Beat 2 — 0:25 to 0:55 (30s) — Input 1: clean listing, high score

> "First, a clean listing — a Doona stroller with full bilingual copy and all required attributes. The auditor returns a score in the high 80s or 90s, no issues. Importantly the prompt forbids padding the issue list to look thorough — empty list is the right answer here."

**On screen:** Click *Audit*. Wait. Show the score. Scroll through the empty issue list.

---

## Beat 3 — 0:55 to 1:30 (35s) — Input 2: literal-translation Arabic + unsupported claim

> "Now case 03 — an UltraDry diaper listing. The English title says 'Doctor Recommended' with no source. The Arabic is a literal word-for-word translation of the English: 'طبيب أوصى' is grammatically broken. And the absorbency attribute is missing. Watch what fires."

**On screen:** Switch fixture, *Audit*. Highlight three things in the output:
1. `weak_arabic` issue with the specific evidence quote.
2. `unsupported_claim` on "Doctor Recommended".
3. `attribute_gap` for absorbency (this one is added by the deterministic taxonomy pass — the engineering safety net on top of the LLM).
4. The native AR copy generated at the bottom — point out that it's not a translation, it uses different sentence structure.

---

## Beat 4 — 1:30 to 1:55 (25s) — Input 3: false-positive guard

> "This one is the adversarial case. A MAM bottle that DOES claim 'reduces colic', but the claim is backed by a `study_reference` attribute. The auditor must NOT flag this. False positives are graded as harshly as false negatives in my eval rubric."

**On screen:** Case 13. *Audit*. Show that `unsupported_claim` does NOT fire, and the score lands in the 80s.

---

## Beat 5 — 1:55 to 2:20 (25s) — Input 4: refusal

> "Brief explicitly asks for at least one refusal or uncertainty case. Case 08 — empty everything. The auditor's pre-flight check refuses without spending an API call, gives a typed `auditable=false`, and explains why. Schema-level — refusals can't carry a quality_score, the validator enforces that."

**On screen:** Case 08. *Audit*. Show the warning panel with the refusal reason. Briefly flip to the raw JSON to show `auditable: false`, `quality_score: null`.

---

## Beat 6 — 2:20 to 2:45 (25s) — Input 5: car seat with safety gaps (CLI)

> "Last input — and let me show this from the CLI to demonstrate it's not just the UI. A generic car seat missing ECE certification, ISOFIX, weight range. Safety gaps are graded as HIGH severity and pull the score down hard."

**On screen:** Switch to terminal:
```
python cli.py data/pdps/10_safety_attrs_missing_carseat.json --pretty
```
Scroll through the JSON output. Highlight the `safety_info_missing` entries with `"severity": "high"`.

---

## Beat 7 — 2:45 to 3:00 (15s) — Wrap

> "Full eval suite is `python -m evals.run_evals` — 17 cases, four orthogonal metrics, results written to JSON. Tradeoffs and tooling transparency in the README. Repo link in the email. Thanks."

---

## Backup lines if something glitches

- If the LLM is slow: "Live model is on OpenRouter free tier, sometimes a couple seconds slower than the cached run."
- If the model returns malformed JSON: "Notice the schema validator caught that and converted it into a refusal — that's the failure-mode handling I described."
- If you blank: scroll to the EVALS.md table on screen and read the rubric. That eats 10 seconds and looks deliberate.

## Submission email template

```
To: ai-intern@mumzworld.com
Subject: Mumzworld AI Intern | Track A | Ankit [Last Name]

Hi team,

Track A submission below.

Repo: https://github.com/<your-handle>/mumzworld-pdp-auditor
Loom: https://www.loom.com/share/<id>

README has setup, evals, tradeoffs, and tooling transparency.
Project is the PDP Quality Auditor for marketplace listings —
problem-selection rationale grounded in Mumzworld's 70% 3P GMV
split is in TRADEOFFS.md.

Thanks,
Ankit
```
