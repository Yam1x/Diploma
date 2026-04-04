import os
import logging
import subprocess
import boto3
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [db-backupper] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    backup_filename = (
        os.getenv("DB_BACKUPS_FILENAME_PREFIX")
        + "-"
        + datetime.strftime(datetime.utcnow(), "%Y-%m-%dT%H-%M-%S")
        + ".backup"
    )
    bucket_name = os.getenv("DESTINATION_DB_AWS_BUCKET_NAME")

    logger.info("Starting database backup into file %s", backup_filename)
    with open(backup_filename, "wb") as backup_file:
        subprocess.run(
            [
                "pg_dump",
                "-h",
                os.getenv("DATABASE_HOST", ""),
                "-U",
                os.getenv("DATABASE_USERNAME", ""),
                "--encoding",
                "UTF8",
                "--format",
                "plain",
                os.getenv("DATABASE_NAME", ""),
            ],
            check=True,
            stdout=backup_file,
        )

    if os.path.exists(backup_filename):
        logger.info("Database dump created, uploading %s to bucket %s", backup_filename, bucket_name)
        upload_to_s3(backup_filename)
        os.remove(backup_filename)
        logger.info("Backup %s uploaded and removed from local disk", backup_filename)

    else:
        logger.error("Backup file was not created: %s", backup_filename)
        raise Exception("No such file: '%s'" % (backup_filename))


def upload_to_s3(backup_filename):

    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('DESTINATION_DB_AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('DESTINATION_DB_AWS_SECRET_ACCESS_KEY'),
        endpoint_url=os.getenv('DESTINATION_DB_AWS_ENDPOINT'),
    )

    bucket_name = os.getenv('DESTINATION_DB_AWS_BUCKET_NAME')


    with open(backup_filename, "rb") as data:
        s3.upload_fileobj(data, bucket_name, backup_filename)
    logger.info("Uploaded %s to bucket %s", backup_filename, bucket_name)

if __name__ == '__main__':

    main()
