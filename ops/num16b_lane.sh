#!/bin/bash
# Restart wrapper for numconv_hz01/lane16b.sh (tmux biocage_16b, by hand 11-22 01:08, PI item 16(b)) (foreman 11-22 02:1x). Same steps, with:
#  build16b.py only for designs without preflight.json (a rebuild would rewrite the source of a <p>_gpu<g> copy mid-run);
#  a design with its 'fine-mesh run ended' line in lane16b.log is skipped; an interrupted <p>_gpu<g> resumes in h18 (split.json).
#  h18 re-checks a stale h24 preflight itself (exit 4, not launched).
# usage: num16b_lane.sh <gpu> <cores> p036 p052 ...   (stdout -> numconv_hz01/lane16b.log)
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
G=$1; C=$2; shift 2; A=human_study/al_v2; L=$A/numconv_hz01/lane16b.log
B=; for p in "$@"; do [ -f $A/numconv_hz01/$p/preflight.json ] || B="$B $p"; done
[ -n "$B" ] && python $A/numconv_hz01/build16b.py $B
for p in "$@"; do
  [ -f $A/numconv_hz01/$p/preflight.json ] || continue
  grep -qs "$p fine-mesh run ended" $L && continue
  bash scripts/5_compute/wait_quota.sh $C
  until python scripts/5_compute/h18_run_gpu_case.py $G $A/numconv_hz01/$p $C; [ $? -ne 3 ]; do sleep 600; done
  echo "$(date '+%m-%d %H:%M') $p fine-mesh run ended"
done
(cd ../biocage-evo && python ops/num16_multi.py p062 "$@")
echo "LANE16B DONE"
