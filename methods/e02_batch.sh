#!/bin/bash
# friction-limit bracket (e02) on every ended physio run, 2 at a time (xplt loading is memory heavy)
cd "$(dirname "$0")/../.."
python -c "import json;[print(r['dir']) for r in json.load(open('human_study/al_v2/physio_analysis/cases.json'))]" |
  xargs -P 2 -I{} sh -c 'o=results/method/fl_$(basename {}).json; [ -f $o ] || timeout 1800 python methods/e02_friction_limit.py {} $o > /dev/null 2>> results/method/e02.err'
echo done > results/method/e02.done
