"""Exercise the scanner contract without performing security analysis."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from secprbench.harnesses.contract import validate_predictions
from secprbench.schema import ReviewInput


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", default=os.environ.get("SECPRBENCH_RUN_ID"))
    args = parser.parse_args()
    if not args.run_id:
        parser.error("provide --run-id or SECPRBENCH_RUN_ID")
    public = ReviewInput.model_validate_json(args.input.read_text())
    result = validate_predictions(
        {
            "instance_id": args.run_id,
            "model": "contract-example-no-security-analysis",
            "predictions": [],
        },
        public,
        instance_id=args.run_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Validated format-only example: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
