"""Full-Newton confirmation (PI 2026-11-22, pending item 12): designs that PASS at mu 0.3 with the quasi-Newton windows are recomputed
with full Newton (window_max_ups 0) from the SAME checkpoints; the read-outs must not move.

For every (design, window) the two windows (quasi-Newton set, full-Newton set) are read with the same method as the verdict
(methods/e04_dislocation.py: state where the window transmits 1.5 N m; ops/fric_compare.py rule: otherwise the state at the intact ROM)
and compared at the SAME evaluation point. Criterion (PI item 12, same number as the R20 read-out noise): |difference| <= 0.005 mm on
the posterior and on the in-plane translation of the cage relative to the C4 endplate.
usage: python ops/newton_confirm.py   -> results/method/fric/newton_confirm.json (exit 1 when a pair is missing or over the criterion)
"""
import os, sys, json, math, subprocess, time, numpy as np
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(os.path.dirname(E), 'biocage_simulation_test_oct2026/human_study/al_v2/')
OUT = os.path.join(E, 'results/method/fric'); sys.path.insert(0, os.path.join(E, 'methods')); import e03_mu_req as e3, e04_dislocation as e4
PAIRS = {'p105': ('pilot_mu03r', 'pilot_mu03rN'), 'p110': ('pilot_mu03r', 'pilot_mu03rN'), 'p131': ('pilot_mu03r', 'pilot_mu03rN'), 'p038': ('pilot_mu03r', 'pilot_mu03rN'),
         'p052': ('pilot_mu03Gr', 'pilot_mu03GrN')}
INTACT = dict(flexion=0.1009, extension=0.1286); CRIT = 0.005


def e04(set_, p, wn):
    w = R + f'{set_}/{p}/w_{wn}'; o = os.path.join(OUT, f'{set_}__{p}__{wn}.e04.json')      # same cache file as ops/fric_compare.py
    if not os.path.exists(o) or os.path.getmtime(o) < os.path.getmtime(w + '/case.log'):
        r = subprocess.run(['timeout', '1500', sys.executable, os.path.join(E, 'methods/e04_dislocation.py'), w, o], capture_output=True, text=True)
        if r.returncode: return None
    r = json.load(open(o))['windows'].get(wn); return r if isinstance(r, dict) else None


