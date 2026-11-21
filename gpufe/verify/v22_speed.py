"""V22 first measurement (stage 0, stop rule): wall time of gpufe on the tied p062 deck against the recorded FEBio + cuDSS run of the SAME input, with a per-phase profile.
No FEBio run. Writes results/gpufe_verify/v2/v22_speed_<tag>.json at every increment, so a stopped run still reports.
usage: CUDA_VISIBLE_DEVICES=n python v22_speed.py <case.feb> <budget_s> [tag] [increments_per_step]"""
import os, sys, time, json, numpy as np
from prov import AL, provenance, save
import torch, feb, model as mdl, newton
path, budget = sys.argv[1], float(sys.argv[2]); tag = sys.argv[3] if len(sys.argv) > 3 else 'p062_tied'; inc = int(sys.argv[4]) if len(sys.argv) > 4 else None
OPT = dict(verbose=False, log_every=0); OPT.update(dict(increments_per_step=inc) if inc else {})
T = dict(factor=0.0, solve=0.0, gres=0.0, line_search=0.0, assemble=0.0); N = dict(factor=0, solve=0, gres=0, line_search=0, assemble=0)
def wrap(name, key):
    f = getattr(newton.NewtonSolver, name)
    def g(self, *a, **k):
        t0 = time.time(); r = f(self, *a, **k); T[key] += time.time() - t0; N[key] += 1; return r
    setattr(newton.NewtonSolver, name, g)
for n_, k_ in (('_factor', 'factor'), ('_solve', 'solve'), ('_gres', 'gres'), ('_line_search_energy', 'line_search')): wrap(n_, k_)
t0 = time.time(); m = feb.read(path); M = mdl.build(m); s = newton.NewtonSolver(M, OPT); setup = time.time() - t0
rep = dict(prov=provenance([path], OPT), case=path, setup_s=setup, rows=[], stop=None); t_run = time.time()
class Stop(Exception): pass
def on(sl, row):
    rep['rows'].append(dict(t=sl.t, step=row['step'], iters=row['iters'], cuts=row['cuts'], wall=time.time() - t_run, res=row['res']))
    rep['timers'] = dict(T); rep['calls'] = dict(N); rep['t_end'] = sl.t; rep['wall_s'] = time.time() - t_run; rep['newton_iters'] = sum(r['iters'] for r in rep['rows'])
    save('v22_speed_' + tag, rep); print(f"t {sl.t:.4f} iters {row['iters']} cuts {row['cuts']} wall {rep['wall_s']:.0f}s", flush=True)
    if time.time() - t_run > budget: raise Stop()
try: s.run(on_increment=on); rep['stop'] = 'finished'
except Stop: rep['stop'] = f'budget {budget} s'
except Exception as ex: rep['stop'] = repr(ex)[:400]
rep['wall_s'] = time.time() - t_run; rep['timers'] = dict(T); rep['calls'] = dict(N); rep['t_end'] = float(s.t)
print('saved', save('v22_speed_' + tag, rep), rep['stop'], 't_end', rep['t_end'], 'wall', round(rep['wall_s']), 'timers', {k: round(v) for k, v in T.items()})
