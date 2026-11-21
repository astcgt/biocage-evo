#!/bin/bash
# pilot_push posterior push-out on an explicit design list (foreman 11-20 12:1x): same steps as human_study/al_v2/pilot_push/push_batch.sh
# (same design list generator, same skip done_push_post + normal true, h53 build, 36-try h47 push_post loop with h24 revalidate), but
# only the designs named on the command line, so lanes never share a design. Usage: push_lanes.sh <gpu> <lane tag> <design...>.
# 11-20 12:1x: lane 1 split: push_batch.sh 3 1 list truncated after p129 (offset 630); lane 2 (GPU 1) = p135 p140 p143 p146.
# resume_all covers pushB1 with "push_lanes.sh 3 1 p110 p114 p120" and pushB2 with "push_lanes.sh 1 2 p135 p140 p143 p146".
# 11-20 13:1x: lane 1 list truncated again after p120 (offset 560); lane 3 (GPU 4, tmux biocage_pushB3) = p122 p129.
# Marker PUSH LANE <tag> DONE in pilot_push/batch_lane<tag>.log.
G=$1; L=$2; shift 2; [ -n "$G" ] && [ -n "$L" ] && [ $# -gt 0 ] || { echo "usage: $0 <gpu> <lane tag> <design...>"; exit 2; }
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
A=human_study/al_v2; mkdir -p /tmp/claude-1024
python - "$@" <<'P' > /tmp/claude-1024/push_lanes_$L.txt
import json, sys
E='/raid/jupyter-alz.ee09/projects/claude-work/biocage-evo/'
cls=json.load(open(E+'results/method/split/verdict_classes_merged.json'))['classes']; fr=json.load(open(E+'results/method/fric/verdicts.json'))
want=sys.argv[1:]
for p in want:
    if p not in cls['PASS']+cls['GREY/friction-posterior-0.45-0.55']: continue
    w=fr[p]['windows']['flexion']; print(p, w['set'], w['case_dir'], 'pilot_pushG' if w['set']=='physio_relGr' else 'pilot_push')
P
while read p set cd dst; do
  d=$A/$dst/$p
  [ -f $d/done_push_post ] && grep -q "\"normal\": true" $d/resources_push_post.json 2>/dev/null && { echo "$p done"; continue; }
  while pgrep -u "$USER" -f "h47_restart_pilot.py run $d " >/dev/null; do sleep 60; done   # a run left by another lane: wait, never double-run
  python scripts/5_compute/h53_push_restart.py build $d $A/$set/$cd 2>&1 | tail -1
  for i in $(seq 36); do
    python scripts/5_compute/h47_restart_pilot.py run $d $G 6 push_post 2>&1 | tail -1
    [ -f $d/resources_push_post.json ] && break
    if ! python -c "import sys;sys.path.insert(0,'scripts/5_compute');import h24_preflight as h;sys.exit(0 if h.valid('$d') else 1)"; then
      python scripts/5_compute/h53_push_restart.py build $d $A/$set/$cd 2>&1 | tail -1; fi
    sleep 300
  done
  echo "$(date +%H:%M) $p push_post $(python -c "import json;print(json.load(open('$d/resources_push_post.json')).get('normal'))" 2>/dev/null)"
done < /tmp/claude-1024/push_lanes_$L.txt
echo "PUSH LANE $L DONE"
