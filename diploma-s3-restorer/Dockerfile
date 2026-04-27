FROM python:3.9-alpine

WORKDIR /app
COPY s3-restore.py .

RUN apk --update add \
    python3 \
    py3-pip \
    && pip3 install --upgrade pip \
    && pip install boto3==1.35.41

CMD ["python", "s3-restore.py"]
