"""Protect the human-readable repository layout and its tool references."""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote


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

    def test_documentation_is_grouped_by_reader_need(self) -> None:
        expected = (
            "docs/product/project-plan.md",
            "docs/product/project-history.md",
            "docs/product/dashboard.md",
            "docs/architecture/api.md",
            "docs/architecture/postgresql.md",
            "docs/architecture/cloud-run.md",
            "docs/analysis/sentiment-evaluation.md",
            "docs/analysis/topic-analysis.md",
            "docs/analysis/anomaly-detection.md",
            "docs/operations/google-cloud-runbook.md",
            "docs/reference/repository-guide.md",
            "docs/decisions/0001-cloud-datastore.md",
        )
        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).is_file())

        for category in (
            "product",
            "architecture",
            "analysis",
            "operations",
            "reference",
            "decisions",
        ):
            with self.subTest(category=category):
                self.assertTrue((PROJECT_ROOT / "docs" / category / "README.md").is_file())

    def test_relative_markdown_links_resolve(self) -> None:
        link_pattern = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
        failures: list[str] = []

        for markdown_file in PROJECT_ROOT.rglob("*.md"):
            text = markdown_file.read_text(encoding="utf-8")
            for raw_target in link_pattern.findall(text):
                target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                relative_target = unquote(target.split("#", 1)[0].split("?", 1)[0])
                resolved = (markdown_file.parent / relative_target).resolve()
                if not resolved.exists():
                    failures.append(
                        f"{markdown_file.relative_to(PROJECT_ROOT)} -> {target}"
                    )

        self.assertEqual(failures, [], "Broken Markdown links:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
