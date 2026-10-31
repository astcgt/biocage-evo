"""Soft-phase degradation sensitivity (2026-10-31): the same designs rebuilt with E_soft x 0.5 / 0.2 / 0.1
(al_v2/physio_degr050, physio_degr020, physio_degr010; split2 protocol). Runs e04 + e05 on every ended window, then tabulates
per design and scale: worst-window mu_req, max one-face slip bound, sustained and peak soft-phase compression, windows reached,
against the baseline (results/method/split/best_by_design_merged.json, comp_by_design_merged.json).
These are sensitivity runs: they are NOT merged into the design verdicts. Writes results/method/degr/compare.json.
usage: python ops/degr_compare.py [workers]
"""
import os, sys, glob, json, subprocess
from concurrent.futures import ThreadPoolExecutor

E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1/human_study/al_v2/'
OUT = os.path.join(E, 'results/method/degr'); os.makedirs(OUT, exist_ok=True)
WIN = ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right')
SETS = {'physio_degr050': 0.5, 'physio_degr020': 0.2, 'physio_degr010': 0.1}
ended = lambda log: os.path.exists(log) and any(k in open(log, errors='ignore').read()[-4000:] for k in ('N O R M A L', 'E R R O R'))
wds = [w for s in SETS for w in sorted(glob.glob(R + s + '/p*/w_*')) if ended(w + '/case.log') and os.path.exists(w + '/case.xplt')]
insertions = {s: {os.path.basename(d)[:4]: ('N' if 'N O R M A L' in open(d + '/case.log', errors='ignore').read()[-4000:] else 'E')
                  for d in glob.glob(R + s + '/p*') if os.path.isdir(d) and ended(d + '/case.log')} for s in SETS}

def one(w):
    s = w.split('/al_v2/')[1].split('/')[0]; tag = f"{s}__{os.path.basename(os.path.dirname(w))}__{os.path.basename(w)[2:]}"
    for m, script in (('e04', 'methods/e04_dislocation.py'), ('e05', 'methods/e05_compression.py')):
        o = os.path.join(OUT, f'{tag}.{m}.json')
        if os.path.exists(o): continue
        r = subprocess.run(['timeout', '2400', sys.executable, os.path.join(E, script), w, o], capture_output=True, text=True)
        if r.returncode: open(o[:-5] + '.err', 'w').write(r.stderr[-3000:])
    return tag

with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3) as ex: list(ex.map(one, wds))
base = json.load(open(os.path.join(E, 'results/method/split/best_by_design_merged.json'))); basec = json.load(open(os.path.join(E, 'results/method/split/comp_by_design_merged.json')))
agg = {}
for f in sorted(glob.glob(os.path.join(OUT, '*.e04.json'))):
    s, dd, wn = os.path.basename(f)[:-9].split('__'); p = dd[:4]; r = json.load(open(f))['windows'].get(wn)
    a = agg.setdefault((p, SETS[s]), dict(design=p, scale=SETS[s], windows={}, insertion=insertions[s].get(p)))
    if isinstance(r, dict): a['windows'][wn] = dict(mu=r['mu_squeeze'], slip=r['one_face_slip_bound_mm'], reached=r['target_reached'], M=r['M_at_target'])
    f5 = f[:-9] + '.e05.json'
    if os.path.exists(f5):
        c = json.load(open(f5)); a['sustained'] = c.get('sustained'); cw = c['windows'].get(wn)
        if cw and cw.get('peak') is not None: a['windows'].setdefault(wn, {})['peak'] = cw['peak']
rows = []
for (p, sc), a in sorted(agg.items()):
    ws = a['windows']; mus = [v['mu'] for v in ws.values() if v.get('reached')]; pk = [v['peak'] for v in ws.values() if 'peak' in v]
    b = base.get(p, {}); bmu = [b[w]['mu_squeeze'] for w in WIN if w in b and b[w]['target_reached']]; bc = basec.get(p, {})
    rows.append(dict(design=p, scale=sc, insertion=a['insertion'], n_reached=sum(1 for v in ws.values() if v.get('reached')), mu_worst=max(mus) if mus else None,
                     slip_max=max((v['slip'] for v in ws.values() if v.get('reached')), default=None), sustained=a.get('sustained'), peak_max=max(pk) if pk else None,
                     base_mu_worst=max(bmu) if bmu else None, base_sustained=bc.get('sustained'), base_peak=max((bc['windows'][w]['peak'] for w in WIN if w in bc.get('windows', {}) and bc['windows'][w].get('peak') is not None), default=None)))
json.dump(rows, open(os.path.join(OUT, 'compare.json'), 'w'), indent=1)
f = lambda v, d=3: '-' if v is None else f'{v:.{d}f}'
print(f"{'design':6s} {'scale':5s} {'ins':3s} {'reach':5s} {'mu_worst':>8s} {'base_mu':>8s} {'slip':>6s} {'sus':>6s} {'base':>6s} {'peak':>6s} {'base':>6s}")
for r in rows: print(f"{r['design']:6s} {r['scale']:<5} {str(r['insertion']):3s} {r['n_reached']:>5d} {f(r['mu_worst']):>8s} {f(r['base_mu_worst']):>8s} {f(r['slip_max']):>6s} {f(r['sustained']):>6s} {f(r['base_sustained']):>6s} {f(r['peak_max']):>6s} {f(r['base_peak']):>6s}")
