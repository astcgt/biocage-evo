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


DT_MIN, JUMP_REL, JUMP_ABS, FIRST_MAX = 1e-4, 1.0, 0.15, 3.0   # evaluation-state filter (2026-11-02, [數值] NUM-04 / [觀測] OBS-03)
DYN_M, DYN_F = 0.02, None                        # rigid-body dynamic residual limit (NUM-14): |M_rb| as a fraction of the target moment. The force
# residual is reported (rb_fres_max) but not a criterion: states with 2-7 N off the follower and |M_rb| < 30 N mm (p092 flexion,
# p130 extension, p083 LB_left) have slip / mu / N trajectories smooth to < 0.5 % - convergence slack, not a dynamic transient.
COL = dict(Rx=4, Ry=5, Rz=6)                     # drive.txt row: id, RCFx, RCFy, RCFz, RCMx, RCMy, RCMz


def filter_rows(rows, t0, Mt, dyn=None, Fref=None):
    """[(t, M)] of one window's up-ramp -> (valid [(t, dt, M)], invalid [[t, dt, M, why, ...]]).
    dropped: 'dt' a step shorter than DT_MIN (must-point / step-end micro-step: spurious inertia in slow dynamics);
    'dyn' (2026-11-02 evening, NUM-14) a state whose driven rigid body is not in quasi-static balance: dyn[t] = (|M_rb|, |F_rb -
    F_ref|) from C3pot.txt exceeds DYN_M x target (or DYN_F x Fref when DYN_F is set). FEBio's logged rigid-body reaction (m_Fr / m_Mr, the
    assembled residual contributions on the body) is (0, 0, -follower, 0, 0, 0) in every converged quasi-static state; after a
    retried / cut step or during contact chatter it carries the body's inertial residual, and the joint moment is off by the
    same amount (p062 extension: retry step 3.9455, drive 1360 with M_rb 184 vs 1535 from the neighbours; p052 extension
    2532 vs 734 with M_rb 1795 - correcting by the axial residual brings the big spikes back to < 1 %). Such states are
    dropped, not repaired (the correction is unreliable inside unstable windows);
    'jump' an isolated spike: the moment differs from the value its neighbours predict - linear interpolation between the
    previous kept row and the next raw row, or for the last row the extrapolation of the last two kept rows - by more than
    max(JUMP_ABS x target, JUMP_REL x |predicted|) (p100 LB_right 171 -> 6798 -> 438 N mm; p093 extension 1807 -> 4288 ->
    2150; p015 extension 1310 -> -13516 -> 3250 at the blow-up of an ERROR window); a first row above FIRST_MAX x target.
    Judging each row against its own neighbours means a legitimate ramp (including the sign crossing at the start of an
    extension window, or an atypically small first row) is never dropped as a block, and a spike cannot cascade."""
    pts, invalid, tp = [], [], t0
    for t, m in rows:
        dt = t - tp
        if dt < DT_MIN: invalid.append([t, dt, m, 'dt']); continue
        tp = t
        if dyn and t in dyn and (dyn[t][0] > DYN_M * Mt or (DYN_F and Fref and dyn[t][1] > DYN_F * Fref)):
            invalid.append([t, dt, m, 'dyn', round(dyn[t][0], 1), round(dyn[t][1], 2)]); continue
        pts.append((t, dt, m))
    acc = []
    for n, (t, dt, m) in enumerate(pts):
        if not acc: bad = abs(m) > FIRST_MAX * Mt
        else:                                   # a row is kept when EITHER prediction fits it: the interpolation with the next
            ta, _, ma = acc[-1]; preds = []     # raw row fails for the row just before a spike, the extrapolation then rescues it
            if n + 1 < len(pts): tn, _, mn = pts[n + 1]; preds.append(ma + (mn - ma) * (t - ta) / (tn - ta))
            if len(acc) >= 2: tb, _, mb = acc[-2]; preds.append(ma + (ma - mb) / (ta - tb) * (t - ta))
            else: preds.append(ma * (t - t0) / (ta - t0))
            bad = all(abs(m - p) > max(JUMP_ABS * Mt, JUMP_REL * abs(p)) for p in preds)
        if bad: invalid.append([t, dt, m, 'jump']); continue
        acc.append((t, dt, m))
    invalid.sort(key=lambda r: r[0])
    return acc, invalid


