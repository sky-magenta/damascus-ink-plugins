DONE_WITH_CONCERNS

## Scope

Implemented the planned marketplace validation/synchronization core, CI/PR safety changes, documentation drift check, and maintainer documentation. Independent delegated implementation/review contexts were unavailable after bounded waits, so implementation and controller verification were performed sequentially in the current workspace.

## Changed files

- `scripts/__init__.py`
- `scripts/marketplace.py`
- `scripts/validate_marketplace.py`
- `scripts/sync_plugins.py`
- `tests/test_marketplace.py`
- `tests/test_cli.py`
- `tests/test_workflows.py`
- `.github/workflows/ci.yml`
- `.github/workflows/sync.yml`
- `.gitignore`
- `README.md`
- `docs/index.html`

## Design decisions

- Validation is network-free and rejects malformed catalog metadata, non-canonical source URLs, duplicate names, and non-lowercase 40-character SHAs.
- Remote failures are aggregated and no manifest write occurs until every lookup succeeds.
- Writes use a temporary file in the manifest directory followed by `os.replace`.
- `--check` and `--dry-run` never write; `--check` returns status 1 for stale pins.
- Scheduled updates push an automation branch and open a reviewable PR; direct pushes to `main` were removed.
- CI reuses the same validator/test commands documented for maintainers.

## Verification

- `python -m unittest discover -s tests -p 'test_*.py' -v` — 16 tests passed.
- `python -m scripts.validate_marketplace --check-docs` — passed for all 3 plugins.
- `git diff --check` — passed.
- `python -m scripts.sync_plugins --check --timeout 1` — returned 3 because outbound GitHub access is blocked in this environment; the error listed all unreachable repositories and a SHA-256 comparison proved the manifest was unchanged.

## Concern

The remote-head freshness path and the real GitHub PR creation path cannot be exercised from this sandbox. The workflow follows the documented GitHub CLI/GITHUB_TOKEN contract and is covered locally by static policy tests, but the first GitHub Actions run should be monitored.