def at_rom(set_, p, wn):                                                                     # same rule as fric_compare.at_intact_rom
    cd = R + f'{set_}/{p}/w_{wn}'; sch = json.load(open(os.path.join(cd, 'physio_schedule.json')))
    br = e3.target_bracket(cd, sch)[wn]; c3 = e4.read_log(os.path.join(cd, 'C3pot.txt')); cn = e4.read_log(os.path.join(cd, 'cage_nodes.txt')); c4 = e4.read_log(os.path.join(cd, 'C4_endplate_nodes.txt'))
    pts = []
    for t in br['valid_times']:
        th = float(np.linalg.norm(e4.nearest(c3, t)[0][2][3:6])); u = np.array(list(e4.nearest(cn, t)[0].values())).mean(0) - np.array(list(e4.nearest(c4, t)[0].values())).mean(0)
        pts.append((th, float(np.hypot(u[0], u[1])), float(-u[0])))
    R0 = INTACT[wn]; k = next((i for i, q in enumerate(pts) if q[0] >= R0), None)
    if k is None: return None
    a, b = (pts[k - 1], pts[k]) if k > 0 else (pts[k], pts[k]); fr = (R0 - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
    return dict(u_h=a[1] + fr * (b[1] - a[1]), post=a[2] + fr * (b[2] - a[2]), rot_max_deg=float(np.degrees(pts[-1][0])))


def ended(set_, p, wn):
    lg = R + f'{set_}/{p}/w_{wn}/case.log'
    if not os.path.exists(lg): return None
    t = open(lg, errors='ignore').read()[-3000:]; return 'N O R M A L' in t


rows = []
for p, (qn, fn) in PAIRS.items():
    for wn in ('flexion', 'extension'):
        r = dict(design=p, window=wn, quasi_newton_set=qn, full_newton_set=fn, normal_end=dict(quasi_newton=ended(qn, p, wn), full_newton=ended(fn, p, wn)))
        try:
            a, b = e04(qn, p, wn), e04(fn, p, wn); ra, rb = at_rom(qn, p, wn), at_rom(fn, p, wn)
            if a and b and a['target_reached'] and b['target_reached']:
                ua, ub = a['cage_translation_tied_mm'], b['cage_translation_tied_mm']
                r['at_1p5Nm'] = dict(post=[-ua[0], -ub[0]], u_h=[math.hypot(ua[0], ua[1]), math.hypot(ub[0], ub[1])])
            elif a and b: r['at_1p5Nm'] = dict(reached=[bool(a['target_reached']), bool(b['target_reached'])], M_max=[a.get('M_at_target'), b.get('M_at_target')])
            if ra and rb: r['at_intact_rom'] = dict(post=[ra['post'], rb['post']], u_h=[ra['u_h'], rb['u_h']])
            else: r['at_intact_rom'] = dict(reached=[ra is not None, rb is not None])
            # evaluation point of the verdict: 1.5 N m when the window transmits it, otherwise the intact ROM
            ev = 'at_1p5Nm' if 'post' in r.get('at_1p5Nm', {}) else 'at_intact_rom' if 'post' in r.get('at_intact_rom', {}) else None
            r['evaluation_point'] = ev
            for k in ('at_1p5Nm', 'at_intact_rom'):
                if 'post' in r.get(k, {}): r[k]['d_post'] = r[k]['post'][1] - r[k]['post'][0]; r[k]['d_u_h'] = r[k]['u_h'][1] - r[k]['u_h'][0]
            if ev: r['d_post_mm'] = r[ev]['d_post']; r['d_u_h_mm'] = r[ev]['d_u_h']; r['within'] = bool(abs(r['d_post_mm']) <= CRIT and abs(r['d_u_h_mm']) <= CRIT)
            else: r['problem'] = 'no common evaluation point'
        except Exception as ex: r['problem'] = 'error: ' + repr(ex)[:200]
        rows.append(r)
ok = [r for r in rows if r.get('within')]; worst = max((max(abs(r['d_post_mm']), abs(r['d_u_h_mm'])) for r in rows if 'd_post_mm' in r), default=None)
allpts = [abs(r[k][d]) for r in rows for k in ('at_1p5Nm', 'at_intact_rom') if 'd_post' in r.get(k, {}) for d in ('d_post', 'd_u_h')]
res = dict(time=time.strftime('%Y-%m-%dT%H:%M'), criterion_mm=CRIT, n_pairs=len(rows), n_within=len(ok), worst_abs_diff_mm=worst,
           worst_abs_diff_any_point_mm=max(allpts) if allpts else None, n_point_comparisons=len(allpts),
           note='same checkpoint, same deck, only restart Control max_ups 10 (quasi-Newton, BFGS) -> 0 (full Newton); differences are full Newton minus quasi-Newton', pairs=rows)
json.dump(res, open(os.path.join(OUT, 'newton_confirm.json'), 'w'), indent=1)
for r in rows:
    ev = r.get('evaluation_point'); print(r['design'], r['window'], ev, *(f"{k} d_post {r[k]['d_post']:+.4f} d_u_h {r[k]['d_u_h']:+.4f} post {r[k]['post'][0]:.4f}/{r[k]['post'][1]:.4f}" for k in ('at_1p5Nm', 'at_intact_rom') if 'd_post' in r.get(k, {})), r.get('problem', ''), 'OK' if r.get('within') else 'OVER')
print(f"{len(ok)} / {len(rows)} pairs within {CRIT} mm; worst at the evaluation point {worst}; worst over all compared points {res['worst_abs_diff_any_point_mm']}")
sys.exit(0 if len(ok) == len(rows) else 1)
