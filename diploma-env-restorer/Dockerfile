FROM python:3.12-slim

WORKDIR /app

COPY namespace-restore.py .

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gzip tar \
    && rm -rf /var/lib/apt/lists/* \
    && arch="$(dpkg --print-architecture)" \
    && case "$arch" in amd64) kubectl_arch=amd64 ;; arm64) kubectl_arch=arm64 ;; *) echo "Unsupported architecture: $arch" && exit 1 ;; esac \
    && curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.33.1/bin/linux/${kubectl_arch}/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && pip install --no-cache-dir boto3 PyYAML

CMD ["python", "namespace-restore.py"]
