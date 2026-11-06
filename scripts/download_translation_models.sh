#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HF_HOME="$ROOT/models/hf"
mkdir -p "$HF_HOME"
models=(de fr es pt it nl ja zh)
for language in "${models[@]}"; do
  hf download "Helsinki-NLP/opus-mt-${language}-en"
done
