FROM python:3.9-alpine

WORKDIR /app
COPY db-restore.py .

RUN apk --update add \
    postgresql-client \
    python3 \
    py3-pip \
    && pip3 install --upgrade pip \
    && pip install boto3==1.35.41

CMD ["python", "db-restore.py"]
