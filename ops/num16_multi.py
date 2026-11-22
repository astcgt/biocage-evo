"""NUM-16, PI 2026-11-22 pending item 16(b): the mesh check of the interface-shear statistics (ops/num16_metric_check.py, p062 only)
repeated on several designs. Tied, flexion at 1.5 N m (e03 target bracket, interpolated); soft-side shear traction on every material
interface face of the cage (methods/e07_interface_shear.py). Tolerance of the label: 5 %.

2026-11-22 second version. The first version (a) read the HORIZONTAL interfaces only, while the verdict takes the larger of the horizontal
and the vertical class (ops/e07_batch.py), and (b) had no check that the fine cage is the SAME material layout. Both were needed:
  - p113 (radial mix) has vertical interfaces only: no read-out;
  - p052, p060 (radial interleave): h12 with a 0.1 mm through-thickness element also halves the printed layer, so the 'fine' cage had
    twice the horizontal interfaces. Those two rows compared two layouts, not two meshes (kept here, flagged layout_ok False).
Arms (production window physio_rot_split2/<p>/w_flexion against):
  z   numconv_hz01/<p>          through-thickness element 0.2 -> 0.1 mm: refines NORMAL to the horizontal interfaces (primary class: horizontal)
  xy  numconv_hz01/inplane/<p>  in-plane element 0.2 -> 0.1 mm: refines NORMAL to the vertical interfaces (primary class: vertical)
Layout guard (face counts of the two meshes): arm z horizontal x1, vertical x2; arm xy horizontal x4, vertical x2; tolerance 10 %
(mix cages: the 0.2 mm axial steps are re-sampled on a wedge, +2-5 % faces). An arm outside the guard is not counted.
Statistics per class: per-face max / p99 / p90 / mean; patch averages with two patch definitions
  column  faces binned on a 0.5 mm IN-PLANE grid (the definition of num16_metric_check.py; for stacked horizontal interfaces one patch
          pools every interface level of the column, for vertical interfaces it is the full-height strip)
  cell    faces binned in 0.5 mm cubes (one interface level per patch where the levels are >= 0.5 mm apart; a 0.5 mm patch of a vertical wall)
Face position = midpoint of the two element centroids. 'verdict_like' = the larger class value, as the verdict uses it.
usage: python ops/num16_multi.py [p062:z p052:xy ...]  -> results/method/numconv/num16_multi.json"""
import os, sys, json, glob, time, numpy as np, xml.etree.ElementTree as ET
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(os.path.dirname(E), 'biocage_simulation_test_oct2026', 'human_study', 'al_v2') + '/'
sys.path[:0] = [os.path.join(E, 'methods'), os.path.join(E, 'common')]
import xplt, e03_mu_req as e3, e07_interface_shear as e7
FINE = dict(z='numconv_hz01', xy='numconv_hz01/inplane'); EXPECT = dict(z=dict(horizontal=1, vertical=2), xy=dict(horizontal=4, vertical=2)); PRIMARY = dict(z='horizontal', xy='vertical')
DEFAULT = ['p062:z', 'p036:z', 'p146:z', 'p113:z', 'p052:z', 'p060:z', 'p052:xy', 'p060:xy']; PATCH = 0.5; TOL = 0.05; GUARD = 0.10
STATS = ('max', 'p99', 'p90', 'mean', 'column_p99', 'column_max', 'cell_p99', 'cell_max')


def wdir(set_, p):
    c = [d for d in sorted(glob.glob(R + f'{set_}/{p}_gpu*/w_flexion')) + [R + f'{set_}/{p}/w_flexion'] if os.path.exists(d + '/case.xplt') and 'N O R M A L' in open(d + '/case.log', errors='ignore').read()[-3000:]]
    return c[0] if c else None


