"""
CLI for the auditor. Useful for graders who want to skip Streamlit
and just see JSON in/out.

Examples:
    python cli.py data/pdps/03_literal_translation_arabic.json
    python cli.py data/pdps/03_literal_translation_arabic.json --pretty
    cat my_pdp.json | python cli.py -
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.auditor import Auditor
from src.schema import PDPInput


def main() -> int:
    p = argparse.ArgumentParser(description="Audit a single PDP JSON.")
    p.add_argument("path", help="Path to a PDP JSON, or '-' for stdin.")
    p.add_argument("--pretty", action="store_true", help="Indented JSON output.")
    args = p.parse_args()

    if args.path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.path).read_text(encoding="utf-8")

    try:
        pdp = PDPInput.model_validate(json.loads(raw))
    except Exception as e:
        print(f"Input failed validation: {e}", file=sys.stderr)
        return 2

    auditor = Auditor()
    result = auditor.audit(pdp)
    out = result.model_dump(mode="json")
    print(json.dumps(out, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
