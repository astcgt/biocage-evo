"""OBS-01 batch (2026-11-18): run the two supplementary slip-out quantities (T19, inside e04) and the hard-phase stress read-out
(e06) on every WINNER window of the current verdicts - the tied screening winners (results/method/split/best_by_design_merged.json
'source' dirs) and the real-friction winners (results/method/fric/verdicts.json windows: set + case_dir) - and summarise.
Read-out only: nothing here changes a verdict or a class (PI 2026-11-03 item 7: e06 secondary). Windows whose xplt is gone
(retired to the NAS or deleted) are listed as 'no_xplt'.
Friction windows judged at the intact ROM are read at that state (t19_at / e06.at_time); windows judged at 1.5 N m use e04's
target bracket, which is that state.
usage: python obs01_batch.py [workers]      -> results/method/obs01/<config>__<design>__<window>.{e04,e06}.json + obs01_summary.json"""
import os, sys, json, glob, subprocess, time
from concurrent.futures import ThreadPoolExecutor
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(os.path.dirname(E), 'biocage_simulation_test_oct2026', 'human_study', 'al_v2') + '/'
OUT = os.path.join(E, 'results/method/obs01'); os.makedirs(OUT, exist_ok=True)
jobs = []
tied = json.load(open(os.path.join(E, 'results/method/split/best_by_design_merged.json')))
for p, d in tied.items():
    for wn, r in d.items():
        if isinstance(r, dict) and r.get('source'):
            src = r['source']; cd = R + src if not src.startswith('/') else src
            if not os.path.isdir(cd + '/w_' + wn) and os.path.isdir(cd): pass
            elif os.path.isdir(cd + '/w_' + wn): cd = cd + '/w_' + wn
            jobs.append(('TIED', p, wn, cd, None, None))
fric = json.load(open(os.path.join(E, 'results/method/fric/verdicts.json')))
for p, d in fric.items():
    if not isinstance(d, dict) or 'windows' not in d: continue
    for wn, r in d['windows'].items():
        if r.get('placeholder'): continue
        jobs.append(('FRIC', p, wn, R + f"{r['set']}/{r['case_dir']}/w_{wn}", r.get('eval_point'), r.get('t_rom')))   # 2026-11-18 13:0x: read at the verdict's evaluation point

