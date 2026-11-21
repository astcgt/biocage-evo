#!/bin/bash
# Restart wrapper for the two waiters in tmux biocage_finish (foreman 11-22 01:2x). Same steps as the originals, with:
#  push2: the retry goes through ops/push2r_lane.sh (re-runs an interrupted retry; push2_retry.sh would skip it); marker PUSH2 FINISH DONE.
#  e: verdicts_before_batch_e.json is copied only once (a relaunch after a partial pipeline must not overwrite it); marker PIPELINE_E DONE.
# usage: finish_lane.sh <push2|e>
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
if [ "$1" = push2 ]; then
  L=human_study/al_v2/pilot_push
  until [ "$(cat $L/push2_lane*.log 2>/dev/null | grep -c 'PUSH2 LANE')" -ge 6 ]; do sleep 300; done
  ALL=$(ls -d human_study/al_v2/pilot_push/p??? human_study/al_v2/pilot_pushG/p??? | xargs -n1 basename | sort -u | tr '\n' ' ')
  bash ../biocage-evo/ops/push2r_lane.sh 0 4 $ALL >> $L/push2_retry.log 2>&1
  (cd ../biocage-evo && python ops/push2_summary.py > results/method/e09/push2_summary.log 2>&1)
  echo "$(date '+%m-%d %H:%M') PUSH2 FINISH DONE" >> $L/push2_retry.log
elif [ "$1" = e ]; then
  L=human_study/al_v2/pilot_mu03
  until [ "$(cat $L/drive_e_fric.log $L/drive_e_G1.log $L/drive_e_G3.log 2>/dev/null | grep -c 'MU03R_E')" -ge 3 ]; do sleep 300; done
  cd ../biocage-evo; LOG=results/method/fric/pipeline_e.log
  [ -f results/method/fric/verdicts_before_batch_e.json ] || cp results/method/fric/verdicts.json results/method/fric/verdicts_before_batch_e.json
  python ops/fric_compare.py 3 >> $LOG 2>&1 && python ops/e07_batch.py 3 >> $LOG 2>&1 && python ops/replicate_agreement.py physio_fric5r physio_relGr pilot_mu03r pilot_mu03Gr >> $LOG 2>&1 && \
  python ops/collect_split.py 3 >> $LOG 2>&1 && python ops/mu_req_field.py >> $LOG 2>&1 && python ops/shortcut_consistency.py >> $LOG 2>&1 && python ops/obs01_batch.py 2 >> $LOG 2>&1
  echo "$(date '+%m-%d %H:%M') PIPELINE_E DONE rc=$?" >> $LOG
fi
