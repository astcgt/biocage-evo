#!/bin/bash
# Extra lanes for astm_f2077_plastic_hard (foreman 11-21 09:5x): lane.sh (tmux biocage_astmP) walks the designs one at a time and sat
# on p064 compression at dtmin (~21 h) with 28 of the 32 quota cores idle. usage astm_plastic_lanes.sh <L> (L = 1, 2, ...).
# Same steps as lane.sh one() (build <out> <src> 1.0 10 0.02 hard, tests with resources.json skipped, e11 astm_result.json), but the
# 3 tests of a design run in parallel (4 cores each) and the list is walked in reverse (p146 down). lane.sh has no claim check, so
# collision-proofing: (1) only designs after p066 in the sorted list (p064 = lane.sh's, p065 / p066 = buffer); (2) a design (own
# claim included) is started only while the last line of lane.log is still 'plastic_hard/p064 built' (lane.sh still on p064);
# else the lane exits. Lanes share designs by an atomic mkdir claim ($out/.claim/lane_<L>). Log plastic_lane_<L>.log (never lane.log).
# Optional 2nd arg = floor (default p066): designs after it only. foreman 11-21 13:4x lane 6 with p064 (p065 / p066 while p064 had ~17 h left;
# a relaunch without the arg skips them, lane.sh then does them).
# Stop: tmux kill-session -t biocage_astmP<L>; lane.sh then runs whatever has no resources.json. Marker ASTM PLASTIC LANE <L> DONE.
L=$1; [ -n "$L" ] || { echo "usage: $0 <lane>"; exit 2; }
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
A=human_study/al_v2; H=scripts/3_cage_case/h55_astm_f2077.py; O=$A/astm_f2077_plastic_hard; EV=../biocage-evo
gate() { tail -n 1 $O/lane.log | grep -q 'astm_f2077_plastic_hard/p064 built'; }
for d in $(ls -d $A/astm_f2077/p*/ | sort -r); do
  p=$(basename $d); [[ "$p" > ${2:-p066} ]] || continue
  out=$O/$p; [ -f $out/astm_result.json ] && [ -f $out/compression/resources.json ] && [ -f $out/shear45/resources.json ] && [ -f $out/torsion/resources.json ] && continue
  src=$(python3 -c "import json;print(json.load(open('$d/astm.json'))['source'])" 2>/dev/null) || continue
  gate || { echo "$(date +%H:%M) lane.sh left p064 ($(tail -n 1 $O/lane.log | cut -c1-60)), lane $L stops"; break; }
  mkdir -p $out; if mkdir $out/.claim 2>/dev/null; then touch $out/.claim/lane_$L; elif [ ! -f $out/.claim/lane_$L ]; then continue; fi
  [ -f $out/astm.json ] || python $H build $out $src 1.0 10 0.02 hard || { echo "$(date +%H:%M) $p build failed"; continue; }
  for t in compression shear45 torsion; do
    [ -f $out/$t/resources.json ] && continue
    ( until python $H run $out $t 4 > $out/$t.run.log 2>&1; [ $? -ne 3 ]; do sleep 300; done ) &
    sleep 5
  done
  wait
  (cd $EV && python methods/e11_astm.py $PWD/../biocage_simulation_test_oct2026/$out $PWD/../biocage_simulation_test_oct2026/$out/astm_result.json > /dev/null 2>&1)
  echo "$(date +%H:%M) $out done"
done
echo "ASTM PLASTIC LANE $L DONE"
