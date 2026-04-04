import boto3
import logging
import os
import shutil
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [s3-backupper] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    temp_directory_for_files_from_source = "/tmp/backup"
    bucket_subfolder_name = os.getenv('SOURCE_S3_AWS_BUCKET_SUBFOLDER_NAME') or ""

    archive_name = os.getenv('S3_BACKUPS_FILENAME_PREFIX') + '-' + datetime.strftime(datetime.utcnow(), "%Y-%m-%dT%H-%M-%S") + '.backup'
    
    source_s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('SOURCE_S3_AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('SOURCE_S3_AWS_SECRET_ACCESS_KEY'),
        endpoint_url=os.getenv('SOURCE_S3_AWS_ENDPOINT'),
    )
    
    destination_s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('DESTINATION_S3_AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('DESTINATION_S3_AWS_SECRET_ACCESS_KEY'),
        endpoint_url=os.getenv('DESTINATION_S3_AWS_ENDPOINT'),
    )

    source_bucket_name = os.getenv('SOURCE_S3_AWS_BUCKET_NAME')
    destination_bucket_name = os.getenv('DESTINATION_S3_AWS_BUCKET_NAME')

    logger.info(
        "Starting S3 backup from bucket %s to bucket %s",
        source_bucket_name,
        destination_bucket_name,
    )
    if not os.path.exists(temp_directory_for_files_from_source):
        os.mkdir(temp_directory_for_files_from_source)
        logger.info("Created temporary directory %s", temp_directory_for_files_from_source)

    downloaded_files = download_dir(
        temp_directory_for_files_from_source,
        source_bucket_name,
        source_s3,
        bucket_subfolder_name,
    )

    if not len(os.listdir(temp_directory_for_files_from_source)) == 0:
        archive_source = temp_directory_for_files_from_source
        if bucket_subfolder_name:
            archive_source = os.path.join(temp_directory_for_files_from_source, bucket_subfolder_name)

        logger.info(
            "Downloaded %s files, creating archive from %s",
            downloaded_files,
            archive_source,
        )
        shutil.make_archive(archive_name, 'zip', archive_source)

        logger.info("Uploading archive %s.zip to bucket %s", archive_name, destination_bucket_name)
        upload_to_s3(archive_name + ".zip", destination_s3, destination_bucket_name)

    else:
        logger.warning("Bucket %s is empty. Backup will not be created.", source_bucket_name)
    
    

# Reference: https://stackoverflow.com/a/56267603
def download_dir(local, bucket, client, bucket_subfolder_name):
    """
    params:
    - local: local path to folder in which to place files
    - bucket: s3 bucket with target contents
    - bucket_subfolder_name: s3 bucket subfolder (if exists)
    - client: initialized s3 client object
    """
    keys = []
    dirs = []
    base_kwargs = {'Bucket': bucket}
    if bucket_subfolder_name:
        base_kwargs['Prefix'] = bucket_subfolder_name

    kwargs = base_kwargs.copy()
    results = client.list_objects_v2(**kwargs)

    contents = results.get('Contents')

    if contents is not None:
        for i in contents:
            k = i.get('Key')
            if k[-1] != '/':
                keys.append(k)

    logger.info(
        "Found %s objects in bucket %s%s",
        len(keys),
        bucket,
        f' with prefix {bucket_subfolder_name}' if bucket_subfolder_name else "",
    )

    for k in keys:
        dest_pathname = os.path.join(local, k)      
        if not os.path.exists(os.path.dirname(dest_pathname)):
            os.makedirs(os.path.dirname(dest_pathname))

        client.download_file(bucket, k, dest_pathname)
        logger.info("Downloaded object %s", k)

    return len(keys)
    

     
def upload_to_s3(path, s3, bucket):
    with open(path, "rb") as data:
        s3.upload_fileobj(data, bucket, path)
    logger.info("Uploaded archive %s to bucket %s", path, bucket)
    
    
if __name__ == '__main__':

    main()
