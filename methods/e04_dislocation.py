"""Can the cage dislocate? Slip-mode screen on a finished tied physio run (PI 2026-10-28: answer first with this method).

Dislocation (PI 2026-10-27) = the cage as a whole moving out of the disc space. For that the cage must slide against BOTH
endplates in the same sense (squeezed out, like a seed between two fingers). Slip at ONE face only means the cage moves
with the other vertebra: its slip is bounded by the relative motion of the two vertebrae at the cage, i.e. by the
physiological segment motion, and reverses with the load.
Per window peak state:
  1. squeeze-out demand: the net force and twist that the surrounding tissue (annulus, biodisc, facets via the vertebrae)
     puts on the cage = the sum over BOTH glued faces of the interface forces / moments on the cage. mu_squeeze = the
     least friction coefficient for which the friction of both faces together (each element in its own tangent plane,
     |f_i| <= mu P_i, P_i compressive force scaled to the face's net normal force: F-0021 option 2) can carry the
     horizontal part of that net force and its twist about the vertical (limit surface LP of e03). mu_squeeze <= mu means
     no rigid-body slip relative to both endplates is possible.
  2. one-face slip bound: horizontal relative displacement between C3 (rigid potting motion) and C4 (endplate nodes) over
     the cage footprint (max over the top-face element centres) -> the most a face can slip if the cage sticks to the
     other vertebra; plus the cage's own rigid-body translation in the tied run (best fit of all cage nodes, vs C4).
Evaluation state (2026-11-02): the metrics are computed at the two logged states bracketing the target moment and
interpolated linearly to it (e03.target_bracket; T07 overshoot removed); states with a micro time step, a rigid-body dynamic
residual above 2 % (retried / chattering steps, NUM-14) or a moment jump are never used (T02). Output per window adds 'eval'
(bracket) and 'window_check' (integrity: rows, invalid states, n_dyn, rb_res_max, monotonic, complete).
usage: python e04_dislocation.py <case_dir> [out.json]     python e04_dislocation.py --test
"""
import sys, os, json, numpy as np, xml.etree.ElementTree as ET
sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p) for p in ('common', 'methods')]
import e03_mu_req as e3


def read_log(path):
    """FEBio node / rigid log -> {time: {id: values}}."""
    out, t = {}, None
    for line in open(path):
        if line.startswith('*Time'): t = float(line.split('=')[1]); out[t] = {}
        elif line[:1].isdigit() and t is not None:
            v = line.split(','); out[t][int(v[0])] = np.array([float(a) for a in v[1:]])
    return out


def nearest(d, t):
    k = min(d, key=lambda a: abs(a - t)); return d[k], k


def rigid_com(root, mat_id='2'):
    """volume-weighted centroid of the C3 potting rigid body (material 2 'Forced', the body logged in C3pot.txt; its
    x, y, z are displacements of this point)."""
    rid = [mat_id]
    m = next((m for m in root.find('Material') if m.get('id') == mat_id), None)
    if m is not None and m.find('center_of_mass') is not None:                  # FEBio uses a given centre of mass as is
        X = {int(n.get('id')): np.array([float(v) for v in n.text.split(',')]) for n in root.find('Geometry').find('Nodes')}
        return np.array([float(v) for v in m.find('center_of_mass').text.split(',')]), X
    X = {int(n.get('id')): np.array([float(v) for v in n.text.split(',')]) for n in root.find('Geometry').find('Nodes')}
    vs, cs = [], []
    for eb in root.find('Geometry').findall('Elements'):
        if eb.get('mat') not in rid: continue
        for e in eb:
            P = np.array([X[int(v)] for v in e.text.split(',')[:4]])
            vs.append(abs(np.linalg.det((P[1:] - P[0]).T)) / 6); cs.append(P.mean(0))
    vs, cs = np.array(vs), np.array(cs)
    return (cs * vs[:, None]).sum(0) / vs.sum(), X


def main(cd, out=None):
    import xplt
    root = ET.parse(os.path.join(cd, 'case.feb')).getroot(); g = root.find('Geometry')
    com, X = rigid_com(root)
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
        if nrm[2] * sgn < 0: nrm = -nrm
        faces.append((dom[b], pos[b], 'top' if lay == K - 1 else 'bot', nrm, A, Pq.mean(0)))
    pf = xplt.read(os.path.join(cd, 'case.xplt')); states = pf['states']
    sch = json.load(open(os.path.join(cd, 'physio_schedule.json')))
    c3 = read_log(os.path.join(cd, 'C3pot.txt')); cn = read_log(os.path.join(cd, 'cage_nodes.txt'))
    c4 = read_log(os.path.join(cd, 'C4_endplate_nodes.txt'))
    res = {}; br = e3.target_bracket(cd, sch)
    for w in sch['windows']:
        # evaluation state (2026-11-02): metrics at the two logged states that bracket the target moment, interpolated
        # linearly to the target (T07); micro-step / jump states are never used (T02; e03.target_bracket)
        k = br[w['name']]
        sa, sb = e3.state_at(states, k['t_a']), e3.state_at(states, k['t_b'])
        if sa is None or sb is None: res[w['name']] = 'missing'; continue
        ma = metrics_at(sa, faces, com, c3, cn, c4)
        m = e3.lerp(ma, metrics_at(sb, faces, com, c3, cn, c4), k['frac']) if sb is not sa and k['frac'] > 0 else ma
        res[w['name']] = dict(t=k['t'], target_reached=k['reached'], M_at_target=k['M'], **m,
                              eval=dict(t_a=k['t_a'], M_a=k['M_a'], t_b=k['t_b'], M_b=k['M_b'], frac=k['frac'], coarse=k['coarse'], invalid=k['invalid']),
                              window_check=k['check'])
    out_d = dict(case=cd, windows=res, provenance=e3.provenance(cd))
    if out: json.dump(out_d, open(out, 'w'), indent=1)
    return out_d


