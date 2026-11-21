#!/bin/bash
# ASTM F2077 batch in 2 lanes (foreman 11-20 08:1x; same steps as human_study/al_v2/astm_f2077/batch.sh, which runs one design at
# a time): usage astm_lanes.sh F|R  (F = sorted list, R = reversed). A lane takes a design by an atomic mkdir claim
# ($d/.claim, owner file lane_<L>; a lane re-takes its own claims after a restart), skips designs with an e11 json and tests with
# resources.json, and does not start a test whose h55 run is already alive (waits for it, e.g. one left by batch.sh).
# START ONLY AFTER biocage_astm (batch.sh) is stopped, or its list is truncated to its current design and that design is claimed
# for lane R (11-20 11:10: p077/.claim/lane_R, so F skips it and R ends with it): batch.sh has no claim check. Marker ASTM LANE <L> DONE.
L=$1; [ "$L" = F ] || [ "$L" = R ] || { echo "usage: $0 F|R"; exit 2; }
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
A=human_study/al_v2; EV=../biocage-evo; mkdir -p /tmp/claude-1024
python - <<'P' | { [ "$L" = R ] && tac || cat; } > /tmp/claude-1024/astm_list_$L.txt
import json
E='/raid/jupyter-alz.ee09/projects/claude-work/biocage-evo/'
cls=json.load(open(E+'results/method/split/verdict_classes_merged.json'))['classes']; fr=json.load(open(E+'results/method/fric/verdicts.json'))
for p in sorted(cls['PASS']+cls['GREY/friction-posterior-0.45-0.55']):
    w=fr[p]['windows']['flexion']; print(p, f"{w['set']}/{w['case_dir']}")
P
while read p src; do
  d=$A/astm_f2077/$p
  [ -f $EV/results/method/e11/$p.json ] && continue
  mkdir -p $d; if mkdir $d/.claim 2>/dev/null; then touch $d/.claim/lane_$L; elif [ ! -f $d/.claim/lane_$L ]; then echo "$(date +%H:%M) $p claimed by $(ls $d/.claim)"; continue; fi
  [ -f $d/astm.json ] || python scripts/3_cage_case/h55_astm_f2077.py build $d $A/$src || { echo "$(date +%H:%M) $p build failed"; continue; }
  for t in compression shear45 torsion; do
    [ -f $d/$t/resources.json ] && continue
    ( while pgrep -u "$USER" -f "^python scripts/3_cage_case/h55_astm_f2077.py run $d $t " >/dev/null; do sleep 60; done
      [ -f $d/$t/resources.json ] || until python scripts/3_cage_case/h55_astm_f2077.py run $d $t 4; [ $? -ne 3 ]; do sleep 300; done ) &
    sleep 5
  done
  wait
  echo "$(date +%H:%M) $p $(python $EV/methods/e11_astm.py $d $EV/results/method/e11/$p.json | tail -1)"
done < /tmp/claude-1024/astm_list_$L.txt
echo "ASTM LANE $L DONE"
