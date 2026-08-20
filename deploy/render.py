"""Render reviewed Cloud Run deployment contracts without contacting Google Cloud."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


HERE = Path(__file__).resolve().parent
ALLOWED_REGIONS = frozenset({"us-west1", "us-west2"})
APPROVED_SCHEDULES = (
    ("stockpulse-premarket-trigger", "15 9 * * 1-5"),
    ("stockpulse-afterhours-trigger", "0 18 * * 1-5"),
)
IMAGE_PATTERN = re.compile(
    r"^[a-z0-9-]+-docker\.pkg\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"[a-z0-9._-]+/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$"
)
PROJECT_PATTERN = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
SERVICE_ACCOUNT_PATTERN = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]"
    r"\.iam\.gserviceaccount\.com$"
)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_config(config: dict[str, Any]) -> None:
    """Reject placeholders, mutable images, and unapproved deployment inputs."""

    if config.get("approval_recorded") is not True:
        raise ValueError(
            "Deployment approval is not recorded; review the cloud runbook first."
        )
    project_id = str(config.get("project_id", ""))
    project_number = str(config.get("project_number", ""))
    region = str(config.get("region", ""))
    if not PROJECT_PATTERN.fullmatch(project_id):
        raise ValueError("project_id is invalid.")
    if "example" in project_id:
        raise ValueError("project_id still contains an example placeholder.")
    if not project_number.isdigit() or not 6 <= len(project_number) <= 20:
        raise ValueError("project_number must be a numeric Google Cloud project number.")
    if region not in ALLOWED_REGIONS:
        raise ValueError("region must be the reviewed us-west1 or us-west2 value.")
    if config.get("cloud_sql_connection") != f"{project_id}:{region}:stockpulse-db":
        raise ValueError("cloud_sql_connection does not match the reviewed resource name.")

    for key in ("service_image", "job_image"):
        image = str(config.get(key, ""))
        if not IMAGE_PATTERN.fullmatch(image):
            raise ValueError(f"{key} must be an Artifact Registry image by sha256 digest.")
        if image.endswith("0" * 64):
            raise ValueError(f"{key} still contains the example digest.")
        if f"/{project_id}/" not in image:
            raise ValueError(f"{key} must belong to the configured project.")

    for key in (
        "service_account",
        "job_service_account",
        "scheduler_service_account",
    ):
        email = str(config.get(key, ""))
        if not SERVICE_ACCOUNT_PATTERN.fullmatch(email) or not email.endswith(
            f"@{project_id}.iam.gserviceaccount.com"
        ):
            raise ValueError(f"{key} must be a service account in the configured project.")

    for key in (
        "database_secret_version",
        "apify_secret_version",
        "gmail_secret_version",
    ):
        version = str(config.get(key, ""))
        if not version.isdigit() or int(version) < 1:
            raise ValueError(f"{key} must be a pinned positive numeric version.")

    notification_email = str(config.get("notification_email", ""))
    if not EMAIL_PATTERN.fullmatch(notification_email) or notification_email.endswith(
        "@example.com"
    ):
        raise ValueError("notification_email must be the approved real mailbox.")
    dashboard_url = str(config.get("dashboard_url", ""))
    if not dashboard_url.startswith("https://") or ".run.app" not in dashboard_url:
        raise ValueError("dashboard_url must be the deployed HTTPS run.app URL.")

    schedules = config.get("schedules")
    if not isinstance(schedules, list) or len(schedules) != 2:
        raise ValueError("Exactly two reviewed Scheduler triggers are required.")
    actual_schedules: list[tuple[str, str]] = []
    for schedule in schedules:
        if not isinstance(schedule, dict):
            raise ValueError("Each Scheduler trigger must be an object.")
        name = str(schedule.get("name", ""))
        cron = str(schedule.get("cron", ""))
        if len(cron.split()) != 5:
            raise ValueError("Each Scheduler cron must contain five fields.")
        if schedule.get("time_zone") != "America/New_York":
            raise ValueError("Scheduler time_zone must be America/New_York.")
        actual_schedules.append((name, cron))
    if tuple(actual_schedules) != APPROVED_SCHEDULES:
        raise ValueError("Scheduler triggers do not match the owner-approved times.")


def render(config_path: Path, output_dir: Path) -> tuple[Path, ...]:
    """Render manifests and a separately reviewed Scheduler command."""

    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    replacements = {
        "PROJECT_NUMBER": str(config["project_number"]),
        "REGION": str(config["region"]),
        "CLOUD_SQL_CONNECTION": str(config["cloud_sql_connection"]),
        "SERVICE_ACCOUNT": str(config["service_account"]),
        "JOB_SERVICE_ACCOUNT": str(config["job_service_account"]),
        "SERVICE_IMAGE": str(config["service_image"]),
        "JOB_IMAGE": str(config["job_image"]),
        "DATABASE_SECRET_VERSION": str(config["database_secret_version"]),
        "APIFY_SECRET_VERSION": str(config["apify_secret_version"]),
        "GMAIL_SECRET_VERSION": str(config["gmail_secret_version"]),
        "NOTIFICATION_EMAIL": str(config["notification_email"]),
        "DASHBOARD_URL": str(config["dashboard_url"]),
        "CLOUD_RUN_JOB_URL": (
            "https://console.cloud.google.com/run/jobs/details/"
            f"{config['region']}/stockpulse-daily-pipeline/executions"
            f"?project={config['project_id']}"
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for name in ("service.yaml", "job.yaml"):
        content = (HERE / f"{name}.tmpl").read_text(encoding="utf-8")
        for key, value in replacements.items():
            content = content.replace("{{" + key + "}}", value)
        if "{{" in content or "}}" in content:
            raise ValueError(f"Unresolved placeholder in {name}.")
        target = output_dir / name
        target.write_text(content, encoding="utf-8", newline="\n")
        rendered.append(target)

    for schedule in config["schedules"]:
        short_name = str(schedule["name"]).removeprefix("stockpulse-").removesuffix(
            "-trigger"
        )
        scheduler = output_dir / f"create-scheduler-{short_name}.ps1"
        scheduler.write_text(
            "# REVIEW BEFORE RUNNING: this command creates a cloud resource.\n"
            f"gcloud scheduler jobs create http {schedule['name']} `\n"
            f"  --project '{config['project_id']}' `\n"
            f"  --location '{config['region']}' `\n"
            f"  --schedule '{schedule['cron']}' `\n"
            f"  --time-zone '{schedule['time_zone']}' `\n"
            "  --uri 'https://run.googleapis.com/v2/projects/"
            f"{config['project_id']}/locations/{config['region']}/jobs/"
            "stockpulse-daily-pipeline:run' `\n"
            "  --http-method POST `\n"
            f"  --oauth-service-account-email '{config['scheduler_service_account']}' `\n"
            "  --max-retry-attempts 0\n",
            encoding="utf-8",
            newline="\n",
        )
        rendered.append(scheduler)

    manifest = output_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "project_id": config["project_id"],
                "region": config["region"],
                "service_image": config["service_image"],
                "job_image": config["job_image"],
                "files": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in rendered
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    rendered.append(manifest)
    return tuple(rendered)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("build/deployment"))
    args = parser.parse_args()
    try:
        paths = render(args.config, args.output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Deployment render stopped safely: {error}")
        return 1
    print("Rendered reviewed deployment files: " + ", ".join(str(p) for p in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
