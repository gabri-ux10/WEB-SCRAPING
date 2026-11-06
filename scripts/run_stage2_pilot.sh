#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing .env. Restore required keys by key only; do not overwrite the file." >&2
  exit 2
fi
cd "$ROOT"
python -m app.v2.local_runner
