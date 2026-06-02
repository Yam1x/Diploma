kind create cluster --name diploma --config kind-config.yaml --kubeconfig ./.diploma-cluster-kubeconfig

bash ./scripts/build-local-images.sh

helmfile cache cleanup && helmfile -f deploy/helmfile.yaml.gotmpl apply

The local image build step covers only services from this repository. External Helm releases and their images still require network access:
- ingress-nginx
- bitnami/minio
- bitnami/postgresql
