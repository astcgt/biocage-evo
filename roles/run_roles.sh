#!/bin/bash
# Run one round of the independent roles (headless Claude, one process each, own permissions). usage: roles/run_roles.sh <round> <role...>
cd "$(dirname "$0")/.."
R=$(printf "r%04d" "$1"); shift
MODEL=claude-opus-5-5
mkdir -p work/board/$R
for role in "$@"; do
  [ -f work/board/$R/$role.json ] && { echo "$role $R already done"; continue; }
  mkdir -p work/agents/$role work/board/$R
  # PI 2026-10-27: full tool permissions for every role. Independence comes from separate processes, separate folders
  # (work/agents/<role>/) and the governance rules, not from tool limits; each role pushes its own goal to the limit.
  allow=(Bash Read Write Edit Glob Grep WebSearch WebFetch NotebookEdit)
  prompt="$(cat roles/prompts/common.md roles/prompts/$role.md)
Round: $R. Start now."
  ( CUDA_VISIBLE_DEVICES=$(python -c "import json;print(json.load(open('config.json'))['gpu'])") claude -p "$prompt" --model $MODEL --allowed-tools "${allow[@]}" --output-format json --add-dir "$(python -c "import json;print(json.load(open('config.json'))['febio_src'])")" \
      > work/agents/$role/$R.session.json 2> work/agents/$role/$R.err
    echo "$(date -Is) $role $R exit $?" >> work/agents/rounds.log ) &
done
wait
