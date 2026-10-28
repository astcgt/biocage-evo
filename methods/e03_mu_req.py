"""Minimum friction coefficient needed to hold the cage (mu_req), from a finished tied-contact FEBio run, 3-D version of e02.

PI 2026-10-27: slip-out (dislocation) is judged by calculation first; the whole-face limit counts, local micro-slip does
not. Changes against e02 (red-team findings):
  F-0011  curved faces: every face element keeps its own normal n_i; friction lives in its own tangent plane; the balance
          is the full 3-D tangential force and the full 3-D moment about the face centroid (not only the X-Y part).
  F-0021  the glued interface carries tension a real cage-bone interface cannot. Reported per face: N_net (net compressive
          normal force), T (total tension), and two estimates of mu_req:
            mu_drop  : tension dropped, compressive elements kept at their tied values (e02 rule; optimistic by N+/N_net)
            mu_scaled: compressive element forces scaled by N_net / N+ so their sum is the real net normal force
                       (red-team option 2; closer to a non-adhesive contact, still an estimate)
          plus tension_frac = T / N_net as a validity flag of the tied solution.
  F-0007  a window counts only if its peak state exists; the case summary says which windows are missing; provenance.
LP (both estimates): minimise mu s.t. f_i = sum_k lambda_ik (a_k t1_i + b_k t2_i), lambda >= 0, sum_k lambda_ik <= mu P_i
(16-gon inscribed in the friction circle: conservative by < 2 %); friction must carry the in-plane force (2 components
about the area-mean normal nb) and the twist about nb that the glue carries beyond what the normal forces P_i n_i carry (on
a curved face the tilted normal forces carry part of the in-plane load); the normal force and the bending moments are
carried by the pressure distribution, not by friction.
usage: python e03_mu_req.py <case_dir> [out.json]     python e03_mu_req.py --test
"""
import sys, os, json, hashlib, subprocess, numpy as np, xml.etree.ElementTree as ET
from scipy.optimize import linprog
from scipy.sparse import csr_matrix
sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'common')]

M_POLY = 16
ANG = 2 * np.pi * np.arange(M_POLY) / M_POLY