sys.path.insert(0, os.path.join(E, 'methods')); sys.path.insert(0, os.path.join(E, 'common'))
def rom_time(cd, wn):
    """time at which |C3 rotation| reaches the intact segment's ROM (same rule as fric_compare.at_intact_rom)."""
    import e03_mu_req as e3, e04_dislocation as e4, numpy as np
    INTACT = dict(flexion=0.1009, extension=0.1286, LB_right=0.0713, LB_left=0.0717, AR_left=0.0905, AR_right=0.0907)
    c3 = e4.read_log(os.path.join(cd, 'C3pot.txt')); sch = json.load(open(os.path.join(cd, 'physio_schedule.json'))); w = sch['windows'][0]
    pts = []
    for t in sorted(c3):
        if t < w['t0'] - 1e-6: continue
        pts.append((float(np.linalg.norm(c3[t][2][3:6])), t))
    R0 = INTACT[wn]; k = next((i for i, (th, t) in enumerate(pts) if th >= R0), None)
    if k is None: return None
    a, b = (pts[k - 1], pts[k]) if k > 0 else (pts[k], pts[k]); fr = (R0 - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
    return a[1] + fr * (b[1] - a[1])

def one(job):
    cfg, p, wn, cd, evp, t_rom = job; tag = f'{cfg}__{p}__{wn}'; res = dict(config=cfg, design=p, window=wn, case_dir=os.path.relpath(cd, R), eval_point=evp)
    if not os.path.exists(os.path.join(cd, 'case.xplt')): res['status'] = 'no_xplt'; return res
    if cfg == 'FRIC' and evp in ('ROM', 'rom'):                     # friction windows judged at the intact ROM: read T19 / e06 there, not at e04's drive-end bracket
        import e04_dislocation as e4, e06_hard_stress as e6
        try:
            t = rom_time(cd, wn); res['t_rom'] = t
            if t is None: res['status'] = 'rom_not_reached'; return res
            o4 = os.path.join(OUT, f'{tag}.t19rom.json'); o6 = os.path.join(OUT, f'{tag}.e06rom.json')
            if not os.path.exists(o4): json.dump(e4.t19_at(cd, t), open(o4, 'w'), indent=1)
            if not os.path.exists(o6): json.dump(dict(e6.at_time(cd, t), **{k: v for k, v in e6.main(cd).items() if k in ('limit_MPa', 'sustained', 'hard_phi')}), open(o6, 'w'), indent=1)
            w = json.load(open(o4)); res['e04'] = {k: w[k] for k in w if k.startswith(('t19', 'posterior', 'hard_')) or k == 'cage_translation_tied_mm'}
            j = json.load(open(o6)); res['e06'] = dict(limit_MPa=j['limit_MPa'], sustained_p99=j['sustained']['p99'] if j['sustained'] else None, sustained_max=j['sustained']['max'] if j['sustained'] else None,
                                                      peak_p99=j['p99'], peak_max=j['max'], within_sustained=(j['sustained']['p99'] <= j['limit_MPa']) if j['sustained'] else None, at='ROM')
            res['status'] = 'ok'; return res
        except Exception as ex: res['status'] = 'error'; res['error'] = str(ex)[:200]; return res
    for m, s in (('e04', 'methods/e04_dislocation.py'), ('e06', 'methods/e06_hard_stress.py')):
        o = os.path.join(OUT, f'{tag}.{m}.json')
        if not os.path.exists(o):
            r = subprocess.run(['timeout', '1800', sys.executable, os.path.join(E, s), cd, o], capture_output=True, text=True)
            if r.returncode: res[m] = 'error: ' + r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else 'error'; continue
        j = json.load(open(o))
        if m == 'e04':
            w = j['windows'].get(wn); res['e04'] = ({k: w[k] for k in w if k.startswith(('t19', 'posterior', 'hard_')) or k == 'cage_translation_tied_mm'} if isinstance(w, dict) else w)
        else:
            res['e06'] = dict(limit_MPa=j['limit_MPa'], sustained_p99=j['sustained']['p99'] if j['sustained'] else None, sustained_max=j['sustained']['max'] if j['sustained'] else None,
                              peak_p99=(j['windows'].get(wn) or {}).get('peak_p99'), peak_max=(j['windows'].get(wn) or {}).get('peak_max'), within_sustained=j['within_sustained'])
    res['status'] = 'ok'; return res

t0 = time.time()
with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as ex: rows = list(ex.map(one, jobs))
st = {}
for r in rows: st[r['status']] = st.get(r['status'], 0) + 1
import numpy as np
def col(cfg, f):
    v = [f(r) for r in rows if r['config'] == cfg and r['status'] == 'ok' and isinstance(r.get('e04'), dict) and r['e04'].get('t19_available')]
    v = [x for x in v if x is not None]; return dict(n=len(v), median=float(np.median(v)) if v else None, p90=float(np.percentile(v, 90)) if v else None, max=float(max(v)) if v else None)
summ = dict(generated=time.strftime('%Y-%m-%dT%H:%M'), windows=len(jobs), status=st, wall_s=round(time.time() - t0, 1),
            t19={cfg: dict(hard_fit_minus_mean_mm=col(cfg, lambda r: r['e04'].get('hard_fit_minus_mean_mm')), hard_fit_rotation_z_deg=col(cfg, lambda r: abs(r['e04'].get('hard_fit_rotation_z_deg')) if r['e04'].get('hard_fit_rotation_z_deg') is not None else None),
                           hard_local_max_inplane_mm=col(cfg, lambda r: r['e04'].get('hard_local_max_inplane_mm')), posterior_rim_minus_mean_mm=col(cfg, lambda r: r['e04'].get('posterior_rim_minus_mean_mm')),
                           posterior_most_minus_mean_posterior_mm=col(cfg, lambda r: (r['e04']['posterior_most_node_posterior_mm'] + r['e04']['cage_translation_tied_mm'][0]) if r['e04'].get('posterior_most_node_posterior_mm') is not None else None)) for cfg in ('TIED', 'FRIC')},
            e06={cfg: dict(n=len([r for r in rows if r['config'] == cfg and r['status'] == 'ok' and r.get('e06')]),
                           sustained_p99_median=(lambda v: float(np.median(v)) if v else None)([r['e06']['sustained_p99'] for r in rows if r['config'] == cfg and r['status'] == 'ok' and isinstance(r.get('e06'), dict) and r['e06']['sustained_p99'] is not None]),
                           within_sustained=sum(1 for r in rows if r['config'] == cfg and r['status'] == 'ok' and isinstance(r.get('e06'), dict) and r['e06']['within_sustained'] is True),
                           exceeded_sustained=sum(1 for r in rows if r['config'] == cfg and r['status'] == 'ok' and isinstance(r.get('e06'), dict) and r['e06']['within_sustained'] is False)) for cfg in ('TIED', 'FRIC')},
            rows=rows)
json.dump(summ, open(os.path.join(OUT, 'obs01_summary.json'), 'w'), indent=1)
print(json.dumps({k: v for k, v in summ.items() if k != 'rows'}, indent=1))
