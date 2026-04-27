import logging
import os
import subprocess
from pathlib import Path

import boto3


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [db-restorer] %(message)s",
)
logger = logging.getLogger(__name__)


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
    restore_backup(target_host, target_db, target_user, backup_file, env)

    backup_file.unlink(missing_ok=True)
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
