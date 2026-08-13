---
slug: marketplace-hardening
created: 2026-08-13
status: completed
phases:
  - id: P1
    scope: "Refactor marketplace validation and pin synchronization; add unit tests"
    status: completed
  - id: P2
    scope: "Strengthen CI and change scheduled synchronization to reviewable pull requests"
    status: completed
  - id: P3
    scope: "Refresh README and GitHub Pages copy; add local documentation drift checks"
    status: completed
---

# Marketplace hardening

## Goal

Make the Damascus Ink marketplace safe to maintain and easy to verify: malformed or stale pins must be detected deterministically, scheduled updates must be reviewable before entering `main`, and the public documentation must not silently drift from the marketplace manifest.

## Current evidence

- `.claude-plugin/marketplace.json` is the catalog and contains three URL sources pinned by SHA.
- `scripts/sync_plugins.py` queries `refs/heads/main` and writes changed pins, but has no local validation command, timeout, unit tests, or aggregated failure handling.
- `.github/workflows/sync.yml` commits and pushes generated changes directly to `main`.
- `.github/workflows/ci.yml` contains an inline, shallow manifest check and no test suite.
- `README.md` and `docs/index.html` repeat plugin names and maintenance behavior manually.

## Global constraints

- Preserve the Anthropic marketplace manifest shape and the existing three plugin names, source URLs, SHAs, homepages, and user-facing install commands unless a test-proven bug requires otherwise.
- Do not vendor third-party skill repositories into this catalog.
- Do not make network calls from unit tests; remote lookups must be injectable or mocked at the process boundary.
- Do not push, force-push, auto-merge, or amend commits from the implementation task.
- Scheduled synchronization may create/update a reviewable PR, but it must not write directly to `main`.
- Keep the implementation dependency-free beyond the Python standard library and existing GitHub-hosted runner tools.
- Keep generated workflow artifacts and the review ledger out of the production diff unless the repository explicitly adopts them.

## Phases

### P1 — validation, synchronization, and tests

Files:

- `scripts/marketplace.py` (new shared validation and synchronization library, if needed by the implementation)
- `scripts/validate_marketplace.py` (new local manifest validator CLI)
- `scripts/sync_plugins.py`
- `scripts/__init__.py` (only if required for clean imports)
- `tests/test_marketplace.py` (new)
- `tests/test_sync_plugins.py` (new)

Consumes:

- `.claude-plugin/marketplace.json`
- The current GitHub `refs/heads/main` lookup behavior

Produces:

- Strict validation of top-level metadata, plugin uniqueness, canonical GitHub URLs, non-empty descriptions/homepages, and lowercase 40-character commit SHAs.
- A local-only validation mode suitable for CI.
- A synchronization CLI with explicit non-writing `--check` and/or `--dry-run` semantics, configurable positive timeout, deterministic output, and nonzero exit codes for stale pins and operational failures.
- No manifest write unless every required remote lookup succeeds; writes should be atomic where practical.
- Unit tests covering valid/invalid manifests, duplicate names, malformed SHAs/URLs, stale pins, dry-run/check behavior, subprocess failure, timeout, and the no-partial-write invariant.

Contracts:

- `validate_manifest(manifest)` returns structured validation errors or raises a documented validation exception; it must not access the network.
- `head_of(url, ref="refs/heads/main", timeout=...)` returns one commit SHA or raises a typed operational error; it must not call `sys.exit`.
- The CLI distinguishes validation failure, stale pins, and remote/process failure with stable nonzero exit statuses documented in `--help`.

Acceptance criteria:

- `python scripts/validate_marketplace.py` passes against the current manifest.
- `python -m unittest discover -s tests -p "test_*.py" -v` runs without network access and passes.
- A simulated failed lookup leaves the manifest byte-for-byte unchanged.
- `--dry-run` never writes; `--check` never writes and reports stale pins with a nonzero status.

Risks:

- Tightening validation may reject future marketplace entries; document the accepted URL/manifest contract and keep the validator focused on the catalog's declared policy.
- Python import layout can become fragile if scripts are tested only from the repository root; tests must exercise the same invocation style used by CI.

Non-goals:

- Downloading, executing, or semantically auditing skill contents.
- Replacing the marketplace schema with a custom format.

### P2 — CI and release safety

Files:

- `.github/workflows/ci.yml`
- `.github/workflows/sync.yml`

Consumes:

- P1 CLIs and tests
- GitHub Actions `GITHUB_TOKEN` and the repository's `main` branch

Produces:

- CI that runs the shared validator and complete Python test suite with read-only repository permissions.
- Scheduled/manual synchronization that creates a uniquely named automation branch and reviewable PR only when pins change, avoids duplicate open sync PRs, and never directly pushes generated changes to `main`.
- Explicit concurrency control and least-privilege workflow permissions.

Acceptance criteria:

- CI invokes the same validator and test commands documented for local development.
- The sync workflow has no direct `git push` to `main` and no auto-merge behavior.
- A no-change run exits successfully without creating a commit or PR.
- A changed-pin run has enough permissions to push its automation branch and open a PR, while ordinary CI remains read-only.

Risks:

- GitHub-hosted runner availability or CLI behavior can differ from local Windows behavior; keep repository mutation in a small, auditable shell step and validate YAML structure in review.
- An existing open automation PR can make a later run redundant; use a stable detectable branch prefix/search and concurrency protection.

Non-goals:

- Automatically approving or merging dependency/source updates.
- Adding third-party Actions solely for PR creation when the runner's existing tooling is sufficient.

### P3 — documentation and drift prevention

Files:

- `README.md`
- `docs/index.html`
- `scripts/validate_marketplace.py` or `scripts/check_docs.py` (only one mechanism; prefer reuse of P1 validation code)
- `tests/test_marketplace.py`

Consumes:

- Manifest plugin names, canonical URLs, and maintenance workflow from P1/P2

Produces:

- Maintainer-facing documentation describing validation, local sync/check commands, and the reviewable-PR release flow.
- Public copy that no longer claims scheduled updates land directly in the catalog.
- A deterministic local check that every manifest plugin name and canonical repository link appears in the maintained public docs, without requiring network access.

Acceptance criteria:

- README and site agree that pin changes require review/merge.
- Documentation contains working commands for local validation and test execution.
- Removing a plugin name or canonical link from either maintained document makes the docs check fail.

Risks:

- Text-presence checks can be too shallow; limit them to stable identifiers and URLs, and keep prose review human-owned.
- The static site embeds a large font asset; avoid unrelated visual rewrites.

Non-goals:

- Building a new static-site generator.
- Automatically rewriting prose or legal disclaimers from JSON.

## Verification strategy

Run after each phase as applicable:

```text
python scripts/validate_marketplace.py
python -m unittest discover -s tests -p "test_*.py" -v
git diff --check
```

For P2, inspect the final workflow diff for permissions, branch targets, duplicate-PR behavior, and absence of direct pushes to `main`. For final review, verify all accepted findings are closed in the transient ledger and that the current manifest still parses and satisfies the validator.

## Final acceptance

- All three phases are complete.
- The manifest is unchanged except for intentional, reviewable metadata changes.
- Tests cover all new behavior and pass locally with no network dependency.
- CI and scheduled sync behavior match the documented security model.
- README and Pages copy are consistent with the actual workflow.
