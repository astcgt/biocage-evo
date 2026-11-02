"""Numerical-convergence and friction second-pass comparison for p062 (2026-11-02; platform checks NUM-01 / NUM-03 / NUM-05 and
PHY-05 of biocage_simulation_test_oct2026/human_study/platform_capabilities.json).

Runs e04 / e05 (interpolated evaluation, e03.target_bracket) on every ended window of the comparison runs and tabulates
mu_squeeze, one-face slip bound, N_total and the compression peak against the baseline split2 result of the same design
(results/method/split/<design>__<window>.e04/.e05.json, i.e. the current production evaluation).  Thresholds (提案, PI to
confirm): mesh (numconv_hz01) and penalty (numconv_pen05 / pen20) <= 5 % on mu_squeeze and slip; time step (numconv_dt)
<= 2 %; sustained compression <= 1 percentage point.  A relative mu change only counts when the absolute change exceeds
MU_ABS (p062 extension has mu ~0.014: +20 % there is 0.003, far below any friction coefficient that matters for a verdict).
physio_fric2 is listed for information (different physics).
usage: python ops/numconv_compare.py [design=p062]      -> results/method/numconv/compare.json + printed table
"""
import os, sys, glob, json, subprocess
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026/human_study/al_v2/'
OUT = os.path.join(E, 'results/method/numconv'); os.makedirs(OUT, exist_ok=True)
MU_ABS = 0.005                                   # 提案 (PI to confirm)
WIN = ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right')
SETS = {'numconv_dt': ('NUM-03 time step x0.5', 0.02), 'numconv_pen05': ('NUM-05 penalty x0.5', 0.05), 'numconv_pen20': ('NUM-05 penalty x2', 0.05),
        'numconv_hz01': ('NUM-01 cage HZ 0.1 mm (penalty 5)', 0.05), 'physio_fric2': ('PHY-05 real friction, retargeted', None)}
ended = lambda log: os.path.exists(log) and any(k in open(log, errors='ignore').read()[-4000:] for k in ('N O R M A L', 'E R R O R'))
design = sys.argv[1] if len(sys.argv) > 1 else 'p062'


def evaluate(wd, tag):
    out = {}
    for m, s in (('e04', 'methods/e04_dislocation.py'), ('e05', 'methods/e05_compression.py')):
        o = os.path.join(OUT, f'{tag}.{m}.json')
        if not os.path.exists(o):
            r = subprocess.run(['timeout', '2400', sys.executable, os.path.join(E, s), wd, o], capture_output=True, text=True)
            if r.returncode: open(o[:-5] + '.err', 'w').write(r.stderr[-3000:]); continue
        out[m] = json.load(open(o))
    return out


base = {}
for w in WIN:
    f4, f5 = (os.path.join(E, f'results/method/split/{design}__{w}.{m}.json') for m in ('e04', 'e05'))
    if os.path.exists(f4) and os.path.exists(f5):
        base[w] = dict(e04=json.load(open(f4))['windows'][w], e05=json.load(open(f5)))
rows = []
for s, (label, tol) in SETS.items():
    runs = [d for d in sorted(glob.glob(f'{R}{s}/{design}_gpu*') + [f'{R}{s}/{design}']) if ended(os.path.join(d, 'case.log'))]
    if not runs: rows.append(dict(set=s, label=label, status='not run')); continue
    rd = runs[0]; rec = dict(set=s, label=label, run=os.path.relpath(rd, R), windows={}, tol=tol)
    for w in WIN:
        wd = os.path.join(rd, 'w_' + w)
        if not ended(os.path.join(wd, 'case.log')): rec['windows'][w] = 'not ended'; continue
        r = evaluate(wd, f'{s}__{design}__{w}'); e4 = r.get('e04', {}).get('windows', {}).get(w); e5 = r.get('e05')
        if not isinstance(e4, dict) or e5 is None: rec['windows'][w] = 'missing'; continue
        b = base.get(w); cmp = dict(reached=e4['target_reached'], mu=e4['mu_squeeze'], slip=e4['one_face_slip_bound_mm'], N=e4['N_total'],
                                    peak=e5['windows'][w]['peak'], sustained=e5['sustained'], window_check=e4.get('window_check'))
        if b and e4['target_reached'] and b['e04']['target_reached']:
            cmp['d_mu'] = e4['mu_squeeze'] / b['e04']['mu_squeeze'] - 1 if b['e04']['mu_squeeze'] else None
            cmp['d_slip'] = e4['one_face_slip_bound_mm'] / b['e04']['one_face_slip_bound_mm'] - 1 if b['e04']['one_face_slip_bound_mm'] else None
            cmp['d_sustained_pp'] = (e5['sustained'] - b['e05']['sustained']) * 100 if e5['sustained'] is not None and b['e05']['sustained'] is not None else None
            cmp['d_mu_abs'] = e4['mu_squeeze'] - b['e04']['mu_squeeze']
            if tol is not None:
                cmp['within_tol'] = ((cmp['d_slip'] is None or abs(cmp['d_slip']) <= tol) and (cmp['d_mu'] is None or abs(cmp['d_mu']) <= tol or abs(cmp['d_mu_abs']) <= MU_ABS)
                                     and (cmp['d_sustained_pp'] is None or abs(cmp['d_sustained_pp']) <= 1.0))
        rec['windows'][w] = cmp
    ok = [c.get('within_tol') for c in rec['windows'].values() if isinstance(c, dict) and 'within_tol' in c]
    rec['verdict'] = ('pass' if all(ok) else 'fail') if ok and len(ok) == 6 else 'incomplete'
    rows.append(rec)
json.dump(dict(design=design, baseline=base, runs=rows), open(os.path.join(OUT, 'compare.json'), 'w'), indent=1)
print(f'{design}: baseline windows {len(base)}/6 (split2, interpolated)')
for r in rows:
    print(f"\n{r['set']:14s} {r['label']}  -> {r.get('status') or r.get('verdict')}")
    for w, c in r.get('windows', {}).items():
        if isinstance(c, dict):
            print(f"  {w:10s} reached {str(c['reached']):5s} mu {c['mu']:.4f} slip {c['slip']:.4f} mm peak {c['peak'] if c['peak'] is None else round(c['peak'], 4)}"
                  + (f"  d_mu {c['d_mu']:+.1%} ({c['d_mu_abs']:+.4f}) d_slip {c['d_slip']:+.1%} d_sus {c['d_sustained_pp']:+.2f} pp" if c.get('d_mu') is not None else '')
                  + (f"  {'OK' if c.get('within_tol') else 'OUT'}" if 'within_tol' in c else ''))
        else: print(f'  {w:10s} {c}')
