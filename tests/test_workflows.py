import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowPolicyTests(unittest.TestCase):
    def test_ci_runs_shared_validation_and_tests_with_read_only_permissions(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("contents: read", workflow)
        self.assertIn("python -m scripts.validate_marketplace --check-docs", workflow)
        self.assertIn("python -m unittest discover -s tests -p 'test_*.py' -v", workflow)

    def test_sync_workflow_creates_reviewable_pr_instead_of_direct_push(self):
        workflow = (ROOT / ".github" / "workflows" / "sync.yml").read_text(encoding="utf-8")

        self.assertIn("pull-requests: write", workflow)
        self.assertIn("gh pr create", workflow)
        self.assertNotIn("git push\n", workflow)
        self.assertNotIn("git push origin main", workflow)
        self.assertIn("concurrency:", workflow)


if __name__ == "__main__":
    unittest.main()
