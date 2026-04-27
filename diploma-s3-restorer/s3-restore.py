import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import boto3


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [s3-restorer] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    prefix = os.getenv("S3_BACKUPS_FILENAME_PREFIX", "").strip()
    target_subfolder = normalize_prefix(os.getenv("TARGET_S3_AWS_BUCKET_SUBFOLDER_NAME", ""))

    source_s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("SOURCE_S3_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("SOURCE_S3_AWS_SECRET_ACCESS_KEY"),
        endpoint_url=os.getenv("SOURCE_S3_AWS_ENDPOINT"),
    )
    target_s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("TARGET_S3_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("TARGET_S3_AWS_SECRET_ACCESS_KEY"),
        endpoint_url=os.getenv("TARGET_S3_AWS_ENDPOINT"),
    )

    source_bucket = os.getenv("SOURCE_S3_AWS_BUCKET_NAME", "")
    target_bucket = os.getenv("TARGET_S3_AWS_BUCKET_NAME", "")
    latest_key = resolve_latest_backup_key(source_s3, source_bucket, prefix)
    logger.info("Selected backup %s from bucket %s", latest_key, source_bucket)

    with tempfile.TemporaryDirectory(prefix="s3-restore-") as temp_dir:
        archive_path = Path(temp_dir) / "restore.backup.zip"
        extract_dir = Path(temp_dir) / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        source_s3.download_file(source_bucket, latest_key, str(archive_path))
        logger.info("Downloaded archive to %s", archive_path)

        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(extract_dir)

        clear_target_prefix(target_s3, target_bucket, target_subfolder)
        upload_directory(target_s3, target_bucket, target_subfolder, extract_dir)

    logger.info("S3 restore finished")


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
            if key.endswith(".backup.zip") and key.startswith(prefix):
                matching_keys.append(key)

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
        if not continuation_token:
            break

    if not matching_keys:
        raise RuntimeError(f"No backup archives found in bucket {bucket_name} for prefix '{prefix}'")

    return max(matching_keys)


def clear_target_prefix(s3, bucket_name: str, prefix: str) -> None:
    logger.info("Clearing target bucket %s with prefix %s", bucket_name, prefix or "<root>")
    continuation_token = None

    while True:
        params = {"Bucket": bucket_name, "MaxKeys": 1000}
        if prefix:
            params["Prefix"] = prefix
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**params)
        objects = [{"Key": item["Key"]} for item in response.get("Contents", []) if item.get("Key")]
        if objects:
            s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects, "Quiet": True})

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
        if not continuation_token:
            break


def upload_directory(s3, bucket_name: str, prefix: str, root: Path) -> None:
    uploaded = 0
    for current_root, _, files in os.walk(root):
        for filename in files:
            path = Path(current_root) / filename
            relative_path = path.relative_to(root).as_posix()
            object_key = f"{prefix}/{relative_path}" if prefix else relative_path
            with path.open("rb") as handle:
                s3.upload_fileobj(handle, bucket_name, object_key)
            uploaded += 1
            logger.info("Uploaded restored object %s", object_key)

    if uploaded == 0:
        logger.warning("Archive did not contain any files to restore")


def normalize_prefix(value: str) -> str:
    return value.strip().strip("/")


if __name__ == "__main__":
    main()
