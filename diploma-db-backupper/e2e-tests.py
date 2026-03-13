import boto3
import os

def main():
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('DB_AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('DB_AWS_SECRET_ACCESS_KEY'),
        endpoint_url=os.getenv('DB_AWS_ENDPOINT')
    )

    objects_list = s3.list_objects_v2(Bucket=os.getenv('DB_AWS_BUCKET_NAME'))

    # Checking that bucket isn't empty
    try:
        contents = objects_list["Contents"]

    except:
        raise Exception("Bucket is empty")

    backups = []

    for content in contents:
        if content["Key"].startswith(os.getenv('DB_BACKUPS_FILENAME_PREFIX')):
            backups.append(content)

    # Checking that database backups exists in bucket
    if len(backups) == 0:
        raise Exception("No database backups found")

    # Checking that database backup file size isn't zero 
    if backups[-1]["Size"] == 0:
        raise Exception("Backup size is 0")

if __name__ == '__main__':
    main()