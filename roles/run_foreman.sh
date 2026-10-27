#!/bin/bash
# One foreman pass (headless Claude, own process, full tools). Called by ops/evo_daemon.sh every 30 min; skips if one is running.
cd "$(dirname "$0")/.."
ps -u "$(id -u)" -o args | grep -q "^claude -p You are the FOREMAN" && exit 0
mkdir -p work/agents/foreman; ts=$(date +%Y%m%d_%H%M)
claude -p "$(cat roles/prompts/foreman.md)" --model claude-opus-5-5 \
  --allowed-tools Bash Read Write Edit Glob Grep --output-format json \
  --add-dir "/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1" \
  > work/agents/foreman/$ts.session.json 2> work/agents/foreman/$ts.err
echo "$(date -Is) foreman exit $?" >> work/agents/rounds.log
