#!/usr/bin/env python3
"""physio_relG production batch driver (foreman 2026-11-10 15:0x). Scheduling only: every design still runs through
scripts/5_compute/h50_relG_batch.py (settings class env, h24 valid() check, GPU-memory guard, h18 checkpoint resume).

Why: the 14:36 h50 run (5 workers, GPUs 1-5) lost its GPU-5 worker to a GPU filled to 39.7/40 GB by another user; 23 designs
ended in 11 s each with a cuDSS 'preprocessing of linear solver' ERROR (launcher failure, not a solver result). h18's idle-core
check counts the 256 node cores, not this account's 32-core cgroup quota, so the cap on concurrent runs is enforced here.

Rule, every 60 s: a design is finished when one of its run dirs other than _gpu5 holds resources.json (any outcome: a solver
ERROR is a result and is not rerun). Unfinished, not live designs are started one per h50 call ('run 1 <gpu> <cores> pNNN')
while fewer than MAXRUN relG runs are live; an interrupted run dir pNNN_gpuK is resumed on GPU K (h18 resumes from case.dmp).
Idempotent: resume_all.sh restarts it after a server restart; it exits with 'RELG DRIVE DONE' when nothing is left.
"""
import os, re, glob, time, subprocess
OLD = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026'
D = os.path.join(OLD, 'human_study/al_v2/physio_relG')
H50 = os.path.join(OLD, 'scripts/5_compute/h50_relG_batch.py')
LOG = os.path.join(D, 'drive.log')
MAXRUN, CORES, GPUS, BAD = 5, 6, (4, 1, 3, 2), (5,)     # 5 x 6 = 30 of the 32-core quota; GPUs 0/5/6 are full of other users' jobs
TUNE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'relG_drive_tuning.json')   # {"MAXRUN": n}, re-read every pass


def maxrun():
    try: return int(__import__('json').load(open(TUNE)).get('MAXRUN', MAXRUN))
    except Exception: return MAXRUN


def say(s): open(LOG, 'a').write(time.strftime('%m-%d %H:%M ') + s + '\n')


def live():
    """design -> gpu for my live h18 runs and my waiting single-design h50 calls"""
    out = {}
    ps = subprocess.run(['ps', '-u', str(os.getuid()), '-o', 'args='], capture_output=True, text=True).stdout
    for l in ps.splitlines():
        m = re.search(r'h18_run_gpu_case\.py (\d+) \S*physio_relG/(p\d{3})( |$)', l) or re.search(r'h50_relG_batch\.py run 1 (\d+) \d+ (p\d{3})', l)
        if m: out[m.group(2)] = int(m.group(1))
    return out


def designs():
    return sorted(os.path.basename(f)[:4] for f in glob.glob(D + '/p[0-9][0-9][0-9]_params.json'))


def finished(p):
    return any(os.path.exists(d + '/resources.json') for d in glob.glob(f'{D}/{p}_gpu*') if int(d.rsplit('gpu', 1)[1]) not in BAD)


def main():
    say(f'start: {len(designs())} designs, MAXRUN {maxrun()}, GPUs {GPUS}, {CORES} cores')
    started = {}                                         # p -> time of my last h50 call (h50 may skip a run dir whose log is < 20 min old)
    while True:
        L = live(); todo = [p for p in designs() if not finished(p) and p not in L]
        if not todo and not L: say('RELG DRIVE DONE'); return
        for p in todo:
            if len(L) >= maxrun(): break
            if time.time() - started.get(p, 0) < 600: continue
            old = [int(d.rsplit('gpu', 1)[1]) for d in glob.glob(f'{D}/{p}_gpu*') if int(d.rsplit('gpu', 1)[1]) not in BAD]
            g = old[0] if old else min(GPUS, key=lambda k: (list(L.values()).count(k), GPUS.index(k)))
            lg = f'{D}/{p}_gpu{g}/case.log'
            if old and os.path.exists(lg) and time.time() - os.path.getmtime(lg) < 1200:
                L[p] = g; continue                       # after a restart: hold the slot until h50's 20-min live rule lets it resume
            subprocess.Popen(['python3', '-u', H50, 'run', '1', str(g), str(CORES), p], cwd=OLD,
                             stdout=open(os.path.join(D, 'run_batch2.log'), 'a'), stderr=subprocess.STDOUT, start_new_session=True)
            # own session: a driver / tmux restart no longer SIGHUPs the live runs (they are in the pane's session up to 11-10 16:0x)
            started[p] = time.time(); L[p] = g; say(f'{p} -> GPU {g}' + (' (resume)' if old else ''))
            time.sleep(20)                               # h18 launches are serialised by its lock; let ps see it
        time.sleep(60)


if __name__ == '__main__':
    main()
