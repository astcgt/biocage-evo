"""NUM-16, PI 2026-11-22 pending item 16(b): the mesh check of the interface-shear statistics (ops/num16_metric_check.py, p062 only)
repeated on several designs. Production mesh physio_rot_split2/<p>*/w_flexion against the fine mesh numconv_hz01/<p>*/w_flexion (cage
through-thickness element 0.1 mm), tied, flexion at 1.5 N m; per-face statistics and the 0.5 mm patch average. Tolerance of the label: 5 %.
usage: python ops/num16_multi.py p062 p036 ...  -> results/method/numconv/num16_multi.json"""
import os, sys, json, glob, time
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(E, 'ops/num16_metric_check.py')).read(); g = {'__name__': 'num16_base', '__file__': os.path.join(E, 'ops/num16_metric_check.py')}
exec(compile(src.split("coarse = tractions(")[0], 'num16_metric_check.py', 'exec'), g); tractions, R = g['tractions'], g['R']   # the function only, not the p062 run at the end of that file
def wdir(set_, p):
    c = [d for d in sorted(glob.glob(R + f'{set_}/{p}_gpu*/w_flexion')) + [R + f'{set_}/{p}/w_flexion'] if os.path.exists(d + '/case.xplt')]
    return c[0] if c else None
KEYS = ('max', 'p99', 'p95', 'p90', 'median', 'mean', 'patch_mean_p99', 'patch_mean_max', 'patch_mean_p90'); rows = {}
for p in sys.argv[1:]:
    a, b = wdir('physio_rot_split2', p), wdir('numconv_hz01', p)
    if not a or not b: rows[p] = dict(error=f'window missing: production {a}, fine {b}'); continue
    try:
        co, fi = tractions(a, 'flexion'), tractions(b, 'flexion'); rel = {k: (fi[k] - co[k]) / co[k] for k in KEYS}
        info = json.load(open(os.path.join(os.path.dirname(a), 'case.json'))).get('params', {})
        rows[p] = dict(production=co, fine=fi, fine_minus_production_rel=rel, within_5pct=[k for k in KEYS if abs(rel[k]) <= 0.05], cage_npz=info.get('cage_npz'), both_reached=bool(co['reached'] and fi['reached']))
    except Exception as ex: rows[p] = dict(error=repr(ex)[:200])
ok = {p: r for p, r in rows.items() if 'error' not in r}
summ = {k: dict(max_abs_rel=max(abs(r['fine_minus_production_rel'][k]) for r in ok.values()), n_within_5pct=sum(abs(r['fine_minus_production_rel'][k]) <= 0.05 for r in ok.values())) for k in KEYS} if ok else {}
out = dict(generated=time.strftime('%Y-%m-%dT%H:%M'), designs=list(rows), n_compared=len(ok), summary=summ, rows=rows, tolerance=0.05)
os.makedirs(os.path.join(E, 'results/method/numconv'), exist_ok=True); json.dump(out, open(os.path.join(E, 'results/method/numconv/num16_multi.json'), 'w'), indent=1)
print(json.dumps(dict(n_compared=len(ok), summary={k: (round(v['max_abs_rel'], 4), v['n_within_5pct']) for k, v in summ.items()}, per_design={p: ({k: round(r['fine_minus_production_rel'][k], 4) for k in ('p99', 'patch_mean_p99', 'patch_mean_max')} if 'error' not in r else r) for p, r in rows.items()}), indent=1))
