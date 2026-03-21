FROM python:3.9-alpine

WORKDIR /app
COPY s3-backup.py .

RUN apk --update add \
    python3 \
    py3-pip \
    curl \
    && pip3 install --upgrade pip \
    && pip3 install awscli \
    && pip install boto3==1.35.41

CMD ["python", "s3-backup.py"]
