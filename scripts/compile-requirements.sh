#!/usr/bin/env bash
# Regenera requirements.txt (com hashes) a partir de requirements.in.
# Usa pip-compile dentro da mesma imagem fixada por digest no Dockerfile,
# para que o resultado seja reproduzivel (Python 3.11, Linux).
# Uso (na raiz do repositorio): scripts/compile-requirements.sh
set -euo pipefail

IMAGE="python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker run --rm -v "${ROOT}:/work" -w /work "${IMAGE}" sh -c '
  pip install --quiet --no-cache-dir pip-tools &&
  pip-compile --quiet --generate-hashes --allow-unsafe --strip-extras \
    --output-file=requirements.txt requirements.in
'
