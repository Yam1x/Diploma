import logging
import os
import re
import subprocess
from pathlib import Path

import boto3


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [db-restorer] %(message)s",
)
logger = logging.getLogger(__name__)
UNSUPPORTED_SET_RE = re.compile(r"^\s*SET\s+([A-Za-z_][A-Za-z0-9_]*)\s*=")


def main():
    prefix = os.getenv("DB_BACKUPS_FILENAME_PREFIX", "").strip()
    backup_file = Path("/tmp/db-restore.backup")

    source_s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("SOURCE_DB_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("SOURCE_DB_AWS_SECRET_ACCESS_KEY"),
        endpoint_url=os.getenv("SOURCE_DB_AWS_ENDPOINT"),
    )

    bucket_name = os.getenv("SOURCE_DB_AWS_BUCKET_NAME", "")
    target_host = os.getenv("TARGET_DATABASE_HOST", "")
    target_db = os.getenv("TARGET_DATABASE_NAME", "")
    target_user = os.getenv("TARGET_DATABASE_USERNAME", "")
    target_password = os.getenv("TARGET_DATABASE_PASSWORD", "")

    latest_key = resolve_latest_backup_key(source_s3, bucket_name, prefix)
    logger.info("Selected backup %s from bucket %s", latest_key, bucket_name)

    backup_file.parent.mkdir(parents=True, exist_ok=True)
    source_s3.download_file(bucket_name, latest_key, str(backup_file))
    logger.info("Downloaded backup to %s", backup_file)

    env = os.environ.copy()
    env["PGPASSWORD"] = target_password

    reset_public_schema(target_host, target_db, target_user, env)
    restore_file = sanitize_backup_for_target(target_host, target_db, target_user, backup_file, env)
    restore_backup(target_host, target_db, target_user, restore_file, env)

    backup_file.unlink(missing_ok=True)
    if restore_file != backup_file:
        restore_file.unlink(missing_ok=True)
    logger.info("Database restore finished")


def resolve_latest_backup_key(s3, bucket_name: str, prefix: str) -> str:
    continuation_token = None
    matching_keys: list[str] = []

    while True:
        params = {"Bucket": bucket_name, "MaxKeys": 1000}
        if prefix:
            params["Prefix"] = prefix
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**params)
        for item in response.get("Contents", []):
            key = str(item.get("Key", ""))
            if key.endswith(".backup") and key.startswith(prefix):
                matching_keys.append(key)

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
        if not continuation_token:
            break

    if not matching_keys:
        raise RuntimeError(f"No backup objects found in bucket {bucket_name} for prefix '{prefix}'")

    return max(matching_keys)


def reset_public_schema(host: str, db_name: str, username: str, env: dict[str, str]) -> None:
    logger.info("Resetting public schema in database %s", db_name)
    subprocess.run(
        [
            "psql",
            "-h",
            host,
            "-U",
            username,
            "-d",
            db_name,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO PUBLIC;",
        ],
        check=True,
        env=env,
    )


def fetch_supported_settings(host: str, db_name: str, username: str, env: dict[str, str]) -> set[str]:
    result = subprocess.run(
        [
            "psql",
            "-h",
            host,
            "-U",
            username,
            "-d",
            db_name,
            "-tAc",
            "SELECT name FROM pg_settings",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def sanitize_backup_for_target(host: str, db_name: str, username: str, backup_file: Path, env: dict[str, str]) -> Path:
    supported_settings = fetch_supported_settings(host, db_name, username, env)
    sanitized_file = backup_file.with_suffix(".sanitized.sql")
    removed_settings: set[str] = set()
    changed = False

    with backup_file.open("r", encoding="utf-8") as source, sanitized_file.open("w", encoding="utf-8") as target:
        for line in source:
            match = UNSUPPORTED_SET_RE.match(line)
            if match and match.group(1) not in supported_settings:
                removed_settings.add(match.group(1))
                changed = True
                continue
            target.write(line)

    if not changed:
        sanitized_file.unlink(missing_ok=True)
        return backup_file

    logger.warning(
        "Removed unsupported PostgreSQL settings from dump before restore: %s",
        ", ".join(sorted(removed_settings)),
    )
    return sanitized_file


def restore_backup(host: str, db_name: str, username: str, backup_file: Path, env: dict[str, str]) -> None:
    logger.info("Applying backup %s into database %s", backup_file.name, db_name)
    subprocess.run(
        [
            "psql",
            "-h",
            host,
            "-U",
            username,
            "-d",
            db_name,
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            str(backup_file),
        ],
        check=True,
        env=env,
    )


if __name__ == "__main__":
    main()
