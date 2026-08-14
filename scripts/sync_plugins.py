"""Synchronize marketplace pins with the main branch of each skill repository."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:  # Support both ``python -m scripts.sync_plugins`` and direct execution.
    from .marketplace import (
        DEFAULT_TIMEOUT,
        ManifestValidationError,
        MarketplaceError,
        RemoteLookupError,
        sync_manifest,
    )
except ImportError:  # pragma: no cover - exercised only by direct script execution.
    from marketplace import (
        DEFAULT_TIMEOUT,
        ManifestValidationError,
        MarketplaceError,
        RemoteLookupError,
        sync_manifest,
    )


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"path to marketplace.json (default: {DEFAULT_MANIFEST})",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"timeout per remote lookup (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="resolve remote pins without writing; exit 1 when any pin is stale",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve remote pins and print changes without writing",
    )
    return parser


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def main(argv: list[str] | None = None, *, lookup=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        updates = sync_manifest(
            args.manifest,
            lookup=lookup,
            timeout=args.timeout,
            dry_run=args.dry_run,
            check=args.check,
        )
    except ManifestValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RemoteLookupError as exc:
        print(f"remote synchronization failed: {exc}", file=sys.stderr)
        return 3
    except (OSError, ValueError, MarketplaceError) as exc:
        print(f"synchronization failed: {exc}", file=sys.stderr)
        return 2

    for name, old_sha, new_sha in updates:
        print(f"{name}: {old_sha[:10]} -> {new_sha[:10]}")

    if not updates:
        print("all pins up to date")
    elif args.check:
        print("stale pins found; manifest was not changed")
        return 1
    elif args.dry_run:
        print("dry run; manifest was not changed")
    else:
        print("pins updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
