#!/bin/bash
# Restartable round runner: every 5 min, run every round in work/board/schedule.json whose time has come and that still misses
# a role verdict; run_roles.sh skips roles that already delivered, so a round interrupted by a server restart resumes.
cd "$(dirname "$0")/.."
while true; do
  python - <<'P' | while read r roles; do roles/run_roles.sh "$r" $roles; done
import json, os, datetime, subprocess
s = json.load(open('work/board/schedule.json'))
now = datetime.datetime.now()
for e in s['rounds']:
    if datetime.datetime.fromisoformat(e['at']) > now: continue
    todo = [r for r in e['roles'] if not os.path.exists(f"work/board/r{e['round']:04d}/{r}.json")]
    busy = subprocess.run(['pgrep', '-u', str(os.getuid()), '-f', 'roles/run_roles.sh'], capture_output=True).returncode == 0
    if todo and not busy: print(e['round'], ' '.join(todo))   # a process check, not a lock file: a lock would survive a server restart
P
  sleep 300
done
