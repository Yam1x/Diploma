FROM alpine:3.22.0

COPY synchronizer.py .

ARG TARGETARCH

# install curl
RUN apk add curl

# install kind https://kind.sigs.k8s.io/docs/user/quick-start/#installing-from-release-binaries
# curl -Lo - follow redirects and write to file
# chmod +x - make file executable
RUN curl -Lo /usr/local/bin/kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-$TARGETARCH && \
    chmod +x /usr/local/bin/kind

# install git
RUN apk add git

# install helm https://kind.sigs.k8s.io/docs/user/quick-start/#installing-from-release-binaries
# curl -o - write to file
# chmod +x - make file executable
RUN curl -L https://get.helm.sh/helm-v3.14.4-linux-$TARGETARCH.tar.gz | tar xz &&\
    mv linux-$TARGETARCH/helm /usr/local/bin/helm && \
    chmod +x /usr/local/bin/helm

# install helm-diff plugin
RUN helm plugin install https://github.com/databus23/helm-diff --version=3.9.6

# install helm-git plugin
RUN helm plugin install https://github.com/aslafy-z/helm-git --version 1.3.0

# install helmfile https://github.com/schlich/devcontainer-features/blob/main/src/helmfile/install.sh
# curl -L - follow redirects
# chmod +x - make file executable
RUN curl -L https://github.com/helmfile/helmfile/releases/download/v0.164.0/helmfile_0.164.0_linux_$TARGETARCH.tar.gz | tar xz && \
    chmod +x helmfile && \
    mv helmfile /usr/local/bin

# install kubectl https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/#install-kubectl-binary-with-curl-on-linux
# curl -Lo - follow redirects and write to file
# chmod +x - make file executable
RUN curl -Lo kubectl https://dl.k8s.io/release/v1.30.0/bin/linux/$TARGETARCH/kubectl && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin

# install python
RUN apk add python3

# install yq
RUN apk add yq

# install envsubst
RUN apk add envsubst

# Clone local env and apply helmfile
CMD ["python", "synchronizer.py"]