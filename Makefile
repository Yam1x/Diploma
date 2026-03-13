SHELL := /bin/sh

GHCR_REGISTRY ?= ghcr.io
GHCR_OWNER ?= yam1x
API_IMAGE_NAME ?= diploma-orchestrator-api
UI_IMAGE_NAME ?= diploma-orchestrator-ui
API_IMAGE ?= $(API_IMAGE_NAME):latest
UI_IMAGE ?= $(UI_IMAGE_NAME):latest
API_IMAGE_REPOSITORY ?= $(GHCR_REGISTRY)/$(GHCR_OWNER)/$(API_IMAGE_NAME)
API_IMAGE_TAG ?= latest
UI_IMAGE_REPOSITORY ?= $(GHCR_REGISTRY)/$(GHCR_OWNER)/$(UI_IMAGE_NAME)
UI_IMAGE_TAG ?= latest
KIND_CLUSTER ?= kind
KIND_CONFIG ?= cluster/kind-config.yaml
ORCHESTRATOR_NAMESPACE ?= diploma-system

.PHONY: api-build ui-build api-test ui-test orchestrator-template orchestrator-deploy orchestrator-deploy-local kind-create kind-delete kind-load db-backupper-template

api-build:
	docker build -t $(API_IMAGE) -f apps/orchestrator-api/Dockerfile .

ui-build:
	docker build -t $(UI_IMAGE) -f apps/orchestrator-ui/Dockerfile .

api-test:
	pytest apps/orchestrator-api/tests

ui-test:
	npm --prefix apps/orchestrator-ui test

orchestrator-template:
	helmfile -f deploy/helmfile.yaml.gotmpl -e default template

orchestrator-deploy:
	API_IMAGE_REPOSITORY=$(API_IMAGE_REPOSITORY) API_IMAGE_TAG=$(API_IMAGE_TAG) UI_IMAGE_REPOSITORY=$(UI_IMAGE_REPOSITORY) UI_IMAGE_TAG=$(UI_IMAGE_TAG) ORCHESTRATOR_NAMESPACE=$(ORCHESTRATOR_NAMESPACE) helmfile -f deploy/helmfile.yaml.gotmpl -e default sync

orchestrator-deploy-local:
	API_IMAGE_REPOSITORY=$(API_IMAGE_NAME) API_IMAGE_TAG=latest UI_IMAGE_REPOSITORY=$(UI_IMAGE_NAME) UI_IMAGE_TAG=latest ORCHESTRATOR_NAMESPACE=$(ORCHESTRATOR_NAMESPACE) helmfile -f deploy/helmfile.yaml.gotmpl -e default sync

kind-create:
	kind create cluster --name $(KIND_CLUSTER) --config $(KIND_CONFIG)

kind-delete:
	kind delete cluster --name $(KIND_CLUSTER)

kind-load:
	kind load docker-image $(API_IMAGE) --name $(KIND_CLUSTER)
	kind load docker-image $(UI_IMAGE) --name $(KIND_CLUSTER)

db-backupper-template:
	helm template demo-db-backupper diploma-db-backupper/ci --namespace default