def read(cd, wn='flexion'):
    faces, loc = e7.interfaces(cd)
    A = [loc[a] for a, b, n, h, ha in faces]; B = [loc[b] for a, b, n, h, ha in faces]; N = np.array([n for a, b, n, h, ha in faces]); H = np.array([h for a, b, n, h, ha in faces], bool); HA = np.array([ha for a, b, n, h, ha in faces], bool)
    root = ET.parse(os.path.join(cd, 'case.feb')).getroot(); X = {int(n.get('id')): np.array([float(v) for v in n.text.split(',')]) for n in root.find('Geometry').find('Nodes')}
    blocks = {i + 1: [[int(v) for v in e.text.split(',')] for e in eb] for i, eb in enumerate(root.find('Geometry').findall('Elements'))}
    cen = lambda L: np.array([np.mean([X[k] for k in blocks[b][i]], axis=0) for b, i in L]); pos = 0.5 * (cen(A) + cen(B))
    states = xplt.read(os.path.join(cd, 'case.xplt'))['states']; k = e3.target_bracket(cd, json.load(open(os.path.join(cd, 'physio_schedule.json'))))[wn]
    def ts_of(st):
        S = st['elem']['stress']; sa = e7.stress_tensor(np.stack([S[b][i] for b, i in A])); sb = e7.stress_tensor(np.stack([S[b][i] for b, i in B]))
        sig = np.where(HA[:, None, None], sb, sa); t = np.einsum('fij,fj->fi', sig, N); tn = np.einsum('fi,fi->f', t, N); return np.linalg.norm(t - tn[:, None] * N, axis=1)
    sa_, sb_ = e3.state_at(states, k['t_a']), e3.state_at(states, k['t_b'])
    ts = ts_of(sa_) + k['frac'] * (ts_of(sb_) - ts_of(sa_)) if (sb_ is not None and sa_ is not None and k['frac'] > 0) else ts_of(sa_ or sb_)
    out = dict(t_eval=k['t'], reached=bool(k['reached']))
    for cls, m in (('horizontal', H), ('vertical', ~H)):
        if not m.any(): out[cls] = dict(n_faces=0); continue
        v, c = ts[m], pos[m]; d = dict(n_faces=int(m.sum()), max=float(v.max()), p99=float(np.percentile(v, 99)), p90=float(np.percentile(v, 90)), mean=float(v.mean()))
        for name, key in (('column', np.floor(c[:, :2] / PATCH).astype(int)), ('cell', np.floor(c / PATCH).astype(int))):
            g = {}
            for i, kk in enumerate(map(tuple, key)): g.setdefault(kk, []).append(v[i])
            pm = np.array([np.mean(x) for x in g.values()]); d.update({f'{name}_p99': float(np.percentile(pm, 99)), f'{name}_max': float(pm.max()), f'n_{name}_patches': len(pm), f'faces_per_{name}_patch': round(len(v) / len(pm), 1)})
        out[cls] = d
    out['verdict_like'] = {s: max(out[c][s] for c in ('horizontal', 'vertical') if out[c]['n_faces']) for s in STATS}
    return out


cache, rows = {}, {}
def get(cd):
    if cd not in cache: cache[cd] = read(cd)
    return cache[cd]