def drive_rows(cd):
    """drive.txt (rigid_connector_data) -> [(t, {joint_id: [id, RCFx, RCFy, RCFz, RCMx, RCMy, RCMz]})] in file order."""
    rows, t = [], None
    for line in open(os.path.join(cd, 'drive.txt')):
        if line.startswith('*Time'): t = float(line.split('=')[1]); rows.append((t, {}))
        elif line[:1].isdigit() and t is not None: v = line.split(','); rows[-1][1][int(v[0])] = [float(a) for a in v]
    return rows


def rb_rows(cd):
    """C3pot.txt (rigid_body_data x;y;z;thx;thy;thz;Fx;Fy;Fz;Mx;My;Mz of the driven C3 pot) -> {t: [12 values]}, None if absent."""
    f = os.path.join(cd, 'C3pot.txt')
    if not os.path.exists(f): return None
    out, t = {}, None
    for line in open(f, errors='ignore'):
        if line.startswith('*Time'): t = float(line.split('=')[1])
        elif line[:1].isdigit() and t is not None:
            v = line.split(',')
            if len(v) >= 13: out[t] = [float(a) for a in v[1:13]]
    return out


def dyn_residuals(rb, times):
    """rigid-body dynamic residual per logged time -> ({t: (|M_rb| N mm, |F_rb - (0, 0, Fz_ref)| N)}, Fz_ref); Fz_ref = the
    median logged Fz over the window (the follower force; -100 N in the physio protocol)."""
    ts = [t for t in times if rb and t in rb]
    if not ts: return {}, None
    fz = float(np.median([rb[t][8] for t in ts]))
    return {t: (float(np.linalg.norm(rb[t][9:12])), float(np.hypot(rb[t][6], rb[t][7]) + abs(rb[t][8] - fz))) for t in ts}, fz


def target_bracket(cd, sch):
    """rotation control (physio_rot, PI 2026-10-28): per window the two logged states that bracket the target moment and the
    linear interpolation between them (2026-11-02; before: the first state past the target, 4-13 % overshoot, T07).
    States that cannot be trusted are dropped before the search (T02; filter_rows): a step shorter than DT_MIN - the step
    controller takes the remaining time to a must point / step end as one step whatever dtmin is (FECore
    FETimeStepController::CheckMustPoints) and in a slow-dynamic analysis the inertia term of such a micro-step gives a
    spurious reaction moment (p060 LB_left 864 -> -295270 N mm at dt 2e-6) - or a state whose driven rigid body carries a
    dynamic residual (C3pot.txt, > DYN_M x target or > DYN_F x follower; retried steps, contact chatter: NUM-14) - or an
    isolated spike / sign change of the moment.
    The driving moment is the moment the joint of the window applies to C3 (drive.txt, joint i = window i; needs the BIOCAGE
    FEGenericRigidJoint output patch 2026-10-28).
    -> {name: dict(t, reached, M, t_a, M_a, t_b, M_b, frac, coarse, valid_times, invalid=[[t, dt, M, why, ...]], check={...})}
    reached: |M_a| < target <= |M_b|, t = t_a + frac (t_b - t_a), M = the signed target; the first valid state already past
    the target brackets with (t0, 0) (coarse). not reached: t = t_a = t_b = last valid time, M = its moment, frac 0.
    check: n_rows, n_invalid, n_dyn, dt_min, monotonic (|M| never drops by more than 2 % between valid states), rb_res_max /
    rb_fres_max (largest rigid-body moment / force residual among the valid states, None when C3pot.txt is absent), t_last
    (last valid time), complete (t_last reaches t_peak)."""
    out = {}
    if sch.get('control') != 'rotation':
        for w in sch['windows']:
            t = (w['t0'] + w['t1']) / 2
            out[w['name']] = dict(t=t, reached=True, M=None, t_a=t, M_a=None, t_b=t, M_b=None, frac=0.0, coarse=False, valid_times=[], invalid=[],
                                  check=dict(n_rows=0, n_invalid=0, dt_min=None, monotonic=True, t_last=t, complete=True))
        return out
    rows = drive_rows(cd); Mt = sch['target_moment_Nmm']; rb = rb_rows(cd)
    for i, w in enumerate(sch['windows']):
        up = [(tt, d[i + 1][COL[w['dof']]]) for tt, d in rows if (i + 1) in d and w['t0'] + 1e-9 < tt <= w['t_peak'] + 1e-9]
        dyn, fz = dyn_residuals(rb, [t for t, _ in up])
        valid, invalid = filter_rows(up, w['t0'], Mt, dyn, abs(fz) if fz else None)
        mono = all(abs(valid[k][2]) >= 0.98 * abs(valid[k - 1][2]) for k in range(1, len(valid)))
        chk = dict(n_rows=len(up), n_invalid=len(invalid), n_dyn=sum(r[3] == 'dyn' for r in invalid), dt_min=min((v[1] for v in valid), default=None),
                   monotonic=mono, rb_res_max=max((dyn[v[0]][0] for v in valid if v[0] in dyn), default=None) if dyn else None,
                   rb_fres_max=max((dyn[v[0]][1] for v in valid if v[0] in dyn), default=None) if dyn else None,
                   t_last=valid[-1][0] if valid else None, complete=bool(valid) and valid[-1][0] >= w['t_peak'] - 1e-6)
        k = next((j for j, v in enumerate(valid) if abs(v[2]) >= Mt), None)
        if k is None:                                                         # not reached: evaluate at the last valid state
            t, m = (valid[-1][0], valid[-1][2]) if valid else (w['t_peak'], None)
            r = dict(t=t, reached=False, M=m, t_a=t, M_a=m, t_b=t, M_b=m, frac=0.0, coarse=False)
        else:
            tb, mb = valid[k][0], valid[k][2]
            ta, ma = (valid[k - 1][0], valid[k - 1][2]) if k > 0 else (w['t0'], 0.0)
            f = (Mt - abs(ma)) / (abs(mb) - abs(ma)) if abs(mb) > abs(ma) else 1.0
            r = dict(t=ta + f * (tb - ta), reached=True, M=Mt * (1 if mb >= 0 else -1), t_a=ta, M_a=ma, t_b=tb, M_b=mb, frac=f, coarse=k == 0)
        out[w['name']] = dict(r, valid_times=[v[0] for v in valid], invalid=invalid, check=chk)
    return out


