#!/bin/bash
# Restart wrapper for numconv_hz01/lane16c.sh (tmux biocage_16c, by hand 11-22 09:06, PI item 16(b) second pass) (foreman 11-22 09:1x).
# Same steps (cases are built and preflighted before the lane, no build here), with: a design with its 'fine-mesh run ended' line in
# lane16c.log is skipped; an interrupted <d>_gpu<g> resumes in h18 (split.json); h18 re-checks a stale h24 preflight (exit 4, not launched).
# usage: num16c_lane.sh <gpu> <cores> numconv_hz01/p146 numconv_hz01/inplane/p060 ...   (stdout -> numconv_hz01/lane16c.log)
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
G=$1; C=$2; shift 2; A=human_study/al_v2; L=$A/numconv_hz01/lane16c.log
for d in "$@"; do
  [ -f $A/$d/preflight.json ] || { echo "$(date '+%m-%d %H:%M') $d no preflight, skipped"; continue; }
  grep -qs "$d fine-mesh run ended" $L && continue
  bash scripts/5_compute/wait_quota.sh $C
  until python scripts/5_compute/h18_run_gpu_case.py $G $A/$d $C; [ $? -ne 3 ]; do sleep 600; done
  echo "$(date '+%m-%d %H:%M') $d fine-mesh run ended"
done
(cd ../biocage-evo && python ops/num16_multi.py)
echo "LANE16C DONE"
