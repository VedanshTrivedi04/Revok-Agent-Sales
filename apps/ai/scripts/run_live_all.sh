#!/usr/bin/env bash
# Runs every live eval against the endpoint in .env and logs to evals/live/. Usage: bash scripts/run_live_all.sh <tag>
TAG="${1:-live}"
cd "$(dirname "$0")/.."
LOG="evals/live/$TAG.log"
: > "$LOG"
echo "== smoke_structured (n=10) $(date +%T)" | tee -a "$LOG"
uv run python scripts/smoke_structured.py --n 10 2>&1 | grep -v llm_call | tee -a "$LOG"
for s in t1 t2 t3 e2e; do
  echo "== suite $s $(date +%T)" | tee -a "$LOG"
  uv run python -m revops_ai.evals.run --suite $s --live --tag "$TAG" 2>&1 | grep -v llm_call | tee -a "$LOG"
done
echo "== DONE $(date +%T)" | tee -a "$LOG"