def target_times(cd, sch):
    """-> {name: (t, reached, M)} from target_bracket (kept for callers that need only the evaluation time)."""
    return {k: (v['t'], v['reached'], v['M']) for k, v in target_bracket(cd, sch).items()}


def lerp(a, b, f):
    """interpolate two metric dicts (numbers and equal-length lists; other values from a)."""
    o = {}
    for k, va in a.items():
        vb = b.get(k, va)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool): o[k] = va + f * (vb - va)
        elif isinstance(va, list) and isinstance(vb, list) and len(va) == len(vb): o[k] = [x + f * (y - x) for x, y in zip(va, vb)]
        else: o[k] = va
    return o


def state_at(states, t, tol=1e-3):
    """the xplt state logged at time t (states and drive.txt rows are both written per converged step), else None."""
    s = min(states, key=lambda s: abs(s['time'] - t))
    return s if abs(s['time'] - t) <= tol else None


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
    ok &= bracket_selftest()
    print('SELFTEST', 'PASS' if ok else 'FAIL'); return ok


def bracket_selftest():
    """target_bracket on synthetic drive.txt files: (1) linear ramp crossing 1500 between two states -> interpolated time;
    (2) p060 LB_left pattern: ramp to 864 then a 2e-6 micro-step to -295270 -> micro-step dropped, not reached, t_last = the
    864 state; (3) a 3x jump at a regular step -> dropped; (4) first state already past the target -> coarse bracket from t0;
    (5) short ramp -> not reached, complete False; (6) rigid-body dynamic residual (NUM-14): the p062 extension retry state
    (drive 1360 with |M_rb| 184) is dropped and the bracket moves to its neighbours; a force residual of 3 N is reported but
    drops nothing (DYN_F None); without C3pot.txt nothing changes."""
    import tempfile
    sch = dict(control='rotation', target_moment_Nmm=1500, windows=[dict(name='w', dof='Ry', t0=3.5, t_peak=4.0, t1=4.0)])
    def run(times_M, rb=None):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'drive.txt'), 'w') as f:
            for k, (t, m) in enumerate(times_M):
                f.write(f'*Step  = {k + 1}\n*Time  = {t}\n*Data  = RCFx;RCFy;RCFz;RCMx;RCMy;RCMz\n1,0,0,0,0,{m},0\n')
        if rb is not None:                                   # [(t, Fz, My)] -> C3pot.txt rows x;y;z;thx;thy;thz;Fx;Fy;Fz;Mx;My;Mz
            with open(os.path.join(d, 'C3pot.txt'), 'w') as f:
                for k, (t, fz, my) in enumerate(rb):
                    f.write(f'*Step  = {k + 1}\n*Time  = {t}\n*Data  = x;y;z;thx;thy;thz;Fx;Fy;Fz;Mx;My;Mz\n2,0,0,0,0,0,0,0,0,{fz},0,{my},0\n')
        return target_bracket(d, sch)['w']
    ok = True
    # (6) p062 extension (split2): step 9 failed and was retried with dt 0.04545; that state's joint moment is 1360 while the
    # rigid body logs My -184 (the neighbours predict 1535) -> dropped as 'dyn', bracket = (3.9, 3.99182)
    ext = [(3.6, 309.7), (3.7, 681.9), (3.8, 1037.1), (3.9, 1380.6), (3.94545, 1360.1), (3.99182, 1693.2), (4.0, 1721.0)]
    rbn = [(t, -100.0, 0.2) for t, _ in ext]; rbd = [(t, -100.0, -184.1 if t == 3.94545 else 0.2) for t, _ in ext]
    r = run(ext, rbd); f_want = (1500 - 1380.6) / (1693.2 - 1380.6)
    ok &= r['reached'] and r['check']['n_dyn'] == 1 and r['invalid'][0][3] == 'dyn' and r['t_a'] == 3.9 and r['t_b'] == 3.99182 and abs(r['frac'] - f_want) < 1e-9 and r['check']['rb_res_max'] < 1
    print(f"bracket dyn-retry  reached {r['reached']} n_dyn {r['check']['n_dyn']} t_a {r['t_a']} t_b {r['t_b']} frac {r['frac']:.4f} want {f_want:.4f} rb_res_max {r['check']['rb_res_max']}")
    r = run(ext, rbn); ok &= r['check']['n_dyn'] == 0 and r['t_a'] == 3.94545; print(f"bracket dyn-clean  n_dyn {r['check']['n_dyn']} t_a {r['t_a']} (3.94545)")
    r = run(ext); ok &= r['check']['n_invalid'] == 0 and r['t_a'] == 3.94545 and r['check']['rb_res_max'] is None; print(f"bracket no-C3pot   n_invalid {r['check']['n_invalid']} t_a {r['t_a']} (3.94545)")
    r = run(ext, [(t, -97.0 if t == 3.9 else -100.0, 0.2) for t, _ in ext]); ok &= r['check']['n_dyn'] == 0 and abs(r['check']['rb_fres_max'] - 3.0) < 1e-9 and r['t_a'] == 3.94545
    print(f"bracket dyn-force  n_dyn {r['check']['n_dyn']} (0: force residual is reported only) rb_fres_max {r['check']['rb_fres_max']} (3.0)")
    r = run([(3.55, -300), (3.6, -600), (3.65, -900), (3.7, -1200), (3.75, -1500 - 300), (3.8, -2100)])
    e = abs(r['t'] - 3.725); ok &= r['reached'] and e < 1e-9 and r['M'] == -1500 and abs(r['frac'] - 0.5) < 1e-9; print(f"bracket ramp       t {r['t']:.4f} want 3.7250 frac {r['frac']:.2f}")
    r = run([(3.55, -300), (3.6, -600), (3.65, -864), (3.650002, -295270)])
    ok &= (not r['reached']) and r['check']['n_invalid'] == 1 and r['t'] == 3.65 and r['invalid'][0][3] == 'dt'; print(f"bracket micro-step reached {r['reached']} invalid {r['invalid']}")
    r = run([(3.55, 300), (3.6, 600), (3.65, 2100), (3.7, 900), (3.75, 1200), (3.8, 1600)])
    ok &= r['reached'] and r['check']['n_invalid'] == 1 and abs(r['t'] - 3.7875) < 1e-9; print(f"bracket spike      t {r['t']:.4f} want 3.7875 invalid {r['invalid'][0][3]}")
    # p100 LB_right (split2): spike in the 2nd row, then the normal ramp (used to cascade with a ratio test)
    r = run([(3.55, -171), (3.595455, 6798.37), (3.629462, -438.86), (3.663469, -506.6), (3.68861, -629.0), (3.718722, -728.4), (3.752812, -845.3), (3.790084, -965.2), (3.829902, -1100.2), (3.871756, -1245.8), (3.915239, -1395.2), (3.958951, -1545.6), (4.0, -1689.7)])
    ok &= r['reached'] and r['check']['n_invalid'] == 1 and r['invalid'][0][0] == 3.595455 and abs(r['t_b'] - 3.958951) < 1e-9; print(f"bracket p100 spike reached {r['reached']} n_invalid {r['check']['n_invalid']} t_b {r['t_b']}")
    # p027 LB_right (split2): small first step then the regular ramp (ratio test used to drop the whole ramp)
    r = run([(3.55, -151), (3.6, -325.3), (3.65, -488.1), (3.7, -646.4), (3.75, -800.8), (3.8, -953.9), (3.85, -1105.3), (3.9, -1255.4), (3.95, -1402.7), (4.0, -1536.7)])
    ok &= r['reached'] and r['check']['n_invalid'] == 0 and abs(r['t_b'] - 4.0) < 1e-9; print(f"bracket p027 ramp  reached {r['reached']} n_invalid {r['check']['n_invalid']}")
    # p015 extension (split2, ERROR window): ramp to 1310 then -13516, +3250 -> both dropped, not reached
    r = run([(3.8, 900), (3.85, 1100), (3.9, 1310), (3.941328, -13516.4), (3.944295, 3250.0)])
    ok &= (not r['reached']) and r['check']['n_invalid'] == 2 and r['t'] == 3.9; print(f"bracket p015 blow-up reached {r['reached']} invalid {[i[3] for i in r['invalid']]}")
    # extension window: the joint moment starts negative (insertion / follower state) and crosses zero -> nothing dropped
    r = run([(3.55, -210), (3.6, 28.6), (3.65, 202.4), (3.7, 429.4), (3.75, 632.7), (3.8, 829.6), (3.85, 1014.4), (3.9, 1191.8), (3.95, 1367.9), (4.0, 1539.4)])
    ok &= r['reached'] and r['check']['n_invalid'] == 0 and abs(r['t_b'] - 4.0) < 1e-9; print(f"bracket sign-cross reached {r['reached']} n_invalid {r['check']['n_invalid']}")
    # atypically small first row then a smooth ramp (p027 flexion) -> at most the odd row is dropped, never the ramp
    r = run([(3.5889, -100), (3.629917, -1210.3), (3.672776, -1327.8), (3.717063, -1493.7), (3.762309, -1673.2), (3.808505, -1861.5)])
    ok &= r['reached'] and r['check']['n_invalid'] <= 1 and abs(r['t_b'] - 3.762309) < 1e-9; print(f"bracket small-first reached {r['reached']} n_invalid {r['check']['n_invalid']} t_b {r['t_b']}")
    r = run([(3.55, 3000), (3.6, 3100)])
    ok &= r['reached'] and r['coarse'] and abs(r['t'] - 3.525) < 1e-9; print(f"bracket coarse     t {r['t']:.4f} want 3.5250")
    r = run([(3.55, 300), (3.6, 600)])
    ok &= (not r['reached']) and (not r['check']['complete']) and r['t'] == 3.6; print(f"bracket short      reached {r['reached']} complete {r['check']['complete']}")
    l = lerp(dict(a=1.0, v=[0.0, 2.0], s='x', b=True), dict(a=3.0, v=[1.0, 4.0], s='y', b=False), 0.25)
    ok &= l == dict(a=1.5, v=[0.25, 2.5], s='x', b=True); print('lerp', l)
    return ok


if __name__ == '__main__':
    if sys.argv[1] == '--test': sys.exit(0 if selftest() else 1)
    r = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps({k: v for k, v in r.items() if k != 'provenance'}, indent=1))
