#!/bin/bash
# Restart wrapper for pilot_mu03/drive_newton_confirm.sh (foreman 11-22 01:2x): the same two h51 halves (build skips valid dirs, run skips
# done windows), but the logs are appended (the driver truncates them with '>'). usage: newtonC_lane.sh <fric|G|both>
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
KEYS='restart_env={"BIOCAGE_STICK_MEMORY": "1"}|window_drive_mode="rigid_relative"|window_min_residual=0.0001|window_max_ups=0'
L=human_study/al_v2/pilot_mu03
if [ "$1" != G ]; then
( export H51_SRC=pilot_mu03 H51_DST=pilot_mu03rN H51_KEYS="$KEYS"
  python scripts/5_compute/h51_relG_fallback.py build p105 p110 p131 p038
  python scripts/5_compute/h51_relG_fallback.py run 2 1,3 6 p105:flexion p105:extension p110:flexion p110:extension p131:flexion p131:extension p038:flexion p038:extension ) >> $L/drive_NC_fric.log 2>&1 &
fi
if [ "$1" != fric ]; then
( export H51_SRC=pilot_mu03G H51_DST=pilot_mu03GrN H51_KEYS="$KEYS"
  python scripts/5_compute/h51_relG_fallback.py build p052
  python scripts/5_compute/h51_relG_fallback.py run 1 4 6 p052:flexion p052:extension ) >> $L/drive_NC_G.log 2>&1 &
fi
# marker only when both halves ran here; after a one-half relaunch the next resume_all pass relaunches both (done windows are skipped)
wait; [ "$1" = both ] && echo "NEWTON_CONFIRM DONE $(date '+%m-%d %H:%M') (relaunch)" >> $L/drive_NC_fric.log
