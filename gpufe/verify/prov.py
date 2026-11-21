"""Provenance block for every verification report (F-0014): code version, input hash, options, host state."""
import os, sys, json, time, hashlib, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); GPUFE = os.path.dirname(HERE); ROOT = os.path.dirname(GPUFE)
OUT = os.path.join(ROOT, 'results/gpufe_verify/v2')
OLD = os.path.join(os.path.dirname(ROOT), 'biocage_simulation_test_oct2026'); AL = os.path.join(OLD, 'human_study/al_v2')
sys.path[:0] = [GPUFE]


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def provenance(inputs=(), opts=None):
    git = lambda *a: subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True).stdout.strip()
    return dict(time=time.strftime('%Y-%m-%d %H:%M:%S'), git=git('rev-parse', '--short', 'HEAD'), dirty_gpufe=bool(git('status', '--short', 'gpufe')),
                inputs={os.path.relpath(p, os.path.dirname(ROOT)): sha(p) for p in inputs}, opts=opts or {}, gpu=os.environ.get('CUDA_VISIBLE_DEVICES'))


def save(name, rep):
    os.makedirs(OUT, exist_ok=True); p = os.path.join(OUT, name + '.json'); tmp = p + '.tmp'
    json.dump(rep, open(tmp, 'w'), indent=1); os.replace(tmp, p); return p
