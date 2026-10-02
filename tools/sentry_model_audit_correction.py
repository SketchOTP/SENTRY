"""Operator-only metadata correction; no resident/MCP write registration.

Dry run is default. Apply requires exact previously inspected UUID:SHA256 pairs.
Only explicit SYNTHETIC_TEST classifications append to the existing private
ledger; original execution records, prompts, models and bindings are untouched.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.sentry_execution_authority import ExecutionAuthority


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument(
        "--receipt",
        action="append",
        required=True,
        help="UUID:SHA256; omit digest for dry run only",
    )
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    expected = {}
    for value in arguments.receipt:
        key, _, digest = value.partition(":")
        if key in expected:
            parser.error("duplicate receipt ID")
        expected[key] = digest
    authority = ExecutionAuthority(arguments.authority_root)
    print(
        json.dumps(
            authority.classify_model_test_receipts(expected, apply=arguments.apply),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
