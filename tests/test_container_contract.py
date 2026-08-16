"""Static checks for the Cloud Run service container contract."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ContainerContractTests(unittest.TestCase):
    def test_service_image_uses_cloud_run_port_and_non_root_user(self) -> None:
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("PORT=8080", dockerfile)
        self.assertIn('CMD ["stockpulse-api"]', dockerfile)
        self.assertIn("USER stockpulse", dockerfile)
        self.assertLess(
            dockerfile.index("USER stockpulse"),
            dockerfile.index('CMD ["stockpulse-api"]'),
        )
        self.assertIn("/api/v1/health", dockerfile)

    def test_container_context_excludes_secrets_and_local_data(self) -> None:
        ignored = {
            line.strip()
            for line in (PROJECT_ROOT / ".dockerignore")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith("#")
        }

        self.assertTrue({".env", ".env.*", "data", "*.db", "raw*.json"} <= ignored)


if __name__ == "__main__":
    unittest.main()
