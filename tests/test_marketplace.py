import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.marketplace import (
    ManifestValidationError,
    RemoteLookupError,
    head_of,
    load_manifest,
    sync_manifest,
    validate_manifest,
)


def manifest_with(*, names=("pravo-grammatika",), shas=None):
    shas = shas or {name: "a" * 40 for name in names}
    return {
        "name": "damascus-ink",
        "plugins": [
            {
                "name": name,
                "description": f"Description for {name}",
                "source": {
                    "source": "url",
                    "url": f"https://github.com/sky-magenta/{name}.git",
                    "sha": shas[name],
                },
                "homepage": f"https://sky-magenta.github.io/{name}/",
            }
            for name in names
        ],
    }


class ManifestValidationTests(unittest.TestCase):
    def test_valid_manifest_has_no_validation_errors(self):
        self.assertEqual(validate_manifest(manifest_with()), [])

    def test_duplicate_names_and_bad_sha_are_reported(self):
        manifest = manifest_with(names=("pravo-grammatika", "pravo-grammatika"))
        manifest["plugins"][1]["source"]["sha"] = "not-a-commit"

        errors = validate_manifest(manifest)

        self.assertTrue(any("duplicate" in error.lower() for error in errors))
        self.assertTrue(any("sha" in error.lower() for error in errors))


class SyncTests(unittest.TestCase):
    def write_manifest(self, directory, manifest):
        path = Path(directory) / "marketplace.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_check_reports_stale_pin_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(directory, manifest_with())
            before = path.read_bytes()

            updates = sync_manifest(
                path,
                lookup=lambda url, timeout: "b" * 40,
                check=True,
            )

            self.assertEqual(updates, [("pravo-grammatika", "a" * 40, "b" * 40)])
            self.assertEqual(path.read_bytes(), before)

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(directory, manifest_with())
            before = path.read_bytes()

            sync_manifest(path, lookup=lambda url, timeout: "b" * 40, dry_run=True)

            self.assertEqual(path.read_bytes(), before)

    def test_successful_sync_updates_all_pins_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(
                directory,
                manifest_with(names=("pravo-grammatika", "pravo-logika")),
            )

            updates = sync_manifest(path, lookup=lambda url, timeout: "b" * 40)
            saved = load_manifest(path)

            self.assertEqual(len(updates), 2)
            self.assertEqual(
                [plugin["source"]["sha"] for plugin in saved["plugins"]],
                ["b" * 40, "b" * 40],
            )

    def test_lookup_failure_does_not_write_or_hide_other_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(
                directory,
                manifest_with(names=("pravo-grammatika", "pravo-logika")),
            )
            before = path.read_bytes()

            def failing_lookup(url, timeout):
                if url.endswith("pravo-logika.git"):
                    raise RemoteLookupError(f"cannot reach {url}")
                return "b" * 40

            with self.assertRaises(RemoteLookupError) as context:
                sync_manifest(path, lookup=failing_lookup)

            self.assertIn("pravo-logika", str(context.exception))
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_manifest_is_rejected_before_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = manifest_with()
            manifest["plugins"][0]["source"]["sha"] = "bad"
            path = self.write_manifest(directory, manifest)

            with self.assertRaises(ManifestValidationError):
                sync_manifest(path, lookup=lambda url, timeout: self.fail("network called"))


class RemoteLookupTests(unittest.TestCase):
    def test_head_of_returns_sha_from_git_output(self):
        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "c" * 40 + "\trefs/heads/main\n", "")

        self.assertEqual(head_of("https://example.test/repo.git", runner=runner), "c" * 40)

    def test_head_of_converts_timeout_to_remote_error(self):
        def runner(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

        with self.assertRaises(RemoteLookupError):
            head_of("https://example.test/repo.git", runner=runner, timeout=3)


if __name__ == "__main__":
    unittest.main()
