#!/bin/bash
# Restart wrapper for pilot_cyc8v/lanes8.sh (foreman 11-22 01:2x). lanes8.sh runs h18 unconditionally and h47 build rmtree's
# pilot_cyc8vrN/<p>, so a blind relaunch would redo a finished insertion or wipe a started window. Here, per stage:
#  process-G (pilot_cyc8vGN/<p>): _gpu<G>/case.log NORMAL or ERROR -> done; else lanes8.sh (h18 resumes from case.dmp).
#  fric: resources_flexion.json -> done; insertion ERROR -> done ('not normal'); insertion NORMAL -> skip h18, skip build when
#  pilot_cyc8vrN/<p> exists (h24 check() in place if stale), then the SAME h47 loop as lanes8.sh; no NORMAL -> lanes8.sh.
# Keep the original GPU (the _gpu<G> suffix is what the build reads). usage: cyc8_lane.sh <gpu> <cores> <design>
cd /raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026
G=$1; C=$2; p=$3; A=human_study/al_v2
if [ -d $A/pilot_cyc8vGN/$p ]; then
  grep -qE "N O R M A L|E R R O R" $A/pilot_cyc8vGN/${p}_gpu$G/case.log 2>/dev/null && { echo "$(date '+%m-%d %H:%M') $p process-G 8-cycle run ended (seen on relaunch)"; exit 0; }
  exec bash $A/pilot_cyc8v/lanes8.sh $G $C $p
fi
[ -f $A/pilot_cyc8vrN/$p/resources_flexion.json ] && { echo "$(date '+%m-%d %H:%M') $p 8-cycle window ended (seen on relaunch)"; exit 0; }
L=$A/pilot_cyc8v/${p}_gpu$G/case.log
grep -q "E R R O R" $L 2>/dev/null && ! grep -q "N O R M A L" $L && { echo "$(date '+%m-%d %H:%M') $p insertion not normal (seen on relaunch)"; exit 0; }
grep -q "N O R M A L" $L 2>/dev/null || exec bash $A/pilot_cyc8v/lanes8.sh $G $C $p
# built dir present: never rebuild (rmtree would wipe a started window); a settings edit only stales h24 -> run the real check() in place
if [ -d $A/pilot_cyc8vrN/$p ]; then
  python3 -c "
import sys; sys.path.insert(0, 'scripts/5_compute'); import h24_preflight
d = '$A/pilot_cyc8vrN/$p'; h24_preflight.valid(d) or print('$p h24 check', h24_preflight.check(d)['ok'])"
else
  python scripts/5_compute/h47_restart_pilot.py build $A/pilot_cyc8vrN/$p $A/pilot_cyc8v/${p}_gpu$G 'window_max_ups=0' || exit 1
fi
for i in $(seq 36); do bash scripts/5_compute/wait_quota.sh $C; python scripts/5_compute/h47_restart_pilot.py run $A/pilot_cyc8vrN/$p $G $C flexion; [ -f $A/pilot_cyc8vrN/$p/resources_flexion.json ] && break; sleep 600; done
echo "$(date '+%m-%d %H:%M') $p 8-cycle window ended"
