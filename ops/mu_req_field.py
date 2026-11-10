"""mu_req field (PI 2026-11-09): one flat table design -> design hyperparameters -> mu_req per window, as the training set for an ML
evolution agent. mu_req = the smallest friction coefficient at which the cage cannot slip out as a whole (tied screening, e03 mu_squeeze,
results/method/split/best_by_design_merged.json; PI 2026-11-07 decision 1: this IS the slip-out verdict, the real-friction run is a check).
Conventions (PI 2026-11-09): a requirement clearly beyond any achievable coefficient is kept as a point labelled over_max (mu_req > MU_MAX)
instead of being dropped, so the field has no holes; a window that never reached its evaluation moment gives a LOWER BOUND (lower_bound
flag); designs whose windows could not be computed carry mu_req null + the computability flag. Hyperparameters = every params key whose
value differs between designs (bookkeeping keys excluded); cage family / thickness parsed from the mesh name.
usage: python ops/mu_req_field.py   -> results/method/mu_req_field.json + .csv"""
import os, re, json, csv, glob, collections
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(os.path.dirname(E), 'biocage_simulation_test_oct2026/human_study/al_v2')
MU_MAX = 1.0        # PLACEHOLDER (PI to set): above this no surface treatment is credible -> the point is labelled over_max, value kept
GREY_MU, GREY_MU_TOL = 0.140, 0.005   # PI 2026-11-10 (shortcut tolerance accepted): the 0.5 mm posterior limit maps to mu_req 0.140 (mu_req_vs_fric5.json); designs within +-0.005 are grey-band and get a friction run
MU_REAL = 0.35      # the coefficient the real-friction check runs with (physio_fric3 / fric5 settings)
SKIP = {'fsu', 'fsu_info', 'frame', 'cage_npz', 'test', 'physio_windows', 'restart_source', 'restart_env', 'window_min_residual', 'physio_split', 'physio_dynamic', 'physio_rot_rad', 'nonsym', 'contact_type'}
best = json.load(open(os.path.join(E, 'results/method/split/best_by_design_merged.json')))
cls = json.load(open(os.path.join(E, 'results/method/split/verdict_classes_merged.json')))['classes']; cls_of = {p: c for c, ps in cls.items() for p in ps}
fv = os.path.join(E, 'results/method/fric/verdicts.json'); fric = {k: v for k, v in (json.load(open(fv)) if os.path.exists(fv) else {}).items() if not k.startswith('_')}
comp = json.load(open(os.path.join(E, 'results/method/split/comp_by_design_merged.json')))
designs = sorted(set(best) | set(cls_of) | set(comp))   # QA 2026-11-09 不符 #4: the field must have a row for EVERY design of the merged verdict (149), not only the 94 with a tied-screening row
rows = []; allprm = {}
for p in designs:
    wins = best.get(p, {})
    src = next((r['source'] for r in wins.values() if isinstance(r, dict) and r.get('source')), None) or comp.get(p, {}).get('source')
    prm = {}
    if src:
        pj = os.path.join(R, src.split('/')[0], src.split('/')[1][:4] + '_params.json')
        if os.path.exists(pj): prm = json.load(open(pj))
    allprm[p] = prm
    m = re.search(r'cage_([A-Z])_(\w+?)_d([\d.]+)\.npz', os.path.basename(prm.get('cage_npz', '')))
    row = dict(design=p, family=m.group(2) if m else None, d_mm=float(m.group(3)) if m else None, mesh=os.path.basename(prm.get('cage_npz', '')), source=src, verdict_class=cls_of.get(p))
    mus = []
    for w, r in wins.items():
        if not isinstance(r, dict): row[f'mu_req_{w}'] = None; row[f'reached_{w}'] = None; continue
        mu = r.get('mu_squeeze'); row[f'mu_req_{w}'] = None if mu is None else round(mu, 4); row[f'reached_{w}'] = bool(r.get('target_reached'))
        if mu is not None: mus.append(mu)
    row['mu_req_max'] = round(max(mus), 4) if mus else None
    row['governing_window'] = max((w for w in wins if isinstance(wins[w], dict) and wins[w].get('mu_squeeze') is not None), key=lambda w: wins[w]['mu_squeeze']) if mus else None
    row['over_max'] = bool(mus) and max(mus) > MU_MAX
    row['lower_bound'] = any(isinstance(r, dict) and not r.get('target_reached') for r in wins.values())
    row['computable'] = bool(mus)
    row['no_mu_req_reason'] = None if mus else (cls_of.get(p) or 'no tied-screening row')   # e.g. DESIGN/compression-sustained: the compression gate failed before the slip screen
    row['ratio_to_mu_real'] = round(max(mus) / MU_REAL, 3) if mus else None
    f = fric.get(p); row['friction_check'] = f['verdict'] if f else None
    row['insertion_process'] = (f or {}).get('insertion_process')            # provenance (PI 2026-11-10 option a)
    row['grey_band'] = row['mu_req_max'] is not None and abs(row['mu_req_max'] - GREY_MU) <= GREY_MU_TOL   # shortcut tolerance (PI 2026-11-10): within 0.140 +- 0.005 -> friction run required
    row['soft_face_locking'] = bool((f or {}).get('soft_face_locking'))        # PI 2026-11-10 item 2: physio windows fold at the first increments -> outside the design envelope
    row['friction_fallback'] = any(bool((x or {}).get('fallback')) for x in ((f or {}).get('windows') or {}).values())   # PI 2026-11-10 item 1: production-law read-out + margin
    rows.append(row)
keys = sorted({k for prm in allprm.values() for k in prm if k not in SKIP})
hyper = [k for k in keys if len({json.dumps(prm.get(k), sort_keys=True) for prm in allprm.values() if prm}) > 1]
for row in rows:
    for k in hyper: row['hp_' + k] = allprm[row['design']].get(k)
meta = dict(generated=__import__('time').strftime('%Y-%m-%d %H:%M'), n_designs=len(rows), mu_max=MU_MAX, mu_real=MU_REAL, hyperparameters=hyper,
            constant_params={k: allprm[rows[0]['design']].get(k) for k in keys if k not in hyper},
            rule='mu_req per window = tied-screening mu_squeeze (e03) at the evaluation moment; mu_req_max over the six windows governs; over_max: mu_req_max > mu_max (value kept, point labelled); lower_bound: a window did not reach its evaluation moment; computable: at least one window gave a value; friction_check: real-friction run verdict (fric_compare, check role)',
            counts=dict(over_max=sum(r['over_max'] for r in rows), lower_bound=sum(r['lower_bound'] for r in rows), not_computable=sum(not r['computable'] for r in rows), with_friction_check=sum(1 for r in rows if r['friction_check'])))
out = os.path.join(E, 'results/method/mu_req_field'); json.dump(dict(_meta=meta, rows=rows), open(out + '.json', 'w'), indent=1)
cols = list(dict.fromkeys(k for r in rows for k in r))   # union, first-seen order (designs without a tied row lack the per-window keys)
with open(out + '.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); [w.writerow(r) for r in rows]
print(json.dumps(meta, indent=1, ensure_ascii=False)[:1500])
byfam = collections.defaultdict(list)
for r in rows:
    if r['mu_req_max'] is not None: byfam[(r['family'], r['d_mm'])].append(r['mu_req_max'])
for k in sorted(byfam, key=lambda k: (str(k[0]), k[1] or 0)): print(k, 'n', len(byfam[k]), 'mu_req_max median', round(sorted(byfam[k])[len(byfam[k]) // 2], 3), 'range', round(min(byfam[k]), 3), round(max(byfam[k]), 3))
print('saved', out + '.json/.csv')
