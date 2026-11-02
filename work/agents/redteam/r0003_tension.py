"""Red team r0003: does the TIED interface carry tension that e02 (M2 / M3 = mu_req) silently counts as friction capacity?
e02 (methods/e02_friction_limit.py:71) keeps P_i = max(-sigma_n, 0) * A_i (tensile elements set to 0) but sums ALL
elements' tangential traction into F and Mz, and the compression it uses is sum(P_i) = N_plus. When part of the glued face is
in tension (glue pulling), N_plus = N_net + T (T = total tensile force), i.e. the glue's tension buys extra friction capacity
that a real (non-adhesive) interface does not have.
For every physio window, at every state, this script reports N_net, N_plus, T and mu_req three ways:
  e02 as is (P_i as above), 'scaled' (P_i * N_net / N_plus: same pattern, total compression = net compression, a crude
  no-tension correction), and the same with the 3-D tangential force (F-0011, out-of-plane part kept in |F|).
usage: python -I work/agents/redteam/r0003_tension.py <case_dir> [...] -> work/agents/redteam/r0003_tension_result.json
"""
import site, sys, os
for p in [site.getusersitepackages()]:
    if os.path.isdir(p) and p not in sys.path: sys.path.append(p)
import json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path[:0] = [os.path.join(ROOT, 'methods'), os.path.join(ROOT, 'common')]
import e02_friction_limit as e02, xplt
sys.path.insert(0, HERE)
from r0002_i001 import faces_of

OLD = "/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1/human_study/al_v2/physio_fix"


def analyse(cd):
    faces = faces_of(cd)
    pf = xplt.read(os.path.join(cd, 'case.xplt'))
    sch = json.load(open(os.path.join(cd, 'physio_schedule.json')))
    out = {}
    for st in pf['states']:
        tt = st['time']; w = next((w for w in sch['windows'] if w['t0'] - 1e-6 <= tt <= w['t1'] + 1e-6), None)
        if w is None: continue
        S = st['elem'].get('stress', {})
        acc = {}
        for di, i, side, n, A, c in faces:
            s6 = S[di + 1][i]; sig = np.array([[s6[0], s6[3], s6[5]], [s6[3], s6[1], s6[4]], [s6[5], s6[4], s6[2]]])
            tv = sig @ n; sn = float(n @ tv); tau = tv - sn * n
            a = acc.setdefault(side, dict(c=[], sn=[], f=[], f3=[], A=[]))
            a['c'].append(c[:2]); a['sn'].append(sn * A); a['f'].append(tau[:2] * A); a['f3'].append(tau * A); a['A'].append(A)
        for side, a in acc.items():
            c = np.array(a['c']); snA = np.array(a['sn']); f = np.array(a['f']); f3 = np.array(a['f3']); Ar = np.array(a['A'])
            c = c - (c * Ar[:, None]).sum(0) / Ar.sum()
            P = np.clip(-snA, 0, None); T = float(np.clip(snA, 0, None).sum()); Nplus = float(P.sum()); Nnet = float(-snA.sum())
            F = f.sum(0); Mz = float((c[:, 0] * f[:, 1] - c[:, 1] * f[:, 0]).sum()); F3 = float(np.linalg.norm(f3.sum(0)))
            s = Nnet / Nplus if Nplus > 0 else np.nan
            r = dict(t=float(tt), side=side, N_net=Nnet, N_plus=Nplus, T=T, tension_frac_of_Nnet=T / Nnet if Nnet > 0 else np.inf,
                     frac_area_tension=float(Ar[snA > 0].sum() / Ar.sum()),
                     M2_e02=float(np.linalg.norm(F) / Nplus), M2_net=float(np.linalg.norm(F) / Nnet) if Nnet > 0 else np.inf,
                     M2_net_3d=F3 / Nnet if Nnet > 0 else np.inf,
                     M3_e02=e02.friction_limit(c, P, F, Mz),
                     M3_net=e02.friction_limit(c, P * s, F, Mz) if Nnet > 0 else np.inf)
            key = w['name']
            o = out.setdefault(key, {})
            # keep the state with the largest M3_net per window and side, and the largest tension
            for crit in ('M3_net', 'T'):
                k2 = f'{side}_max_{crit}'
                if k2 not in o or r[crit] > o[k2][crit]: o[k2] = r
            k3 = f'{side}_max_M3_e02'
            if k3 not in o or r['M3_e02'] > o[k3]['M3_e02']: o[k3] = r
    return out


if __name__ == '__main__':
    res = {}
    for case in sys.argv[1:]:
        res[case] = analyse(os.path.join(OLD, case)); print(case, 'done', flush=True)
    json.dump(res, open(os.path.join(HERE, 'r0003_tension_result.json'), 'w'), indent=1, default=float)
    for case, o in res.items():
        print('==', case)
        print(f"{'window':10s} {'side':4s} {'Nnet':>7s} {'N+':>7s} {'T':>7s} {'T/Nnet':>6s} {'areaT':>5s} {'M2e02':>6s} {'M2net':>6s} {'M2n3d':>6s} {'M3e02':>6s} {'M3net':>6s}")
        for wn, d in o.items():
            for side in ('top', 'bot'):
                for crit in ('max_M3_e02', 'max_M3_net'):
                    r = d.get(f'{side}_{crit}')
                    if r is None: continue
                    print(f"{wn:10s} {side:4s} {r['N_net']:7.1f} {r['N_plus']:7.1f} {r['T']:7.1f} {r['tension_frac_of_Nnet']:6.2f} "
                          f"{r['frac_area_tension']:5.2f} {r['M2_e02']:6.3f} {r['M2_net']:6.3f} {r['M2_net_3d']:6.3f} {r['M3_e02']:6.3f} "
                          f"{r['M3_net']:6.3f}  t={r['t']:.2f} ({crit})")
