kind create cluster --name diploma --config kind-config.yaml --kubeconfig ./.diploma-cluster-kubeconfig

helmfile cache cleanup && helmfile -f deploy/helmfile.yaml.gotmpl apply