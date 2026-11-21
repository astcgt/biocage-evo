"""V17(e): does FEBio's augmented Lagrangian remove the hold creep on the verifier's block pair (V07 deck)? Coulomb answer: hold creep 0.
laugon 0 = production cage setting. laugon 1 keeps the tangential multiplier across increments (t = Lt + eps dg, Zimmerman & Ateshian 2018 section 2.6.2).
Benchmark deck, not a production case, so no h24. usage: python v17e_block_al.py"""
import os, sys, re, json, importlib.util, shutil, subprocess, numpy as np
from prov import ROOT, provenance, save
os.environ.setdefault('V07_RATIO', '0.5')
sp = importlib.util.spec_from_file_location('v07', os.path.join(ROOT, 'work/agents/verifier/v07_stick_creep.py')); v = importlib.util.module_from_spec(sp); sp.loader.exec_module(v)
W = os.path.join(ROOT, 'results/gpufe_verify/v2/v17e_block_al'); rep = dict(prov=provenance(), rows=[])
for ratio in (0.5, 0.9):
    v.RATIO = ratio
    for E in (10, 400):
        for n in (10, 40):
            for lag in (0, 1):
                d = f'{W}/r{ratio}_E{E}_n{n}_L{lag}'; shutil.rmtree(d, ignore_errors=True); os.makedirs(d); fp = d + '/case.feb'
                v.write(fp, E, n); s = open(fp).read()
                if lag: s = s.replace('<laugon>0</laugon>', '<laugon>1</laugon><tolerance>0.01</tolerance><gaptol>0</gaptol><minaug>1</minaug><maxaug>20</maxaug>')
                open(fp, 'w').write(s)
                try: ok, R = v.febio(d)
                except Exception as ex: rep['rows'].append(dict(ratio=ratio, E=E, n=n, laugon=lag, error=repr(ex)[:200])); print(ratio, E, n, lag, 'ERR', repr(ex)[:120]); continue
                ts = np.array(sorted(R)); x = np.array([R[t][0] for t in ts]) if len(ts) else np.array([])
                at = lambda T: float(np.interp(T, ts, x)) if len(ts) and ts[-1] >= T - 1e-9 else None
                x05, x10 = at(0.5), at(1.0); hold_inc = int(((ts > 0.5 + 1e-9) & (ts <= 1 + 1e-9)).sum()) if len(ts) else 0
                r = dict(ratio=ratio, E=E, n=n, laugon=lag, normal=ok, t_last=float(ts[-1]) if len(ts) else None, hold_inc=hold_inc, x05=x05, x10=x10, creep=(x10 - x05) if x05 is not None and x10 is not None else None); rep['rows'].append(r)
                print(f"ratio {ratio} E {E:3d} n {n:2d} laugon {lag} ok {ok} t_last {r['t_last']} hold_inc {hold_inc}: x(0.5) {x05} hold creep {r['creep']}", flush=True)
print('saved', save('v17e_block_al', rep))
