#!/bin/bash
# Bring all unattended BIOCAGE work back after a Jupyter server stop / cull (which kills every process of this account).
# Idempotent: starts only what is not already running. Called by ~/.jupyter/jupyter_server_config.py at every server start.
OLD="/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1"
EVO="$(cd "$(dirname "$0")/.." && pwd)"
tmux has-session -t biocage_watchdog 2>/dev/null || tmux new-session -d -s biocage_watchdog "cd '$OLD' && python scripts/5_compute/h23_watchdog.py 2>> human_study/watchdog.err"
tmux has-session -t evo_daemon 2>/dev/null || tmux new-session -d -s evo_daemon "cd '$EVO' && ops/evo_daemon.sh >> work/agents/evo_daemon.log 2>&1"
[ -f "$OLD/human_study/al_v2/physio_v3_prerun.done" ] || tmux has-session -t biocage_physio_v3 2>/dev/null || \
  tmux new-session -d -s biocage_physio_v3 "cd '$OLD' && python scripts/6_active_learning/h28_physio_prerun.py 12 >> human_study/al_v2/physio_v3_prerun.log 2>&1 && touch human_study/al_v2/physio_v3_prerun.done"
[ -f "$OLD/human_study/al_v2/physio_rot_prerun.done" ] || tmux has-session -t biocage_physio_rot 2>/dev/null || \
  tmux new-session -d -s biocage_physio_rot "cd '$OLD' && python scripts/6_active_learning/h28_physio_prerun.py 12 physio_rot al_v2/physio_rot physrot_ >> human_study/al_v2/physio_rot_prerun.log 2>&1 && touch human_study/al_v2/physio_rot_prerun.done"
# report real work as Jupyter activity so the idle culler does not stop a computing server (PI-authorised 2026-10-26)
tmux has-session -t evo_keepalive 2>/dev/null || tmux new-session -d -s evo_keepalive "cd '$EVO' && python ops/activity_keepalive.py"
echo "$(date -Is) resume_all" >> "$EVO/work/agents/resume_all.log"
tmux ls
