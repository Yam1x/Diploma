FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl ca-certificates git \
    && curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash \
    && curl -fsSL -o /usr/local/bin/kubectl https://dl.k8s.io/release/v1.33.4/bin/linux/amd64/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/orchestrator-api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/orchestrator-api /app
COPY diploma-db-backupper/ci /opt/diploma-charts/diploma-db-backupper/ci
COPY diploma-db-restorer/ci /opt/diploma-charts/diploma-db-restorer/ci
COPY diploma-s3-backupper/ci /opt/diploma-charts/diploma-s3-backupper/ci
COPY diploma-s3-restorer/ci /opt/diploma-charts/diploma-s3-restorer/ci
COPY diploma-env-backupper/ci /opt/diploma-charts/diploma-env-backupper/ci
COPY diploma-env-restorer/ci /opt/diploma-charts/diploma-env-restorer/ci
COPY diploma-env-synchronizer/ci /opt/diploma-charts/diploma-env-synchronizer/ci

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
