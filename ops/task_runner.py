"""Deterministic task runner for the long computations of this repository (gate runs, evaluations, ...).

Called every 5 min by ops/evo_daemon.sh (and safe to call any time; one pass, then exit).
Tasks are JSON files in work/ops/tasks/{queue,running,done,failed}/<name>.json:
  {"name": "gate2_lb_pos_x", "cmd": "python gate2_fsu.py lb_pos_x 20", "cwd": "gpufe", "gpu": true,
   "gpu_mem_gb": 4, "host_mem_gb": 6, "max_retries": 2, "priority": 0, "log": "work/agents/gate2_lb_pos_x.log"}
A pass:
  1. running tasks whose tmux session (task_<name>) is gone: exit code file 0 -> done/, else re-queue until max_retries,
     then failed/; no exit file (killed, server restart) -> re-queued without counting a retry.
  2. queued tasks, highest priority then oldest first: started in tmux when there is host memory (cgroup memory.max -
     memory.current - HEADROOM_GB >= host_mem_gb) and, for GPU tasks, a GPU with >= gpu_mem_gb free (all GPUs of the node,
     other users included; the GPU with the most free memory that runs the fewest of my tasks is used).
Every action is logged to work/ops/task_runner.log. Add a task: python ops/task_runner.py add <json-file-or-string>.
"""
import os, sys, json, glob, time, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'work/ops/tasks'); LOG = os.path.join(ROOT, 'work/ops/task_runner.log')
HEADROOM_GB = 16                                  # same margin as the old study's scheduler (h19: runs grow while running)
CG = '/sys/fs/cgroup' + open('/proc/self/cgroup').read().strip().split(':')[-1]
for d in ('queue', 'running', 'done', 'failed'): os.makedirs(os.path.join(T, d), exist_ok=True)


def log(msg):
    with open(LOG, 'a') as f: f.write(time.strftime('%m-%d %H:%M:%S ') + msg + '\n')


def host_free_gb():
    lim = open(CG + '/memory.max').read().strip(); cur = int(open(CG + '/memory.current').read())
    lim = int(lim) if lim != 'max' else int(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'))
    return (lim - cur) / 2**30 - HEADROOM_GB


def gpus():
    out = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.total,memory.used', '--format=csv,noheader,nounits'],
                         capture_output=True, text=True).stdout
    return {int(a): (float(b) - float(c)) / 1024 for a, b, c in (l.split(', ') for l in out.strip().splitlines())}


def alive(name):
    return subprocess.run(['tmux', 'has-session', '-t', 'task_' + name], capture_output=True).returncode == 0


def move(task, frm, to):
    os.replace(os.path.join(T, frm, task['name'] + '.json'), os.path.join(T, to, task['name'] + '.json'))
    json.dump(task, open(os.path.join(T, to, task['name'] + '.json'), 'w'), indent=1)


def launch(task, gpu):
    ex = os.path.join(T, 'running', task['name'] + '.exit')
    if os.path.exists(ex): os.remove(ex)
    env = f'CUDA_VISIBLE_DEVICES={gpu} ' if gpu is not None else ''
    logf = os.path.join(ROOT, task.get('log') or f'work/ops/{task["name"]}.log')
    cmd = f"cd '{os.path.join(ROOT, task.get('cwd', '.'))}' && {env}{task['cmd']} >> '{logf}' 2>&1; echo $? > '{ex}'"
    subprocess.run(['tmux', 'new-session', '-d', '-s', 'task_' + task['name'], cmd], check=True)
    task.update(gpu=gpu if gpu is not None else task.get('gpu'), gpu_id=gpu, started=time.strftime('%Y-%m-%dT%H:%M:%S'))
    move(task, 'queue', 'running'); log(f'start {task["name"]} gpu {gpu}')


def check_running():
    for f in sorted(glob.glob(os.path.join(T, 'running', '*.json'))):
        task = json.load(open(f)); n = task['name']
        if alive(n): continue
        ex = os.path.join(T, 'running', n + '.exit')
        if os.path.exists(ex):
            code = open(ex).read().strip(); os.remove(ex); task['last_exit'] = code
            if code == '0':
                task['finished'] = time.strftime('%Y-%m-%dT%H:%M:%S'); move(task, 'running', 'done'); log(f'done {n}')
            elif task.get('retries', 0) < task.get('max_retries', 1):
                task['retries'] = task.get('retries', 0) + 1; move(task, 'running', 'queue'); log(f'exit {code}: re-queue {n} (retry {task["retries"]})')
            else:
                move(task, 'running', 'failed'); log(f'exit {code}: FAILED {n}')
        else:
            move(task, 'running', 'queue'); log(f'session gone without exit code (restart?): re-queue {n}')


def start_queued():
    q = [json.load(open(f)) for f in glob.glob(os.path.join(T, 'queue', '*.json'))]
    q.sort(key=lambda t: (-t.get('priority', 0), t.get('created', '')))
    mine = {}
    for f in glob.glob(os.path.join(T, 'running', '*.json')):
        g = json.load(open(f)).get('gpu_id')
        if g is not None: mine[g] = mine.get(g, 0) + 1
    free = gpus() if any(t.get('gpu') for t in q) else {}
    hf = host_free_gb()
    for task in q:
        if task.get('host_mem_gb', 4) > hf: continue
        gpu = None
        if task.get('gpu'):
            ok = [g for g, fr in free.items() if fr >= task.get('gpu_mem_gb', 4)]
            if not ok: continue
            gpu = min(ok, key=lambda g: (mine.get(g, 0), -free[g]))
            free[gpu] -= task.get('gpu_mem_gb', 4); mine[gpu] = mine.get(gpu, 0) + 1
        launch(task, gpu); hf -= task.get('host_mem_gb', 4)


def add(spec):
    task = json.load(open(spec)) if os.path.exists(spec) else json.loads(spec)
    task.setdefault('created', time.strftime('%Y-%m-%dT%H:%M:%S'))
    for d in ('queue', 'running'):
        if os.path.exists(os.path.join(T, d, task['name'] + '.json')): print('already', d, task['name']); return
    json.dump(task, open(os.path.join(T, 'queue', task['name'] + '.json'), 'w'), indent=1); log(f'add {task["name"]}')
    print('queued', task['name'])


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == 'add': add(sys.argv[2])
    else:
        check_running(); start_queued()
