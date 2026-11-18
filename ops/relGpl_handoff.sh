#!/bin/bash
# One-shot handoff (foreman 2026-11-10 22:0x): restart the h51 relG_pl driver with more workers without killing a running window.
# A placeholder process whose args match h51 busy_threads() ('h47_restart_pilot.py run <x> <gpu> <cores>') holds the quota full so
# the old driver starts no new window; once its last h47 window and any fric_compare refresh have exited, the old driver (no
# children left) is stopped and relGpl_drive is started again with the resume_all.sh command line, then the hold is removed.
# Restart-safe: if the server stops mid-handoff, resume_all.sh starts the driver with the new worker count.
OLD=/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
W=${1:-5}
f=human_study/al_v2/physio_relG_pl/run_batch.log
log() { echo "$(date '+%m-%d %H:%M') handoff: $*" >> "$OLD/$f"; }
bash -c 'exec -a "relGpl_hold h47_restart_pilot.py run hold 0 32" sleep 86400' & HOLD=$!
log "quota hold pid $HOLD; waiting for the running window"
while ps -u "$USER" -o args= | grep -v relGpl_hold | grep -q 'h4[7]_restart_pilot.py run .*physio_relG_pl\|fric_compar[e]'; do sleep 30; done
pkill -u "$USER" -f 'h51_relG_fallback.py run' ; sleep 5
tmux kill-session -t relGpl_drive 2>/dev/null; sleep 2
tmux new-session -d -s relGpl_drive "cd '$OLD' && python3 -u scripts/5_compute/h51_relG_fallback.py run $W 1,2,3,4 6 +p039:extension +p039:flexion +p052:extension +p052:flexion +p061:extension +p061:flexion >> $f 2>&1"
sleep 20; kill $HOLD
log "driver restarted with $W workers, hold removed"
