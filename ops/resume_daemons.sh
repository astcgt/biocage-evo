#!/bin/bash
# Resident daemon start-up, split out of resume_all.sh on 2026-11-22 (platform capability check SPD-06 depends on THIS file, not on the
# lane list in resume_all.sh, which the foreman edits every time a lane is added). Starts the platform watchdog if it is not running;
# the watchdog brings back the scheduler, the samplers, the preflight daemon and the QA loop (h23_watchdog.py ensure_daemons).
# Idempotent. Called first by resume_all.sh (which Jupyter runs at every server start).
export PATH="/raid/jupyter-alz.ee09/.local/bin:/raid/jupyter-alz.ee09/bin:/usr/local/cuda/bin:$PATH"
OLD="/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026"
export USER="${USER:-$(id -un)}"
tmux has-session -t biocage_watchdog 2>/dev/null || tmux new-session -d -s biocage_watchdog "cd '$OLD' && python scripts/5_compute/h23_watchdog.py 2>> human_study/watchdog.err"
