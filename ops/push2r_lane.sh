#!/bin/bash
# Restart wrapper for pilot_push/push2_retry.sh (foreman 11-21 16:5x). The retry script skips a design once case_first_fail.log exists,
# so a retry killed by a server stop would be dropped. Here, per design: case_first_fail.log present and no resources_push_post2.json
# newer than it -> the SAME h47 loop + e09 read the retry script runs after its add2; e09 json older than the retry -> e09 only;
# no case_first_fail.log -> the unchanged push2_retry.sh for that design. usage: push2r_lane.sh <gpu> <cores> p075 p093 ...
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
G=$1; C=$2; shift 2; A=human_study/al_v2; EV=../biocage-evo
for p in "$@"; do
  d=$A/pilot_push/$p; [ -d $A/pilot_pushG/$p ] && d=$A/pilot_pushG/$p; w=$d/w_push_post2; r=$d/resources_push_post2.json
  if [ ! -f $w/case_first_fail.log ]; then bash $A/pilot_push/push2_retry.sh $G $C $p | grep --line-buffered -v 'PUSH2 RETRY'; continue; fi
  if [ ! $r -nt $w/case_first_fail.log ]; then
    echo "$(date +%H:%M) $p retry interrupted, h47 re-run"
    # killed between the retry's cp and its rm: redo its add2 (rewrites w_push_post2/restart.feb from w_flexion, same arguments) and rm
    [ $w/restart.feb -nt $w/case_first_fail.log ] || python scripts/5_compute/h53_push_restart.py add2 $d mm=3.0 dt0=0.005 maxups=0
    rm -f $r $d/done_push_post2
    bash scripts/5_compute/wait_quota.sh $C
    for i in $(seq 36); do python scripts/5_compute/h47_restart_pilot.py run $d $G $C push_post2; [ -f $r ] && break; sleep 600; done
  fi
  e=$EV/results/method/e09/${p}_push_post2.json
  [ -f $r ] && [ ! $e -nt $r ] && (cd $EV && python methods/e09_pushout.py $PWD/../biocage_simulation_test_oct2026/$w results/method/e09/${p}_push_post2.json 2>&1 | tail -1 | sed "s/^/$(date +%H:%M) $p retry /")
done
echo "PUSH2 RETRY $G DONE"
