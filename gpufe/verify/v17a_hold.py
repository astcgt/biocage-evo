"""V17(a): FEBio hold at a fixed angle. Same ramp as production to about the intact ROM (t 3.9), then the C3 angle is held to t 4.4 with dtmax 0.05 (class pilot_holdA, about 10 increments)
or 0.0125 (pilot_holdB, about 40 increments). Coulomb friction with stick memory: no drift once the dynamic transient has settled. FEBio stick-point reset: drift grows with the number of increments.
Reports cage translation relative to C4 (same metric as e04) at the start and end of the hold, drift per increment over the second half, and a stuck-fraction proxy is not used.
usage: python v17a_hold.py"""
import os, sys, json, glob, re, numpy as np
from prov import AL, ROOT, provenance, save
sys.path[:0] = [os.path.join(ROOT, 'methods'), os.path.join(ROOT, 'common')]
import e04_dislocation as e4
rep = dict(prov=provenance(), cases=[]); T0, T1 = 3.9, 4.4
for c in ('pilot_holdA', 'pilot_holdB', 'pilot_holdC', 'pilot_holdD', 'pilot_holdE'):
    for d in sorted(glob.glob(os.path.join(AL, c, 'p*_gpu*'))):
        for wn in ('flexion', 'extension'):
            cd = f'{d}/w_{wn}'; log = cd + '/case.log'
            if not os.path.exists(cd + '/cage_nodes.txt'): continue
            txt = open(log, errors='ignore').read(); st = 'NORMAL' if 'N O R M A L' in txt[-4000:] else ('ERROR' if 'E R R O R' in txt[-4000:] else 'running')
            cn = e4.read_log(cd + '/cage_nodes.txt'); c4 = e4.read_log(cd + '/C4_endplate_nodes.txt'); c3 = e4.read_log(cd + '/C3pot.txt'); ts = sorted(cn)
            U = {}
            for t in ts:
                u = np.array(list(e4.nearest(cn, t)[0].values())).mean(0) - np.array(list(e4.nearest(c4, t)[0].values())).mean(0); U[t] = u
            hold = [t for t in ts if T0 - 1e-6 <= t <= T1 + 1e-6]
            if len(hold) < 2: rep['cases'].append(dict(set=c, dir=os.path.basename(d), window=wn, state=st, t_last=ts[-1] if ts else None)); continue
            h = np.array([np.hypot(*U[t][:2]) for t in hold]); post = np.array([-U[t][0] for t in hold]); th = [float(np.linalg.norm(e4.nearest(c3, t)[0][2][3:6])) for t in hold]
            half = [i for i, t in enumerate(hold) if t >= 0.5 * (hold[0] + hold[-1])]
            rep['cases'].append(dict(set=c, dir=os.path.basename(d), window=wn, state=st, t_last=hold[-1], n_hold=len(hold) - 1, u_h_start=float(h[0]), u_h_end=float(h[-1]), post_start=float(post[0]), post_end=float(post[-1]),
                                     drift_total_mm=float(h[-1] - h[0]), drift_per_inc_second_half_mm=float((h[half[-1]] - h[half[0]]) / max(len(half) - 1, 1)), rot_start_deg=float(np.degrees(th[0])), rot_end_deg=float(np.degrees(th[-1]))))
print(f"{'set':12s}{'dir':11s}{'win':10s}{'state':8s}{'n':>4s}{'u_start':>9s}{'u_end':>8s}{'drift':>9s}{'per inc(2nd half)':>19s}{'rot deg':>15s}")
for r in rep['cases']:
    if 'n_hold' in r: print(f"{r['set']:12s}{r['dir']:11s}{r['window']:10s}{r['state']:8s}{r['n_hold']:4d}{r['u_h_start']:9.4f}{r['u_h_end']:8.4f}{r['drift_total_mm']:9.4f}{r['drift_per_inc_second_half_mm']:19.6f}{r['rot_start_deg']:8.3f}{r['rot_end_deg']:7.3f}")
    else: print(f"{r['set']:12s}{r['dir']:11s}{r['window']:10s}{r['state']:8s} t_last {r['t_last']}")
print('saved', save('v17a_hold', rep))
