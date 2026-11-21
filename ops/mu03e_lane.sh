#!/bin/bash
# Restart wrapper for pilot_mu03/drive_mu03r_e.sh (foreman 11-21 15:5x). The driver skips h18 when <SRC>/<p>_gpu* exists, so an
# insertion killed by a server stop would be reported 'insertion not normal' and its design dropped. Here: for each design whose
# _gpu dir exists without N O R M A L and without a live FEBio, run the SAME h18 command first (h18 resumes from case.dmp), then exec
# the unchanged driver. usage: mu03e_lane.sh <fric|G> <gpu> p036 p066 ...
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
KIND=$1; G0=$2; A=human_study/al_v2
if [ $KIND = G ]; then SRC=pilot_mu03G; else SRC=pilot_mu03; fi
for p in "${@:3}"; do
  d=$(ls -d $A/$SRC/${p}_gpu* 2>/dev/null | head -1); [ -n "$d" ] || continue
  grep -q "N O R M A L" $d/case.log 2>/dev/null && continue
  grep -q "E R R O R" $d/case.log 2>/dev/null && continue    # ended in error, not interrupted: the driver reports it
  pgrep -u "$USER" -f "h18_run_gpu_case.py .* $A/$SRC/$p " >/dev/null && continue
  echo "$(date +%H:%M) $p insertion interrupted, h18 resume ($d)"
  bash scripts/5_compute/wait_quota.sh 6
  if [ $KIND = G ]; then
    until BIOCAGE_FEBIO=$PWD/third_party/FEBio/cbuild_fric/bin/febio4 BIOCAGE_STICK_MEMORY=1 python scripts/5_compute/h18_run_gpu_case.py ${d##*_gpu} $A/$SRC/$p 6; [ $? -ne 3 ]; do echo "$p no idle cores, retry in 10 min"; sleep 600; done
  else
    until python scripts/5_compute/h18_run_gpu_case.py ${d##*_gpu} $A/$SRC/$p 6; [ $? -ne 3 ]; do echo "$p no idle cores, retry in 10 min"; sleep 600; done
  fi
done
exec bash $A/pilot_mu03/drive_mu03r_e.sh "$@"
