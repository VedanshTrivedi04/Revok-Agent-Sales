#!/usr/bin/env bash
# Usage: bash scripts/run_live_suites.sh <tag> <suite> [<suite> ...]   (sequential: one GPU, latency numbers need an idle endpoint)
TAG="$1"; shift
cd "$(dirname "$0")/.."
LOG="evals/live/$TAG.log"; : > "$LOG"
for s in "$@"; do
  echo "== suite $s $(date +%T)" | tee -a "$LOG"
  uv run python -m revops_ai.evals.run --suite "$s" --live --tag "$TAG" 2>&1 | grep -v llm_call | tail -n 400 >> "$LOG"
done
echo "== DONE $(date +%T)" | tee -a "$LOG"
