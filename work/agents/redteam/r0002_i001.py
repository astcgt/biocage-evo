"""Red team r0002, I-001: twist (moment about the disc normal Z) on the glued cage faces in all six windows,
re-measured on the physio reruns WITH the fixed load curves (human_study/al_v2/physio_fix/<case>).
Same face / traction method as r0001_i001.py and e02 (element Cauchy stress of the cage contact layer . outward
face normal x face area); also reports the full tangential force (incl. the out-of-plane part, F-0011).
usage: python -I work/agents/redteam/r0002_i001.py p062_gpu2 [p063_gpu3 p014_gpu1]
"""
import site, sys, os
for p in [site.getusersitepackages()]:
    if os.path.isdir(p) and p not in sys.path: sys.path.append(p)
import json, numpy as np, xml.etree.ElementTree as ET
from scipy.spatial import cKDTree
OLD = "/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'common'))
import xplt


def faces_of(cd):
    root = ET.parse(os.path.join(cd, 'case.feb')).getroot(); g = root.find('Geometry')
    X = {int(n.get('id')): np.array([float(v) for v in n.text.split(',')]) for n in g.find('Nodes')}
    blocks = [(eb.get('name'), np.array([[int(v) for v in e.text.split(',')] for e in eb])) for eb in g.findall('Elements')]
    dom = {n: i for i, (n, E) in enumerate(blocks)}; conn = dict(blocks)
    ce = np.load(os.path.join(cd, 'cage_elems.npz')); K = int(ce['K'])
    faces, pos = [], {}
    for b, lay in zip(ce['block'], ce['layer']):
        pos[b] = pos.get(b, -1) + 1
        if 'biodisc' in b or lay not in (0, K - 1): continue
        h = conn[b][pos[b]]; q = h[4:8] if lay == K - 1 else h[0:4]
        Pq = np.array([X[i] for i in q]); nrm = np.cross(Pq[2] - Pq[0], Pq[3] - Pq[1]); A = 0.5 * np.linalg.norm(nrm); nrm /= 2 * A
        sgn = 1.0 if lay == K - 1 else -1.0
        if nrm[2] * sgn < 0: nrm = -nrm
        faces.append((dom[b], pos[b], 'top' if lay == K - 1 else 'bot', nrm, A, Pq.mean(0)))
    return faces


def analyse(cd):
    faces = faces_of(cd)
    pf = xplt.read(os.path.join(cd, 'case.xplt'))
    sch = json.load(open(os.path.join(cd, 'physio_schedule.json')))
    C = np.array([f[5] for f in faces]); side = np.array([f[2] for f in faces]); A = np.array([f[4] for f in faces])
    N_ = np.array([f[3] for f in faces])
    partner = np.full(len(faces), -1); gap = np.full(len(faces), np.nan)
    for s in ('top', 'bot'):
        ii = np.where(side == s)[0]; t = cKDTree(C[ii]); d, j = t.query(C[ii] * [1, -1, 1]); partner[ii] = ii[j]; gap[ii] = d
    rows = []
    for st in pf['states']:
        tt = st['time']; w = next((w for w in sch['windows'] if w['t0'] - 1e-6 <= tt <= w['t1'] + 1e-6), None)
        if w is None: continue
        S = st['elem'].get('stress', {})
        tr = np.zeros((len(faces), 3)); sn = np.zeros(len(faces))
        for k, (di, i, sd, n, a, c) in enumerate(faces):
            s6 = S[di + 1][i]; sig = np.array([[s6[0], s6[3], s6[5]], [s6[3], s6[1], s6[4]], [s6[5], s6[4], s6[2]]])
            tv = sig @ n; sn[k] = n @ tv; tr[k] = tv * a
        r = dict(t=float(tt), window=w['name'])
        for s in ('top', 'bot'):
            m = side == s
            c0 = (C[m] * A[m, None]).sum(0) / A[m].sum(); rr = C[m] - c0
            tau = tr[m] - (sn[m] * A[m])[:, None] * N_[m]
            Mz = float((rr[:, 0] * tau[:, 1] - rr[:, 1] * tau[:, 0]).sum())
            tp = tau[np.searchsorted(np.where(m)[0], partner[m])]
            anti = 0.5 * (tau - tp * [1, -1, 1])
            Mz_anti = float((rr[:, 0] * anti[:, 1] - rr[:, 1] * anti[:, 0]).sum())
            P = np.clip(-sn[m], 0, None) * A[m]
            r[s] = dict(shear_xy=float(np.linalg.norm(tau[:, :2].sum(0))), shear_3d=float(np.linalg.norm(tau.sum(0))),
                        sum_abs_tau=float(np.linalg.norm(tau, axis=1).sum()), N=float(P.sum()), Mz=Mz, Mz_anti=Mz_anti)
        rows.append(r)
    return rows, float(np.median(gap)), float(gap.max())


def main():
    out = {}
    for case in sys.argv[1:] or ['p062_gpu2']:
        cd = os.path.join(OLD, 'human_study/al_v2/physio_fix', case)
        rows, gmed, gmax = analyse(cd)
        summ = {}
        for wn in ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right'):
            R = [r for r in rows if r['window'] == wn]
            if not R: summ[wn] = None; continue
            summ[wn] = {f'{k}_{s}': max(abs(r[s][k]) for r in R) for s in ('top', 'bot') for k in ('Mz', 'Mz_anti', 'shear_xy', 'shear_3d')}
            summ[wn]['M2xy_max'] = max(r[s]['shear_xy'] / r[s]['N'] for r in R for s in ('top', 'bot'))
            summ[wn]['M2_3d_max'] = max(r[s]['shear_3d'] / r[s]['N'] for r in R for s in ('top', 'bot'))
        out[case] = dict(mirror_gap_median=gmed, mirror_gap_max=gmax, windows=summ, rows=rows)
        print(case, 'mirror gap median %.4f max %.4f' % (gmed, gmax))
        for wn, s in summ.items():
            if s is None: print('  %-9s (no states)' % wn); continue
            print('  %-9s max|Mz| top %7.1f bot %7.1f N mm (antisym top %6.1f) | M2 xy %.3f vs 3-D %.3f' % (
                wn, s['Mz_top'], s['Mz_bot'], s['Mz_anti_top'], s['M2xy_max'], s['M2_3d_max']))
    json.dump(out, open(os.path.join(HERE, 'r0002_i001_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