def metrics_at(st, faces, com, c3, cn, c4):
    """slip-mode metrics of one xplt state -> dict (mu_squeeze, net_push_N, net_twist_Nmm, N_total, one_face_slip_bound_mm,
    cage_translation_tied_mm)."""
    S = st['elem']['stress']; per = {}
    for di, i, side, nv, A, c in faces:
        s6 = S[di + 1][i]; sig = np.array([[s6[0], s6[3], s6[5]], [s6[3], s6[1], s6[4]], [s6[5], s6[4], s6[2]]])
        a = per.setdefault(side, dict(c=[], n=[], A=[], t=[])); a['c'].append(c); a['n'].append(nv); a['A'].append(A); a['t'].append(sig @ nv)
    # 1. squeeze-out: both faces together
    C, N, Ar, T, Pn, nup = [], [], [], [], [], []
    for side, a in per.items():
        c_, n_, A_, t_ = (np.array(a[k]) for k in ('c', 'n', 'A', 't'))
        pn = -(t_ * n_).sum(1) * A_; Pp = np.clip(pn, 0, None); Nnet = Pp.sum() - np.clip(-pn, 0, None).sum()
        C.append(c_); N.append(n_); Ar.append(A_); T.append(t_); Pn.append(Pp * (max(Nnet, 0) / Pp.sum() if Pp.sum() > 0 else 0))
        nup.append(n_ * (1 if side == 'top' else -1))
    C, N, Ar, T, Pn, nup = (np.concatenate(v) for v in (C, N, Ar, T, Pn, nup))
    c0 = (C * Ar[:, None]).sum(0) / Ar.sum(); r = C - c0
    f = T * Ar[:, None]; Fnet = f.sum(0); Mnet = np.cross(r, f).sum(0)            # what the tissue pushes on the cage
    Fn = (Pn[:, None] * -N).sum(0); Mn = np.cross(r, Pn[:, None] * -N).sum(0)     # what the (scaled) pressures carry
    mu_sq = e3.mu_limit(r, nup, Pn, Fnet - Fn, Mnet - Mn)                         # nup: one up-normal for the plane
    # 2. one-face slip bound: C3 rigid motion vs C4 endplate at the top-face element centres
    rv, tk = nearest(c3, st['time']); x, th = rv[2][:3], rv[2][3:6]
    top = np.array(per['top']['c']); uC3 = x + np.cross(th, top - com)
    u4 = np.array(list(nearest(c4, st['time'])[0].values())).mean(0)
    rel = uC3 - u4; slip_bound = float(np.linalg.norm(rel[:, :2], axis=1).max())
    # cage rigid-body translation in the tied run (relative to C4): mean of cage node displacements
    uc = np.array(list(nearest(cn, st['time'])[0].values())).mean(0) - u4
    return dict(mu_squeeze=mu_sq, net_push_N=float(np.linalg.norm((Fnet - Fn)[:2])), net_twist_Nmm=float(abs((Mnet - Mn)[2])),
                N_total=float(Pn.sum()), one_face_slip_bound_mm=slip_bound, cage_translation_tied_mm=uc.tolist())


def selftest():
    """(1) e03 bracket + lerp self-tests; (2) a flat 2 x 2 face patch under uniform pressure p and shear q, with the C3 pot
    translated by (dx, dy): mu_squeeze = q/p (both faces together carry the shear), one-face slip bound = |(dx, dy)| when C4
    does not move, cage translation = the mean cage node displacement."""
    ok = e3.bracket_selftest()
    g = np.linspace(-0.75, 0.75, 4); X, Y = np.meshgrid(g, g); A = 0.25; faces = []
    for side, z, sgn in (('top', 1.0, 1.0), ('bot', 0.0, -1.0)):
        for x, y in zip(X.ravel(), Y.ravel()):
            faces.append((0, len(faces), side, np.array([0, 0, sgn]), A, np.array([x, y, z])))
    p, q = 1.0, 0.3
    S = {1: []}
    for di, i, side, nv, A_, c in faces:                 # Cauchy stress whose traction sig @ n is q e_x in-plane and -p n (compression)
        sig = np.zeros((3, 3)); sig[2, 2] = -p; sig[0, 2] = sig[2, 0] = q * nv[2]
        S[1].append([sig[0, 0], sig[1, 1], sig[2, 2], sig[0, 1], sig[1, 2], sig[0, 2]])
    st = dict(time=3.9, elem={'stress': {1: S[1]}})
    dx, dy = 0.12, -0.05
    c3 = {3.9: {2: np.array([dx, dy, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])}}
    cn = {3.9: {1: np.array([0.07, 0.0, 0.0]), 2: np.array([0.09, 0.0, 0.0])}}
    c4 = {3.9: {1: np.zeros(3), 2: np.zeros(3)}}
    m = metrics_at(st, faces, np.zeros(3), c3, cn, c4)
    checks = [('mu_squeeze q/p', m['mu_squeeze'], q / p), ('one-face slip |u|', m['one_face_slip_bound_mm'], np.hypot(dx, dy)),
              ('cage translation x', m['cage_translation_tied_mm'][0], 0.08), ('N_total', m['N_total'], 2 * 16 * A * p)]
    for name, got, want in checks:
        e = abs(got - want) / want; ok &= e < 0.03; print(f'{name:22s} got {got:.4f} want {want:.4f} rel err {e:.3%}')
    print('SELFTEST', 'PASS' if ok else 'FAIL'); return ok


if __name__ == '__main__':
    if sys.argv[1] == '--test': sys.exit(0 if selftest() else 1)
    r = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(r['windows'], indent=1))
