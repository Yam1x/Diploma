#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLUSTER_NAME="diploma"
TEMP_DOCKER_CONFIG="$(mktemp -d)"

cleanup() {
  rm -rf "${TEMP_DOCKER_CONFIG}"
}

trap cleanup EXIT

printf '{}' > "${TEMP_DOCKER_CONFIG}/config.json"
export DOCKER_CONFIG="${TEMP_DOCKER_CONFIG}"

IMAGES=(
  "ghcr.io/yam1x/diploma-orchestrator-api:latest|apps/orchestrator-api/Dockerfile|."
  "ghcr.io/yam1x/diploma-orchestrator-ui:latest|apps/orchestrator-ui/Dockerfile|."
  "ghcr.io/yam1x/diploma-demo-api:latest|apps/demo-api/Dockerfile|."
  "ghcr.io/yam1x/diploma-db-backupper:latest|diploma-db-backupper/Dockerfile|diploma-db-backupper"
  "ghcr.io/yam1x/diploma-db-restorer:latest|diploma-db-restorer/Dockerfile|diploma-db-restorer"
  "ghcr.io/yam1x/diploma-s3-backupper:latest|diploma-s3-backupper/Dockerfile|diploma-s3-backupper"
  "ghcr.io/yam1x/diploma-s3-restorer:latest|diploma-s3-restorer/Dockerfile|diploma-s3-restorer"
  "ghcr.io/yam1x/diploma-env-backupper:latest|diploma-env-backupper/Dockerfile|diploma-env-backupper"
  "ghcr.io/yam1x/diploma-env-restorer:latest|diploma-env-restorer/Dockerfile|diploma-env-restorer"
  "ghcr.io/yam1x/diploma-env-synchronizer:latest|diploma-env-synchronizer/Dockerfile|diploma-env-synchronizer"
)

BUILT_IMAGES=()

for tool in docker kind; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "Required tool '${tool}' was not found in PATH." >&2
    exit 1
  fi
done

for entry in "${IMAGES[@]}"; do
  IFS="|" read -r image dockerfile context <<< "${entry}"
  dockerfile_path="${REPO_ROOT}/${dockerfile}"
  build_context="${REPO_ROOT}/${context}"

  if [[ ! -f "${dockerfile_path}" ]]; then
    echo "Dockerfile not found: ${dockerfile_path}" >&2
    exit 1
  fi

  if [[ ! -d "${build_context}" ]]; then
    echo "Build context not found: ${build_context}" >&2
    exit 1
  fi

  echo "Building ${image} using ${dockerfile} with context ${context}..."
  docker build -t "${image}" -f "${dockerfile_path}" "${build_context}"

  echo "Loading ${image} into kind cluster '${CLUSTER_NAME}'..."
  kind load docker-image "${image}" --name "${CLUSTER_NAME}"

  BUILT_IMAGES+=("${image}")
done

echo
echo "Successfully built and loaded images:"
for image in "${BUILT_IMAGES[@]}"; do
  echo " - ${image}"
done
