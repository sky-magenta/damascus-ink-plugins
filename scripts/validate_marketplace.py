"""Validate the marketplace catalog and its stable documentation references."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable

try:  # Support both ``python -m scripts.validate_marketplace`` and direct execution.
    from .marketplace import load_manifest, validate_manifest
except ImportError:  # pragma: no cover - exercised only by direct script execution.
    from marketplace import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
DEFAULT_DOCUMENTS = (ROOT / "README.md", ROOT / "docs" / "index.html")


def check_documentation(manifest: dict[str, Any], documents: Iterable[str | Path]) -> list[str]:
    """Return plugin names missing from the supplied public documents.

    The check intentionally covers only stable identifiers and canonical
    repository links; it does not attempt to validate prose.
    """

    texts: list[str] = []
    for document in documents:
        path = Path(document)
        if path.is_file():
            texts.append(path.read_text(encoding="utf-8"))
        else:
            texts.append(str(document))

    if not texts:
        return [plugin["name"] for plugin in manifest.get("plugins", [])]

    missing: list[str] = []
    for plugin in manifest.get("plugins", []):
        name = plugin["name"]
        canonical_url = f"https://github.com/sky-magenta/{name}"
        if any(name not in text or canonical_url not in text for text in texts):
            missing.append(name)
    return missing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"path to marketplace.json (default: {DEFAULT_MANIFEST})",
    )
    parser.add_argument(
        "--check-docs",
        action="store_true",
        help="also require each plugin name and canonical GitHub link in README and docs/index.html",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
    except (OSError, ValueError) as exc:
        print(f"manifest cannot be read: {exc}", file=sys.stderr)
        return 1

    errors = validate_manifest(manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.check_docs:
        missing = check_documentation(manifest, DEFAULT_DOCUMENTS)
        if missing:
            print("ERROR: documentation is missing: " + ", ".join(missing), file=sys.stderr)
            return 1

    print(f"marketplace.json OK: {len(manifest['plugins'])} plugins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
