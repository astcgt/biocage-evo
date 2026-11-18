#!/bin/bash
# febio_pin.sh (foreman 11-10): h18/h47 pick "idle" cores at spawn without NUMA awareness, so new runs land on node 0-1,
# overlap each other's cores and sit away from their GPU (re-pin by hand gave +50% 11-10 21:53, +31% 22:53).
# Every 30 s: each of my febio4 processes that overlaps another of my runs, spans >1 NUMA node, or sits off its GPU's node while
# that node has room is moved ONCE (taskset -a) to a disjoint block of idle physical cores (GPU-local node first, else one other
# node). Scheduling only: no run is stopped. claimed_cores() in h06 reads live affinity, so launchers see the new cores.
# Log: work/ops/febio_pin.log. Started by ops/resume_all.sh (tmux febio_pin).
cd "$(dirname "$0")/.." || exit 1
exec python3 -u - "$@" >> work/ops/febio_pin.log 2>&1 <<'EOF'
import os, time, subprocess
GPU_NODE = {0: 3, 1: 3, 2: 1, 3: 1, 4: 7, 5: 7, 6: 5}          # nvidia-smi topo -m; node k = physical cores 16k..16k+15
node = lambda c: (c % 128) // 16
moved = set()
def busy(dt=2.0):
    def snap(): return {int(l.split()[0][3:]): (sum(map(int, l.split()[1:])), int(l.split()[4]) + int(l.split()[5]))
                        for l in open('/proc/stat') if l.startswith('cpu') and l[3].isdigit()}
    a = snap(); time.sleep(dt); b = snap()
    return {c: 1 - (b[c][1] - a[c][1]) / max(1, b[c][0] - a[c][0]) for c in a}
def mine():
    out = {}
    for p in os.listdir('/proc'):
        try:
            if not p.isdigit() or os.stat(f'/proc/{p}').st_uid != os.getuid(): continue
            if open(f'/proc/{p}/comm').read().strip() != 'febio4': continue
            env = dict(x.split('=', 1) for x in open(f'/proc/{p}/environ').read().split('\0') if '=' in x)
            out[int(p)] = (int(env.get('CUDA_VISIBLE_DEVICES', '-1').split(',')[0]), os.sched_getaffinity(int(p)))
        except (OSError, ValueError):
            pass
    return out
while True:
    runs = mine(); b = None
    for pid, (gpu, aff) in runs.items():
        if pid in moved or len(aff) >= os.cpu_count() or gpu not in GPU_NODE: continue
        taken = set().union(*[a for q, (g, a) in runs.items() if q != pid]) if len(runs) > 1 else set()
        taken |= {c ^ 128 if c < 256 else c for c in taken}                 # HT siblings (c, c+128) count as taken
        b = b or busy()
        def free(n): return [c for c in range(16 * n, 16 * n + 16) if c not in taken and (c in aff or b[c] < 0.25) and b[c + 128] < 0.25]
        n, home = len(aff), GPU_NODE[gpu]
        nodes = {node(c) for c in aff}
        bad = bool(aff & taken) or len(nodes) > 1 or (nodes != {home} and len(free(home)) >= n)
        if not bad: continue
        for k in [home] + [k for k in range(8) if k != home]:
            f = free(k)
            if len(f) >= n:
                new = f[:n]
                r = subprocess.run(['taskset', '-a', '-pc', ','.join(map(str, new)), str(pid)], capture_output=True)
                moved.add(pid)
                print(time.strftime('%m-%d %H:%M:%S'), f'pid {pid} gpu {gpu}: {sorted(aff)} -> {new} (node {k})', 'ok' if r.returncode == 0 else r.stderr.decode().strip(), flush=True)
                if r.returncode == 0: runs[pid] = (gpu, set(new))
                break
    moved &= set(runs)
    time.sleep(30)
EOF
