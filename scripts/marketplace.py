"""Shared validation and synchronization logic for marketplace metadata."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_OWNER = "sky-magenta"
DEFAULT_MARKETPLACE_NAME = "damascus-ink"
DEFAULT_TIMEOUT = 30


class MarketplaceError(Exception):
    """Base class for expected marketplace maintenance failures."""


class ManifestValidationError(MarketplaceError):
    """Raised when the catalog does not satisfy the repository policy."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(errors)
        super().__init__("manifest validation failed: " + "; ".join(self.errors))


class RemoteLookupError(MarketplaceError):
    """Raised when a remote repository head cannot be resolved."""


def load_manifest(path: Path | str) -> dict[str, Any]:
    """Load a UTF-8 JSON marketplace manifest."""

    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_manifest(
    manifest: Any,
    *,
    owner: str = DEFAULT_OWNER,
    marketplace_name: str = DEFAULT_MARKETPLACE_NAME,
) -> list[str]:
    """Return human-readable policy violations without accessing the network."""

    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["top-level value must be an object"]

    if manifest.get("name") != marketplace_name:
        errors.append(f"name must be {marketplace_name!r}")

    plugins = manifest.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        return errors + ["plugins must be a non-empty list"]

    names: list[str] = []
    for index, plugin in enumerate(plugins):
        prefix = f"plugins[{index}]"
        if not isinstance(plugin, dict):
            errors.append(f"{prefix} must be an object")
            continue

        name = plugin.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix}.name must be a non-empty string")
            continue
        names.append(name)

        description = plugin.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append(f"{prefix}.description must be a non-empty string")

        homepage = plugin.get("homepage")
        if not isinstance(homepage, str) or not homepage.startswith("https://"):
            errors.append(f"{prefix}.homepage must be an https URL")

        source = plugin.get("source")
        if not isinstance(source, dict):
            errors.append(f"{prefix}.source must be an object")
            continue
        if source.get("source") != "url":
            errors.append(f"{prefix}.source.source must be 'url'")

        expected_url = f"https://github.com/{owner}/{name}.git"
        if source.get("url") != expected_url:
            errors.append(f"{prefix}.source.url must be {expected_url}")

        sha = source.get("sha")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            errors.append(f"{prefix}.source.sha must be 40 lowercase hexadecimal characters")

    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        errors.append("duplicate plugin names: " + ", ".join(duplicates))

    return errors


def head_of(
    url: str,
    *,
    ref: str = "refs/heads/main",
    timeout: int = DEFAULT_TIMEOUT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Resolve a remote branch to a commit SHA using ``git ls-remote``."""

    try:
        result = runner(
            ["git", "ls-remote", url, ref],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RemoteLookupError(f"timed out after {timeout}s while reading {url}") from exc
    except OSError as exc:
        raise RemoteLookupError(f"could not run git for {url}: {exc}") from exc

    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.strip() or "no matching remote ref"
        raise RemoteLookupError(f"failed to resolve {url} ({ref}): {detail}")

    fields = result.stdout.split()
    sha = fields[0] if fields else ""
    if not SHA_RE.fullmatch(sha):
        raise RemoteLookupError(f"remote returned an invalid commit SHA for {url}: {sha!r}")
    return sha


def sync_manifest(
    path: Path | str,
    *,
    lookup: Callable[[str, int], str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    dry_run: bool = False,
    check: bool = False,
) -> list[tuple[str, str, str]]:
    """Resolve all pins and optionally atomically update the manifest.

    All remote lookups complete before any write. ``check`` and ``dry_run``
    both guarantee that the manifest is left unchanged; callers distinguish
    them through their CLI exit policy.
    """

    manifest_path = Path(path)
    manifest = load_manifest(manifest_path)
    validation_errors = validate_manifest(manifest)
    if validation_errors:
        raise ManifestValidationError(validation_errors)

    resolver = lookup or (lambda url, limit: head_of(url, timeout=limit))
    updates: list[tuple[str, str, str]] = []
    failures: list[str] = []

    for plugin in manifest["plugins"]:
        name = plugin["name"]
        url = plugin["source"]["url"]
        old_sha = plugin["source"]["sha"]
        try:
            new_sha = resolver(url, timeout)
        except RemoteLookupError as exc:
            failures.append(f"{name}: {exc}")
            continue
        if not isinstance(new_sha, str) or not SHA_RE.fullmatch(new_sha):
            failures.append(f"{name}: lookup returned an invalid commit SHA {new_sha!r}")
            continue
        if new_sha != old_sha:
            updates.append((name, old_sha, new_sha))

    if failures:
        raise RemoteLookupError("; ".join(failures))

    if updates and not dry_run and not check:
        updated = json.loads(json.dumps(manifest, ensure_ascii=False))
        by_name = {name: new_sha for name, _, new_sha in updates}
        for plugin in updated["plugins"]:
            if plugin["name"] in by_name:
                plugin["source"]["sha"] = by_name[plugin["name"]]
        _atomic_write_json(manifest_path, updated)

    return updates


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Write JSON beside the target and replace it atomically."""

    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
