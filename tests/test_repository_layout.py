"""Protect the human-readable repository layout and its tool references."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_github_cannot_override_the_product_readme(self) -> None:
        self.assertTrue((PROJECT_ROOT / "README.md").is_file())
        self.assertFalse((PROJECT_ROOT / ".github" / "README.md").exists())

    def test_runtime_setup_files_are_grouped(self) -> None:
        expected = (
            "config/env.example",
            "config/requirements/base.txt",
            "config/requirements/ai.txt",
            "config/requirements/postgres.txt",
            "containers/service.Dockerfile",
            "containers/job.Dockerfile",
        )
        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).is_file())

        retired_root_files = (
            ".env.example",
            "requirements.txt",
            "requirements-ai.txt",
            "requirements-postgres.txt",
            "Dockerfile",
            "Dockerfile.job",
        )
        for filename in retired_root_files:
            with self.subTest(retired=filename):
                self.assertFalse((PROJECT_ROOT / filename).exists())

    def test_ci_uses_the_grouped_paths(self) -> None:
        workflow = (PROJECT_ROOT / ".github/workflows/tests.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("config/requirements/postgres.txt", workflow)
        self.assertIn("containers/service.Dockerfile", workflow)
        self.assertIn("containers/job.Dockerfile", workflow)

    def test_optional_requirement_sets_include_grouped_base(self) -> None:
        for filename in ("ai.txt", "postgres.txt"):
            requirements = (
                PROJECT_ROOT / "config" / "requirements" / filename
            ).read_text(encoding="utf-8")
            self.assertEqual(requirements.splitlines()[0], "-r base.txt")


if __name__ == "__main__":
    unittest.main()
