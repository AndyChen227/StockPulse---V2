"""Deployment contract tests; no cloud calls are made."""

import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from deploy.render import render, validate_config  # noqa: E402


class DeploymentContractTests(unittest.TestCase):
    def config(self) -> dict[str, object]:
        digest = "a" * 64
        return {
            "approval_recorded": True,
            "project_id": "stockpulse-prod1",
            "project_number": "123456789012",
            "region": "us-west1",
            "cloud_sql_connection": "stockpulse-prod1:us-west1:stockpulse-postgres",
            "service_account": "stockpulse-service@stockpulse-prod1.iam.gserviceaccount.com",
            "job_service_account": "stockpulse-job@stockpulse-prod1.iam.gserviceaccount.com",
            "scheduler_service_account": "stockpulse-scheduler@stockpulse-prod1.iam.gserviceaccount.com",
            "database_secret_version": "3",
            "apify_secret_version": "2",
            "service_image": f"us-west1-docker.pkg.dev/stockpulse-prod1/stockpulse/service@sha256:{digest}",
            "job_image": f"us-west1-docker.pkg.dev/stockpulse-prod1/stockpulse/job@sha256:{digest}",
            "schedule": "0 14 * * *",
            "time_zone": "America/Los_Angeles",
        }

    def test_requires_recorded_approval_and_immutable_images(self) -> None:
        config = self.config()
        config["approval_recorded"] = False
        with self.assertRaisesRegex(ValueError, "approval is not recorded"):
            validate_config(config)
        config["approval_recorded"] = True
        config["service_image"] = "us-west1-docker.pkg.dev/project/repo/service:latest"
        with self.assertRaisesRegex(ValueError, "sha256 digest"):
            validate_config(config)

    def test_example_placeholders_cannot_be_rendered(self) -> None:
        example = json.loads(
            (PROJECT_ROOT / "deploy" / "config.example.json").read_text(
                encoding="utf-8"
            )
        )
        example["approval_recorded"] = True
        with self.assertRaisesRegex(ValueError, "example placeholder"):
            validate_config(example)

    def test_rejects_unreviewed_region_or_cross_project_identity(self) -> None:
        config = self.config()
        config["region"] = "us-central1"
        with self.assertRaisesRegex(ValueError, "us-west1 or us-west2"):
            validate_config(config)
        config = self.config()
        config["service_account"] = "stockpulse-service@another-project.iam.gserviceaccount.com"
        with self.assertRaisesRegex(ValueError, "configured project"):
            validate_config(config)

    def test_requires_pinned_numeric_secret_versions(self) -> None:
        config = self.config()
        config["database_secret_version"] = "latest"
        with self.assertRaisesRegex(ValueError, "pinned positive numeric"):
            validate_config(config)

    def test_rendered_contracts_are_bounded_private_and_secret_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            config_path.write_text(json.dumps(self.config()), encoding="utf-8")
            paths = render(config_path, root / "out")
            service = paths[0].read_text(encoding="utf-8")
            job = paths[1].read_text(encoding="utf-8")
            scheduler = paths[2].read_text(encoding="utf-8")
            manifest = json.loads(paths[3].read_text(encoding="utf-8"))

        self.assertIn('run.googleapis.com/iap-enabled: "true"', service)
        self.assertIn('autoscaling.knative.dev/minScale: "0"', service)
        self.assertIn('autoscaling.knative.dev/maxScale: "1"', service)
        self.assertNotIn("APIFY_API_TOKEN", service)
        self.assertIn("APIFY_API_TOKEN", job)
        self.assertIn('key: "3"', service)
        self.assertIn('key: "2"', job)
        self.assertNotIn("key: latest", service + job)
        self.assertIn("maxRetries: 0", job)
        self.assertIn('timeoutSeconds: "900"', job)
        self.assertIn("--max-retry-attempts 0", scheduler)
        self.assertIn(":run", scheduler)
        self.assertEqual(set(manifest["files"]), {
            "service.yaml", "job.yaml", "create-scheduler.ps1"
        })
        self.assertNotIn("{{", service + job + scheduler)


if __name__ == "__main__":
    unittest.main()
