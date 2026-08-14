import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.sync_plugins import main as sync_main
from scripts.validate_marketplace import check_documentation, main as validate_main

from test_marketplace import manifest_with


class CliTests(unittest.TestCase):
    def write_manifest(self, directory, manifest):
        path = Path(directory) / "marketplace.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_validator_cli_accepts_valid_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(directory, manifest_with())

            self.assertEqual(validate_main(["--manifest", str(path)]), 0)

    def test_validator_cli_rejects_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = manifest_with()
            manifest["plugins"][0]["source"]["sha"] = "bad"
            path = self.write_manifest(directory, manifest)

            with redirect_stderr(StringIO()):
                self.assertEqual(validate_main(["--manifest", str(path)]), 1)

    def test_sync_cli_returns_stale_status_for_check_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(directory, manifest_with())

            with redirect_stdout(StringIO()):
                result = sync_main(
                    ["--manifest", str(path), "--check"],
                    lookup=lambda url, timeout: "b" * 40,
                )

            self.assertEqual(result, 1)

    def test_documentation_check_reports_missing_plugin(self):
        manifest = manifest_with(names=("pravo-grammatika", "pravo-logika"))
        self.assertEqual(
            check_documentation(
                manifest,
                ["pravo-grammatika https://github.com/sky-magenta/pravo-grammatika"],
            ),
            ["pravo-logika"],
        )

    def test_documentation_check_requires_each_document_to_contain_each_plugin(self):
        manifest = manifest_with()

        self.assertEqual(
            check_documentation(
                manifest,
                [
                    "pravo-grammatika https://github.com/sky-magenta/pravo-grammatika",
                    "pravo-grammatika without its canonical link",
                ],
            ),
            ["pravo-grammatika"],
        )


if __name__ == "__main__":
    unittest.main()
