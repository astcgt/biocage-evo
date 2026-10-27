#!/bin/bash
# e03 on every tied physio run of the old study that finished all 6 windows (NORMAL TERMINATION); 8 in parallel.
cd "$(dirname "$0")/.."
OLD="/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1/human_study/al_v2"
for d in "$OLD"/physio_v3/p*/ "$OLD"/physio_fix/p*/; do
  [ -f "$d/case.log" ] && grep -q "N O R M A L" "$d/case.log" && echo "$d"
done | xargs -P 8 -I{} bash -c 'n=$(basename "{}"); s=$(basename $(dirname "{}")); python methods/e03_mu_req.py "{}" results/method/e03/${s}_${n}.json > /dev/null 2> results/method/e03/${s}_${n}.err && echo "ok ${s}_${n}" || echo "FAIL ${s}_${n}"'
