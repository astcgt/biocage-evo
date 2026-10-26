#!/bin/bash
# Run one round of the independent roles (headless Claude, one process each, own permissions). usage: roles/run_roles.sh <round> <role...>
cd "$(dirname "$0")/.."
R=$(printf "r%04d" "$1"); shift
MODEL=claude-opus-5-5
for role in "$@"; do
  mkdir -p work/agents/$role work/board/$R
  allow=(Read Glob Grep WebSearch WebFetch "Write(work/agents/$role/**)" "Edit(work/agents/$role/**)"
         "Write(work/board/$R/$role.json)" "Edit(work/board/$R/$role.json)")
  [ $role = redteam ] && allow+=("Write(work/findings/**)" "Edit(work/findings/**)" "Bash(python -I work/agents/redteam/*)")
  [ $role = verifier ] && allow+=("Bash(python gpufe/gate1_patch.py work/agents/verifier/*)" "Bash(python -I work/agents/verifier/*)")
  [ $role = safety ] && allow+=("Bash(python -I work/agents/safety/*)")
  prompt="$(cat roles/prompts/common.md roles/prompts/$role.md)
Round: $R. Start now."
  ( CUDA_VISIBLE_DEVICES=$(python -c "import json;print(json.load(open('config.json'))['gpu'])") claude -p "$prompt" --model $MODEL --allowed-tools "${allow[@]}" --output-format json --add-dir "$(python -c "import json;print(json.load(open('config.json'))['febio_src'])")" \
      > work/agents/$role/$R.session.json 2> work/agents/$role/$R.err
    echo "$(date -Is) $role $R exit $?" >> work/agents/rounds.log ) &
done
wait