def basis(n):
    a = np.where(np.abs(n[:, 0:1]) < 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
    t1 = np.cross(n, a); t1 /= np.linalg.norm(t1, axis=1, keepdims=True); t2 = np.cross(n, t1)
    return t1, t2


def mu_limit(r, n, P, F, M):
    """r (m,3) element centres about the face centroid, n (m,3) unit normals, P (m,) compressive normal forces (>= 0),
    F (3,), M (3,): the wrench friction must carry. Smallest mu, inf if no compression, nan if infeasible."""
    keep = P > 1e-9 * max(P.max(), 1e-30) if len(P) else P > 0
    r, n, P = r[keep], n[keep], P[keep]; m = len(P)
    if m == 0: return float('inf')
    t1, t2 = basis(n)
    D = np.cos(ANG)[None, :, None] * t1[:, None, :] + np.sin(ANG)[None, :, None] * t2[:, None, :]       # (m, K, 3)
    Mo = np.cross(r[:, None, :], D)                                                                    # (m, K, 3)
    nv = m * M_POLY + 1
    # friction carries the in-plane force (2 components about the area-mean normal nb) and the twist about nb; the normal
    # force and the bending moments are carried by the pressure distribution (P fixed), so they are not friction equations
    nb = n.mean(0); nb /= np.linalg.norm(nb); e1, e2 = basis(nb[None])[0][0], basis(nb[None])[1][0]
    E = np.stack([e1, e2]); Aeq = np.zeros((3, nv))
    Aeq[:2, :-1] = E @ D.reshape(-1, 3).T; Aeq[2, :-1] = Mo.reshape(-1, 3) @ nb
    beq = np.r_[E @ F, nb @ M]
    rows = np.repeat(np.arange(m), M_POLY)
    Aub = csr_matrix((np.r_[np.ones(m * M_POLY), -P], (np.r_[rows, np.arange(m)], np.r_[np.arange(m * M_POLY), np.full(m, nv - 1)])), shape=(m, nv))
    cost = np.zeros(nv); cost[-1] = 1.0
    res = linprog(cost, A_ub=Aub, b_ub=np.zeros(m), A_eq=Aeq, b_eq=beq, bounds=(0, None), method='highs')
    return float(res.x[-1]) if res.status == 0 else float('nan')


def face_mu(c, n, A, tv):
    """c, n (m,3) element centres / normals, A (m,), tv (m,3) traction on the face (from the cage side) -> dict."""
    w = A / A.sum(); c0 = (c * w[:, None]).sum(0); r = c - c0
    f = tv * A[:, None]                                        # glue force on each element
    pn = -(tv * n).sum(1) * A                                  # compressive normal force (+), tension (-)
    Pp = np.clip(pn, 0, None); T = float(np.clip(-pn, 0, None).sum()); Nplus = float(Pp.sum()); Nnet = Nplus - T
    Ftot = f.sum(0); Mtot = np.cross(r, f).sum(0)
    out = dict(N_net=Nnet, N_plus=Nplus, T=T, tension_frac=T / Nnet if Nnet > 0 else float('inf'))
    for key, Puse in (('mu_drop', Pp), ('mu_scaled', Pp * (max(Nnet, 0) / Nplus if Nplus > 0 else 0))):
        Fn = (Puse[:, None] * -n).sum(0); Mn = np.cross(r, Puse[:, None] * -n).sum(0)   # what the normal forces carry
        out[key] = mu_limit(r, n, Puse, Ftot - Fn, Mtot - Mn) if Nnet > 0 else float('inf')
    out['mu_force'] = float(np.linalg.norm(Ftot - (Pp[:, None] * -n).sum(0)) / Nplus) if Nplus > 0 else float('inf')
    return out


def target_times(cd, sch):
    """rotation control (physio_rot, PI 2026-10-28): per window the first logged time in the up-ramp at which the C3 reaction
    moment about the window's axis reaches the target; moment control: the window peak. -> {name: (t, reached, M)}."""
    out = {}
    if sch.get('control') != 'rotation':
        return {w['name']: ((w['t0'] + w['t1']) / 2, True, None) for w in sch['windows']}
    # driving moment = the moment the joint of the window applies to C3 (drive.txt, rigid_connector_data, joint i = window i;
    # needs the BIOCAGE FEGenericRigidJoint output patch 2026-10-28)
    col = dict(Rx=4, Ry=5, Rz=6); rows, t = [], None
    for line in open(os.path.join(cd, 'drive.txt')):
        if line.startswith('*Time'): t = float(line.split('=')[1]); rows.append((t, {}))
        elif line[:1].isdigit() and t is not None: v = line.split(','); rows[-1][1][int(v[0])] = [float(a) for a in v]
    for i, w in enumerate(sch['windows']):
        up = [(tt, d[i + 1][col[w['dof']]]) for tt, d in rows if (i + 1) in d and w['t0'] + 1e-9 < tt <= w['t_peak'] + 1e-9]
        hit = next(((tt, m) for tt, m in up if abs(m) >= sch['target_moment_Nmm']), None)
        out[w['name']] = (hit[0], True, hit[1]) if hit else ((up[-1][0], False, up[-1][1]) if up else (w['t_peak'], False, None))
    return out


def provenance(cd):
    h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.exists(p) else None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git = subprocess.run(['git', '-C', root, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', '-C', root, 'status', '--porcelain', 'methods/e03_mu_req.py'], capture_output=True, text=True).stdout.strip())
    return dict(git=git, script_dirty=dirty, script_sha256=h(os.path.abspath(__file__)), case_feb=h(os.path.join(cd, 'case.feb')),
                case_xplt=h(os.path.join(cd, 'case.xplt')))


def main(cd, out=None):
    import xplt
    case = json.load(open(os.path.join(cd, 'case.json'))); prm = case['params']
    assert prm.get('contact_type') == 'tied', 'needs a tied run'
    root = ET.parse(os.path.join(cd, 'case.feb')).getroot(); g = root.find('Geometry')
    X = {int(nd.get('id')): np.array([float(v) for v in nd.text.split(',')]) for nd in g.find('Nodes')}
    blocks = [(eb.get('name'), np.array([[int(v) for v in e.text.split(',')] for e in eb])) for eb in g.findall('Elements')]
    dom = {nm: i for i, (nm, E) in enumerate(blocks)}; conn = dict(blocks)
    ce = np.load(os.path.join(cd, 'cage_elems.npz')); K = int(ce['K'])
    faces, pos = [], {}
    for b, lay in zip(ce['block'], ce['layer']):
        pos[b] = pos.get(b, -1) + 1
        if 'biodisc' in b or lay not in (0, K - 1): continue
        h = conn[b][pos[b]]; q = h[4:8] if lay == K - 1 else h[0:4]
        Pq = np.array([X[i] for i in q]); nrm = np.cross(Pq[2] - Pq[0], Pq[3] - Pq[1]); A = 0.5 * np.linalg.norm(nrm); nrm /= 2 * A
        sgn = 1.0 if lay == K - 1 else -1.0
        if nrm[2] * sgn < 0: nrm = -nrm                          # outward from the cage (towards the vertebra)
        faces.append((dom[b], pos[b], 'top' if lay == K - 1 else 'bot', nrm, A, Pq.mean(0)))
    pf = xplt.read(os.path.join(cd, 'case.xplt')); states = pf['states']
    sch = json.load(open(os.path.join(cd, 'physio_schedule.json')))
    rows = []
    for st in states:
        tt = st['time']; w = next((w for w in sch['windows'] if w['t0'] - 1e-6 <= tt <= w['t1'] + 1e-6), None)
        if w is None: continue
        S = st['elem'].get('stress', {}); acc = {}
        for di, i, side, nv, A, c in faces:
            Sg = S.get(di + 1)
            if Sg is None: continue
            s6 = Sg[i]; sig = np.array([[s6[0], s6[3], s6[5]], [s6[3], s6[1], s6[4]], [s6[5], s6[4], s6[2]]])
            a = acc.setdefault(side, dict(c=[], n=[], A=[], t=[]))
            a['c'].append(c); a['n'].append(nv); a['A'].append(A); a['t'].append(sig @ nv)
        r = dict(t=tt, window=w['name'])
        for side, a in acc.items():
            r[side] = face_mu(np.array(a['c']), np.array(a['n']), np.array(a['A']), np.array(a['t']))
        rows.append(r)
    per, missing = {}, []; tt_ = target_times(cd, sch)
    for w in sch['windows']:
        peak, reached, Mhit = tt_[w['name']]
        rw = [r for r in rows if r['window'] == w['name'] and r['t'] <= peak + 1e-6]          # up to the target moment
        if not rw or max(r['t'] for r in rw) < peak - 1e-6: missing.append(w['name']); continue
        f = lambda key, agg=max: agg(max(r[s][key] for s in ('top', 'bot') if s in r) for r in rw)
        per[w['name']] = dict(n_states=len(rw), mu_drop=f('mu_drop'), mu_scaled=f('mu_scaled'), mu_force=f('mu_force'),
                              tension_frac_max=f('tension_frac'), t_target=peak, target_reached=reached, M_at_target=Mhit)
    worst = dict(mu_drop=max([v['mu_drop'] for v in per.values()], default=float('nan')),
                 mu_scaled=max([v['mu_scaled'] for v in per.values()], default=float('nan')),
                 governing=max(per, key=lambda k: per[k]['mu_scaled']) if per else None)
    res = dict(case=cd, complete=not missing, windows_missing=missing, windows=per, worst=worst if not missing else 'incomplete',
               provenance=provenance(cd))
    if out: json.dump(dict(res, states=rows), open(out, 'w'), indent=1)
    return res


def selftest():
    """analytic checks: (1) flat face under shear Q and normal N, uniform pressure: mu = Q / N; (2) flat disc, uniform
    pressure, pure twist T: spin limit T = 2/3 mu N R (Goyal 1991) -> mu = 1.5 T / (N R); (3) block on a plane tilted by
    theta carrying a vertical load W: mu = tan(theta) (F-0011 check); (4) half the face in tension: mu_scaled > mu_drop."""
    g = np.linspace(-1, 1, 41); X, Y = np.meshgrid(g, g); m = X.ravel() ** 2 + Y.ravel() ** 2 <= 1
    c = np.c_[X.ravel()[m], Y.ravel()[m], 0 * X.ravel()[m]]; A = np.full(len(c), (2 / 40) ** 2); nz = np.tile([0, 0, 1.0], (len(c), 1))
    N, Q = 100.0, 30.0; p = N / A.sum()
    t = np.tile([Q / A.sum(), 0, -p], (len(c), 1)); r1 = face_mu(c, nz, A, t)['mu_drop']
    T = 20.0; rr = np.linalg.norm(c[:, :2], axis=1); J = (A * rr ** 2).sum()
    tw = np.c_[-c[:, 1] * T / J, c[:, 0] * T / J, -p * np.ones(len(c))]; r2 = face_mu(c, nz, A, tw)['mu_drop']
    th = np.radians(15); nn = np.tile([np.sin(th), 0, np.cos(th)], (len(c), 1)); R = np.array([[np.cos(th), 0, np.sin(th)], [0, 1, 0], [-np.sin(th), 0, np.cos(th)]])
    ct = c @ R.T; W = 100.0; tt = np.tile([0, 0, -W / A.sum()], (len(c), 1)); r3 = face_mu(ct, nn, A, tt)['mu_drop']
    pt = np.where(c[:, 0] > 0, -2 * p, 0.5 * p); tq = np.c_[np.full(len(c), Q / A.sum()), 0 * pt, pt]; r4 = face_mu(c, nz, A, tq)
    checks = [('flat shear Q/N', r1, Q / N), ('disc twist 1.5T/(NR)', r2, 1.5 * T / (N * 1.0)), ('15 deg incline tan', r3, np.tan(th))]
    ok = True
    for name, got, want in checks:
        e = abs(got - want) / want; ok &= e < 0.03
        print(f'{name:22s} got {got:.4f} want {want:.4f} rel err {e:.3%}')
    print(f"half tension: mu_drop {r4['mu_drop']:.4f} mu_scaled {r4['mu_scaled']:.4f} tension_frac {r4['tension_frac']:.3f}")
    ok &= r4['mu_scaled'] > r4['mu_drop']
    print('SELFTEST', 'PASS' if ok else 'FAIL'); return ok


if __name__ == '__main__':
    if sys.argv[1] == '--test': sys.exit(0 if selftest() else 1)
    r = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps({k: v for k, v in r.items() if k != 'provenance'}, indent=1))
