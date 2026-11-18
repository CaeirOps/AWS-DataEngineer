#!/usr/bin/env bash
# Regenera requirements.txt (com hashes) a partir de requirements.in.
# Usa pip-compile dentro da mesma imagem fixada por digest no Dockerfile,
# para que o resultado seja reproduzivel (Python 3.15, Linux).
# Uso (na raiz do repositorio): scripts/compile-requirements.sh
set -euo pipefail

IMAGE="python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker run --rm -v "${ROOT}:/work" -w /work "${IMAGE}" sh -c '
  pip install --quiet --no-cache-dir pip-tools &&
  pip-compile --quiet --generate-hashes --allow-unsafe --strip-extras \
    --output-file=requirements.txt requirements.in
'
