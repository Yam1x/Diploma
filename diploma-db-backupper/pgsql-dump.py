import os
import boto3
from datetime import datetime


def main():

    backup_filename = os.getenv('DB_BACKUPS_FILENAME_PREFIX') + '-' + datetime.strftime(datetime.utcnow(), "%Y-%m-%dT%H-%M-%S") + '.backup'

    os.system('pg_dump -h $DATABASE_HOST -U $DATABASE_USERNAME --encoding UTF8 --format plain $DATABASE_NAME > %s' %(backup_filename))

    if os.path.exists(backup_filename):
        upload_to_s3(backup_filename)
        os.remove(backup_filename)

    else:
        raise Exception("No such file: '%s'" %(backup_filename))


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

if __name__ == '__main__':

    main()