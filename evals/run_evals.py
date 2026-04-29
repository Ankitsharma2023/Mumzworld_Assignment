"""
Run the eval suite end-to-end and report.

Usage:
    python -m evals.run_evals               # full run, real LLM calls
    python -m evals.run_evals --case 03     # one case only
    python -m evals.run_evals --dry-run     # validate fixtures + cases, no LLM

Output:
    - prints a per-case PASS/FAIL line
    - writes evals/results.json with the full structured output
    - prints a summary table at the end with the rubric scores

Rubric (matches EVALS.md):
    1. issue_recall          : did must_flag types fire?            (binary per case, averaged)
    2. issue_precision       : were must_not_flag types absent?     (binary per case, averaged)
    3. score_band_accuracy   : did quality_score land in band?      (binary per case, averaged)
    4. refusal_correctness   : did refusal cases refuse?            (binary per case, averaged)
    5. schema_validity       : did the output validate?             (binary per case, averaged)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.auditor import Auditor
from src.schema import AuditResult, PDPInput

from evals.test_cases import CASES, PDP_DIR, EvalCase


console = Console()
RESULTS_PATH = Path(__file__).parent / "results.json"


@dataclass
class CaseResult:
    fixture: str
    passed: bool
    failures: list[str]
    audit_dict: dict
    score_band_hit: bool | None
    issue_recall_hit: bool
    issue_precision_hit: bool
    refusal_correct: bool
    schema_valid: bool
    elapsed_s: float


def grade_one(case: EvalCase, audit: AuditResult) -> CaseResult:
    failures: list[str] = []
    schema_valid = True

    refusal_correct = audit.auditable == case.must_be_auditable
    if not refusal_correct:
        failures.append(
            f"auditable mismatch: expected={case.must_be_auditable}, got={audit.auditable}"
        )

    if case.refusal_reason_keywords and not audit.auditable:
        rr = (audit.refusal_reason or "").lower()
        if not any(kw in rr for kw in case.refusal_reason_keywords):
            failures.append(
                f"refusal_reason missing any of {case.refusal_reason_keywords!r}; got={rr!r}"
            )

    fired_types = {issue.type for issue in audit.issues}
    issue_recall_hit = all(t in fired_types for t in case.must_flag)
    if not issue_recall_hit:
        missing = [t.value for t in case.must_flag if t not in fired_types]
        failures.append(f"must_flag missing: {missing}")

    issue_precision_hit = all(t not in fired_types for t in case.must_not_flag)
    if not issue_precision_hit:
        bad = [t.value for t in case.must_not_flag if t in fired_types]
        failures.append(f"false positives flagged: {bad}")

    if case.score_band is None:
        score_band_hit = None
    else:
        lo, hi = case.score_band
        if audit.quality_score is None:
            score_band_hit = False
            failures.append(f"score_band {case.score_band} but score is None")
        else:
            score_band_hit = lo <= audit.quality_score <= hi
            if not score_band_hit:
                failures.append(
                    f"score {audit.quality_score} outside band {case.score_band}"
                )

    passed = (
        refusal_correct
        and issue_recall_hit
        and issue_precision_hit
        and (score_band_hit is None or score_band_hit)
    )

    return CaseResult(
        fixture=case.fixture,
        passed=passed,
        failures=failures,
        audit_dict=audit.model_dump(mode="json"),
        score_band_hit=score_band_hit,
        issue_recall_hit=issue_recall_hit,
        issue_precision_hit=issue_precision_hit,
        refusal_correct=refusal_correct,
        schema_valid=schema_valid,
        elapsed_s=0.0,
    )


def run(case_filter: str | None = None, dry_run: bool = False) -> int:
    auditor = None if dry_run else Auditor()
    results: list[CaseResult] = []

    cases = CASES
    if case_filter:
        cases = [c for c in CASES if case_filter in c.fixture]
        if not cases:
            console.print(f"[red]No cases match {case_filter!r}[/red]")
            return 2

    for case in cases:
        path = PDP_DIR / case.fixture
        with path.open(encoding="utf-8") as f:
            pdp = PDPInput.model_validate(json.load(f))

        if dry_run:
            console.print(f"[dim]dry-run: {case.fixture} fixture-valid[/dim]")
            continue

        t0 = time.time()
        audit = auditor.audit(pdp)
        dt = time.time() - t0

        cr = grade_one(case, audit)
        cr.elapsed_s = round(dt, 2)
        results.append(cr)

        marker = "[green]PASS[/green]" if cr.passed else "[red]FAIL[/red]"
        console.print(f"{marker} {case.fixture}  ({dt:.1f}s)")
        for f in cr.failures:
            console.print(f"   [yellow]·[/yellow] {f}")

    if dry_run:
        console.print("\n[bold green]All fixtures validate.[/bold green]")
        return 0

    _print_summary(results)
    _write_results(results)
    return 0 if all(r.passed for r in results) else 1


def _print_summary(results: list[CaseResult]) -> None:
    n = len(results) or 1
    table = Table(title="Eval rubric")
    table.add_column("Metric", justify="left")
    table.add_column("Score", justify="right")

    table.add_row("Cases passed (overall)", f"{sum(r.passed for r in results)}/{n}")
    table.add_row(
        "Issue recall (must_flag fired)",
        f"{sum(r.issue_recall_hit for r in results)}/{n}",
    )
    table.add_row(
        "Issue precision (no false positives)",
        f"{sum(r.issue_precision_hit for r in results)}/{n}",
    )
    table.add_row(
        "Refusal correctness",
        f"{sum(r.refusal_correct for r in results)}/{n}",
    )

    band_eligible = [r for r in results if r.score_band_hit is not None]
    table.add_row(
        "Score-band accuracy",
        f"{sum(r.score_band_hit for r in band_eligible)}/{len(band_eligible)}",
    )

    console.print(table)


def _write_results(results: list[CaseResult]) -> None:
    payload = {
        "n_cases": len(results),
        "n_passed": sum(1 for r in results if r.passed),
        "cases": [r.__dict__ for r in results],
    }

    RESULTS_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    console.print(f"\nResults written to [cyan]{RESULTS_PATH}[/cyan]")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    sys.exit(run(case_filter=args.case, dry_run=args.dry_run))


if __name__ == "__main__":
    main()