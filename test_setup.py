"""
Self-test for your local setup.

Run this BEFORE running evals or recording the Loom. It makes one cheap
API call to OpenRouter and reports exactly what's wrong if anything fails.

Usage:
    python test_setup.py

Exit codes:
    0 = everything works, you're ready to run evals and record the Loom
    1 = setup problem; the message above tells you what to fix
"""

from __future__ import annotations

import os
import sys


def _fail(msg: str, fix: str) -> None:
    print(f"\n[FAIL] {msg}")
    print(f"[FIX]  {fix}\n")
    sys.exit(1)


def main() -> None:
    print("=" * 60)
    print("Mumzworld PDP Auditor — Setup Self-Test")
    print("=" * 60)

    # ----- 1. Imports -----
    print("\n[1/4] Checking imports...")
    try:
        from dotenv import load_dotenv
        from openai import OpenAI
        import pydantic
        import streamlit  # noqa: F401  (just imported to verify availability)
    except ImportError as e:
        _fail(
            f"Missing dependency: {e.name}",
            "Run: pip install -r requirements.txt  (and make sure your venv is activated)",
        )
    print("    OK — all dependencies installed")

    # ----- 2. .env file -----
    print("\n[2/4] Checking .env file...")
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        _fail(
            "OPENROUTER_API_KEY is not set",
            "Copy .env.example to .env and paste your OpenRouter key into it. "
            "On Windows: Copy-Item .env.example .env",
        )
    if not api_key.startswith("sk-or-"):
        _fail(
            f"OPENROUTER_API_KEY doesn't look right (starts with {api_key[:8]!r})",
            "OpenRouter keys start with 'sk-or-'. Generate a fresh one at "
            "https://openrouter.ai/settings/keys",
        )
    print(f"    OK — key loaded (starts with {api_key[:10]}...)")

    model = os.getenv("AUDIT_MODEL", "google/gemini-2.0-flash-exp:free")
    print(f"    Using model: {model}")

    # ----- 3. Make a tiny API call -----
    print("\n[3/4] Making a test API call to OpenRouter...")
    print("      (this confirms your key works and the model is reachable)")
    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly the word: PONG",
                }
            ],
            max_tokens=10,
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        _fail(
            f"API call failed: {type(e).__name__}: {e}",
            "Common causes: (a) wrong API key, (b) no internet, "
            "(c) model name is wrong in .env, (d) you're rate-limited on the "
            "free tier — wait 30s and retry. If it persists, try changing "
            "AUDIT_MODEL in .env to: meta-llama/llama-3.2-11b-vision-instruct:free",
        )
    if "PONG" not in text.upper():
        print(f"    WARN — model replied {text!r} instead of 'PONG'.")
        print("    This isn't fatal but indicates the model isn't following instructions strictly.")
    else:
        print("    OK — model replied 'PONG'")

    # ----- 4. Run a real audit on the smallest fixture -----
    print("\n[4/4] Running one real audit (case 08, the refusal case — fast)...")
    import json
    from pathlib import Path
    from src.auditor import Auditor
    from src.schema import PDPInput

    fixture = Path("data/pdps/08_too_sparse_refuse.json")
    if not fixture.exists():
        _fail(
            f"Fixture {fixture} is missing",
            "You may have downloaded an incomplete copy of the project. "
            "Re-download the mumzworld-pdp-auditor folder.",
        )
    pdp = PDPInput.model_validate(json.loads(fixture.read_text(encoding="utf-8")))
    auditor = Auditor()
    result = auditor.audit(pdp)
    if result.auditable:
        print(
            f"    WARN — case 08 should have refused, but it returned auditable=True "
            f"(score={result.quality_score}). The pipeline ran but the model is being "
            "over-helpful. Not a setup problem — just note it."
        )
    else:
        print(f"    OK — case 08 refused as expected")
        print(f"    Refusal reason: {result.refusal_reason}")

    # ----- All clear -----
    print("\n" + "=" * 60)
    print("All setup checks passed. You're ready to:")
    print("  1. Run the demo UI:        streamlit run app.py")
    print("  2. Run the full eval suite: python -m evals.run_evals")
    print("  3. Audit one PDP:           python cli.py data/pdps/03_literal_translation_arabic.json --pretty")
    print("=" * 60)


if __name__ == "__main__":
    main()
