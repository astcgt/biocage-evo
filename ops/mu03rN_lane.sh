#!/bin/bash
# foreman 2026-11-21 14:5x: one half of human_study/al_v2/pilot_mu03/drive_mu03rN.sh (same H51_SRC / H51_DST / H51_KEYS, designs and windows
# verbatim), with the GPU list as an argument. Made for the G half: the driver gave it GPU 5, which another user holds at 39.7 / 40 GB, so the
# h51 gpu_busy 60 % gate would hold it 24 h and requeue it forever. h51 build skips valid dirs, run skips windows with a done marker.
# usage: mu03rN_lane.sh fric|G [gpus]   (defaults: fric 0,3 / G 4); log: pilot_mu03/drive_N_<fric|G>.log, h51 ends it with RELG_PL DONE
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
export H51_KEYS='restart_env={"BIOCAGE_STICK_MEMORY": "1"}|window_drive_mode="rigid_relative"|window_min_residual=0.0001|window_max_ups=0'
case "$1" in
  fric) export H51_SRC=pilot_mu03 H51_DST=pilot_mu03rN
        python scripts/5_compute/h51_relG_fallback.py build p014 p026 p079 p086 p093 p117 p125
        python scripts/5_compute/h51_relG_fallback.py run 2 "${2:-0,3}" 6 p014:extension p026:extension p079:extension p086:flexion p093:flexion p117:flexion p117:extension p125:flexion ;;
  G)    export H51_SRC=pilot_mu03G H51_DST=pilot_mu03GrN
        python scripts/5_compute/h51_relG_fallback.py build p095 p104 p128
        python scripts/5_compute/h51_relG_fallback.py run 1 "${2:-4}" 6 p095:extension p104:extension p128:extension ;;
  *) echo "usage: $0 fric|G [gpus]"; exit 2 ;;
esac