for item in (sys.argv[1:] or DEFAULT):
    p, arm = item.split(':'); a, b = wdir('physio_rot_split2', p), wdir(FINE[arm], p)
    if not a or not b: rows[item] = dict(design=p, arm=arm, error=f'window missing or not ended: production {a}, fine {b}'); continue
    try:
        co, fi = get(a), get(b); r = dict(design=p, arm=arm, primary_class=PRIMARY[arm], cage_npz=json.load(open(os.path.join(os.path.dirname(a), 'case.json'))).get('params', {}).get('cage_npz'),
                                          production_dir=os.path.relpath(a, R), fine_dir=os.path.relpath(b, R), both_reached=bool(co['reached'] and fi['reached']), production=co, fine=fi, rel={}, face_ratio={})
        rok = {}
        for cls in ('horizontal', 'vertical'):
            n0, n1 = co[cls]['n_faces'], fi[cls]['n_faces']
            if not n0: rok[cls] = not n1; continue
            r['face_ratio'][cls] = n1 / n0; rok[cls] = abs(n1 / n0 / EXPECT[arm][cls] - 1) <= GUARD
            if n1: r['rel'][cls] = {s: (fi[cls][s] - co[cls][s]) / co[cls][s] for s in STATS}
        r['rel']['verdict_like'] = {s: (fi['verdict_like'][s] - co['verdict_like'][s]) / co['verdict_like'][s] for s in STATS}
        # the guard is on the PRIMARY class. The other class of a mix cage is the stair-step of the axial 0.2 mm steps on the wedge (p062: 208 of
        # 5576 faces): its face count changes with the mesh by construction, it is reported and not guarded. A cage without the primary class
        # (p113: vertical interfaces only, arm z) is guarded on the class it has and has no primary read-out.
        pc = PRIMARY[arm]; r['primary_absent'] = not co[pc]['n_faces']; ok = all(rok.values()) if r['primary_absent'] else rok[pc]
        r['face_ratio_ok'] = {k: bool(v) for k, v in rok.items()}; r['layout_ok'] = bool(ok)
        if not ok: r['problem'] = 'the fine cage is not the same material layout (face-count guard on the primary class): row not counted'
        rows[item] = r
    except Exception as ex: rows[item] = dict(design=p, arm=arm, error=repr(ex)[:300])
good = {k: r for k, r in rows.items() if r.get('layout_ok') and r.get('both_reached')}
def summ(sel):
    v = [(k, r['rel'][sel(r)]) for k, r in good.items() if sel(r) in r['rel']]
    return {s: dict(max_abs_rel=max(abs(x[s]) for _, x in v), n_within_tol=sum(abs(x[s]) <= TOL for _, x in v), n=len(v), worst=max(v, key=lambda q: abs(q[1][s]))[0]) for s in STATS} if v else {}
out = dict(generated=time.strftime('%Y-%m-%dT%H:%M'), tolerance=TOL, patch_mm=PATCH, n_counted=len(good), counted=list(good), not_counted={k: r.get('problem') or r.get('error') or 'target not reached' for k, r in rows.items() if k not in good},
           summary_primary_class=summ(lambda r: r['primary_class']), summary_verdict_like=summ(lambda r: 'verdict_like'), rows=rows,
           note='primary class = the interface class the arm refines normal to; verdict_like = larger of the two classes (as ops/e07_batch.py takes it)')
os.makedirs(os.path.join(E, 'results/method/numconv'), exist_ok=True); json.dump(out, open(os.path.join(E, 'results/method/numconv/num16_multi.json'), 'w'), indent=1)
f = lambda x: f'{x:+.3f}'
for k, r in rows.items():
    if 'error' in r: print(k, 'ERROR', r['error']); continue
    print(k, 'layout', 'OK' if r['layout_ok'] else 'DIFFERENT', {c: round(v, 2) for c, v in r['face_ratio'].items()}, '|', ' | '.join(
        f"{c}: prod p99 {r['production'][c]['p99']:.3f} col {r['production'][c]['column_p99']:.3f} cell {r['production'][c]['cell_p99']:.3f}; rel p99 {f(x['p99'])} col {f(x['column_p99'])} cell {f(x['cell_p99'])} cellmax {f(x['cell_max'])}" for c, x in r['rel'].items()))
print(json.dumps(dict(n_counted=len(good), primary={s: (round(v['max_abs_rel'], 4), f"{v['n_within_tol']}/{v['n']}", v['worst']) for s, v in out['summary_primary_class'].items()},
                      verdict_like={s: (round(v['max_abs_rel'], 4), f"{v['n_within_tol']}/{v['n']}", v['worst']) for s, v in out['summary_verdict_like'].items()}), indent=1))
