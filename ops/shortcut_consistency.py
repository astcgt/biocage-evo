"""PHY-05 shortcut consistency (PI 2026-11-10 accepted rule): the tied screening's mu_req_max must rank the designs like the gold
standard (real-friction posterior translation in extension at the evaluation point): Spearman >= 0.9 and the linear mapping
residual <= 0.05 mm; designs with mu_req_max within 0.140 +- 0.005 are the grey band that must have a friction run.
Recomputed on the CURRENT verdicts (all designs with a friction verdict), replacing the 2026-11-09 one-off (43 designs, pre route E).
usage: python shortcut_consistency.py -> results/method/fric/shortcut_consistency.json"""
import os, json, csv, time, numpy as np
from scipy import stats
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fld = {r['design']: r for r in csv.DictReader(open(os.path.join(E, 'results/method/mu_req_field.csv')))}
v = json.load(open(os.path.join(E, 'results/method/fric/verdicts.json')))
rows = []
for p, d in v.items():
    if not isinstance(d, dict) or 'windows' not in d: continue
    f = fld.get(p, {}); mu = float(f['mu_req_max']) if f.get('mu_req_max') not in (None, '') else None
    ext, flx = d['windows'].get('extension', {}), d['windows'].get('flexion', {})
    pe = ext.get('post_at_1p5Nm') if ext.get('eval_point') == '1.5Nm' else ext.get('post_at_rom')      # value at the window's own evaluation point (PI 2026-11-05 item 1)
    uf = flx.get('u_h_at_1p5Nm') if flx.get('eval_point') == '1.5Nm' else flx.get('u_h_at_rom')
    rows.append(dict(design=p, verdict=d['verdict'], own_verdict=d.get('own_verdict'), mu_req_max=mu, tied_class=f.get('verdict_class'),
                     ext_posterior_mm=pe, ext_eval=ext.get('eval_point'), ext_usable=ext.get('usable'), flex_u_h_mm=uf, flex_eval=flx.get('eval_point'), flex_usable=flx.get('usable')))
E_ = [(r['mu_req_max'], r['ext_posterior_mm']) for r in rows if r['mu_req_max'] is not None and r['ext_posterior_mm'] is not None and r['ext_usable']]
F_ = [(r['mu_req_max'], r['flex_u_h_mm']) for r in rows if r['mu_req_max'] is not None and r['flex_u_h_mm'] is not None and r['flex_usable']]
x, y = np.array(E_).T; sp_e = stats.spearmanr(x, y); a, b = np.polyfit(x, y, 1); res = y - (a * x + b)
xf, yf = np.array(F_).T; sp_f = stats.spearmanr(xf, yf)
mu_at_05 = (0.5 - b) / a; mu_at_055 = (0.55 - b) / a
grey = [r['design'] for r in rows if r['mu_req_max'] is not None and abs(r['mu_req_max'] - 0.140) <= 0.005]
# agreement table: tied rank (mu_req_max <= mu_at_05 => 'tied says inside') vs gold verdict
tab = {}
for r in rows:
    if r['mu_req_max'] is None: continue
    k = ('tied<=mu(0.5mm)' if r['mu_req_max'] <= mu_at_05 else 'tied>mu(0.5mm)', r['verdict']); tab[str(k)] = tab.get(str(k), 0) + 1
out = dict(generated=time.strftime('%Y-%m-%dT%H:%M'), n_designs_with_friction_verdict=len(rows), n_ext=len(E_), spearman_ext_posterior=float(sp_e.correlation), spearman_ext_p=float(sp_e.pvalue),
           linear_fit_ext=dict(slope=float(a), intercept=float(b), rms_residual_mm=float(np.sqrt((res ** 2).mean())), max_abs_residual_mm=float(np.abs(res).max()), p90_abs_residual_mm=float(np.percentile(np.abs(res), 90))),
           mu_req_at_0p5mm=float(mu_at_05), mu_req_at_0p55mm=float(mu_at_055), n_flex=len(F_), spearman_flex_u_h=float(sp_f.correlation),
           grey_band_0p140_pm_0p005=grey, grey_band_without_friction_run=[g for g in grey if g not in v], agreement_table=tab,
           rule='PI 2026-11-10: Spearman >= 0.9 and linear residual <= 0.05 mm (RMS reading; max also reported); grey band mu_req 0.140 +- 0.005 must have a friction run', rows=rows)
json.dump(out, open(os.path.join(E, 'results/method/fric/shortcut_consistency.json'), 'w'), indent=1)
print(json.dumps({k: v_ for k, v_ in out.items() if k != 'rows'}, indent=1))
