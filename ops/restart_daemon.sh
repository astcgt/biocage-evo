#!/bin/bash
# Restart the evo daemon in its tmux session (ops/evo_daemon.sh, log work/agents/evo_daemon.log). Kept in a file so that the
# pattern below never appears in the caller's own command line (pgrep -f would otherwise kill the caller, 2026-11-08).
cd "$(dirname "$0")/.."
for p in $(pgrep -f 'ops/evo_daemon[.]sh'); do kill "$p" 2>/dev/null && echo "killed old daemon $p"; done
tmux kill-session -t evo_daemon 2>/dev/null
sleep 1
tmux new-session -d -s evo_daemon "cd '$(pwd)' && ops/evo_daemon.sh >> work/agents/evo_daemon.log 2>&1"
sleep 2
echo "tmux sessions named evo_daemon: $(tmux ls 2>/dev/null | grep -c '^evo_daemon:'); daemon processes: $(pgrep -f 'ops/evo_daemon[.]sh' | wc -l)"
