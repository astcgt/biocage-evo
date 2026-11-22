"""PI 2026-11-22 pending item 19: 「找出合理、符合醫療法規、學術或醫學規範的精準度，不要亂設，要有可信原因」.
Numerical uncertainty budget of the verdict read-out (posterior translation of the cage relative to the C4 endplate at the evaluation
point of a friction window, mm) and the decision rule it supports.

Framework (references in the output file):
  - FDA 2023 CM&S credibility guidance / ASME V&V 40-2018: calculation verification estimates the numerical error of the quantity of
    interest; acceptability is set relative to the context of use, and the proximity of the prediction to the decision threshold is
    judged together with the uncertainty of the prediction. No fixed number is given -> the number must come from our data and our line.
  - GUM (JCGM 100:2008): standard uncertainties of independent components combine as a root sum square; expanded
    uncertainty U = k u_c with k = 2 (about 95 %).
  - ISO 5725-6: repeatability limit r = 2.8 s_r = 1.96 sqrt(2) s_r: two results of the same model under repeatability conditions differ
    by more than r in about 5 % of the cases.
  - JCGM 106:2012 section 8.3 (read in the OIML G 1-106 reproduction): guarded acceptance - acceptance limit = tolerance limit - w,
    'a common choice is r = 1, in which case w = U'; with w = 2u the probability of accepting a nonconforming item is at most 2.3 %
    (normal PDF). ISO 14253-1 uses this as its default rule.
  - Richardson / Roache: for an error of order p in a parameter refined by the ratio q, the error of the coarse result is
    |difference| * q^p / (q^p - 1). Time step q 10, p 1 -> 1.11 x; contact penalty (error ~ 1 / penalty) doubled -> 2 x.
Components:
  replicate  pooled within-group SD of the posterior read-out over the identical-deck replicate groups (replicate_agreement.json): run
             path, GPU summation order, insertion lineage
  time step  p124 cycle arms from the same checkpoint (window_dt 0.001 vs production stepping), same C3 angle 1-7.8 deg, extension
             loading of cycles 1 and 2: RMS of the difference x 1.11
  penalty    same, penalty x2 vs production: RMS x 2
  solver     newton_confirm.json: full minus quasi-Newton at the evaluation point (10 windows): RMS
  static     NUM-08 static vs slow-dynamic window;  process  NUM-15 process G vs production insertion (extension)
  mesh       NOT measured for this read-out (the cage mesh checks cover tied mu_req and the interface shear) -> the room left inside the
             guard band is reported as the allowance for it
usage: python ops/precision_budget.py  -> results/method/fric/precision_budget.json"""
import os, sys, json, glob, itertools, time, numpy as np
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(E, 'methods')); import e04_dislocation as e4
R = os.path.join(os.path.dirname(E), 'biocage_simulation_test_oct2026/human_study/al_v2/'); F = os.path.join(E, 'results/method/fric/')
LIMIT, PASS_LINE, FAIL_LINE, ROM, K = 0.5, 0.45, 0.55, 0.1286, 2.0

# replicate precision
rep = json.load(open(F + 'replicate_agreement.json')); ss = dof = 0; pairs = []
for g in rep['groups']:
    for wn, w in g['windows'].items():
        v = [x['post'] for x in w['values'].values() if x.get('post') is not None]
        if len(v) < 2 or not w.get('same_eval_point'): continue
        v = np.array(v); ss += float(((v - v.mean()) ** 2).sum()); dof += len(v) - 1; pairs += [abs(a - b) for a, b in itertools.combinations(v, 2)]
s_r = (ss / dof) ** 0.5; r_lim = 2.8 * s_r

# time step, penalty: p124 cycle arms at the same C3 angle, extension loading
def series(d):
    w = [x for x in sorted(glob.glob(R + d + '*/w_flexion')) if os.path.exists(x + '/cage_nodes.txt')][0]
    c3, cn, c4 = (e4.read_log(os.path.join(w, f)) for f in ('C3pot.txt', 'cage_nodes.txt', 'C4_endplate_nodes.txt'))
    return np.array([(t, float(np.linalg.norm(e4.nearest(c3, t)[0][2][3:6])), float(-(np.array(list(cn[t].values())).mean(0) - np.array(list(c4[t].values())).mean(0))[0])) for t in sorted(t for t in cn if t in c4)])
arms = {k: series(v) for k, v in dict(small='pilot_cyc3vdt/p124', prod='pilot_cyc3vr/p124', pen2='pilot_cyc3vpen/p124').items()}
grid = np.radians(np.arange(1.0, 7.81, 0.1)); near = np.radians(np.arange(np.degrees(ROM) - 1.0, np.degrees(ROM) + 1e-6, 0.05))   # the last degree before the intact ROM angle
diff = {'time_step': [], 'penalty': []}; diff_near = {'time_step': [], 'penalty': []}; at_rom = {'time_step': [], 'penalty': []}
for t0, t1 in ((4.5, 5.0), (6.5, 7.0)):
    P = {}
    for k, a in arms.items():
        b = a[(a[:, 0] >= t0 - 1e-6) & (a[:, 0] <= t1 + 1e-6)]
        if len(b) > 5 and b[-1, 0] >= t1 - 0.02: o = np.argsort(b[:, 1]); P[k] = (np.interp(grid, b[o, 1], b[o, 2]), float(np.interp(ROM, b[o, 1], b[o, 2])), np.interp(near, b[o, 1], b[o, 2]))
    for name, k in (('time_step', 'small'), ('penalty', 'pen2')):
        if k in P and 'prod' in P: diff[name] += list(P[k][0] - P['prod'][0]); at_rom[name].append(P[k][1] - P['prod'][1]); diff_near[name] += list(P[k][2] - P['prod'][2])
rms = lambda x: float(np.sqrt(np.mean(np.square(x))))
nc = json.load(open(F + 'newton_confirm.json')); dsol = [p['d_post_mm'] for p in nc['pairs'] if 'd_post_mm' in p]
comp = dict(replicate=dict(u_mm=s_r, basis=f'pooled SD, {len(pairs)} pairs in {dof} degrees of freedom (replicate_agreement.json)', max_pair_mm=max(pairs)),
            time_step=dict(u_mm=1.11 * rms(diff_near['time_step']), rms_diff_last_degree_mm=rms(diff_near['time_step']), rms_diff_1_to_7p8deg_mm=rms(diff['time_step']), max_abs_diff_mm=float(np.max(np.abs(diff['time_step']))),
                           at_intact_rom_mm=at_rom['time_step'], basis='p124, window_dt 0.001 vs production stepping, extension loading of cycles 1-2, RMS over the last degree before the intact ROM angle '
                           '(every near-line verdict read-out is extension at the intact ROM), x 1.11 (Richardson q 10, order 1). Upper estimate: the differences alternate in sign (stick-slip texture), not smooth convergence'),
            penalty=dict(u_mm=2.0 * rms(diff_near['penalty']), rms_diff_last_degree_mm=rms(diff_near['penalty']), rms_diff_1_to_7p8deg_mm=rms(diff['penalty']), max_abs_diff_mm=float(np.max(np.abs(diff['penalty']))),
                         at_intact_rom_mm=at_rom['penalty'], basis='p124, penalty x2 vs production, same angles, x 2 (penalty error ~ 1 / penalty). Upper estimate: the penalty arm has its own stepping, so its difference also carries the stick-slip texture'),
            solver=dict(u_mm=rms(dsol), basis=f'newton_confirm.json, full minus quasi-Newton at the evaluation point, {len(dsol)} windows', max_abs_diff_mm=float(np.max(np.abs(dsol)))),
            static_vs_slow_dynamic=dict(u_mm=0.0005 / 3 ** 0.5, basis='NUM-08 (2026-11-21, p062, mu 0.35): extension at the intact ROM 0.4421 static vs 0.4426 slow dynamic; rectangular, half-width 0.0005'),
            insertion_process=dict(u_mm=0.001 / 3 ** 0.5, basis='NUM-15 (process G vs production, p062 / p094): extension at the intact ROM differs <= 0.001 mm; rectangular, half-width 0.001. '
                                   'Flexion differs 0.02-0.05 mm (usage limit R13); no near-line read-out is a flexion read-out'))
excluded = dict(anchor_drift='NUM-13 (2026-11-18): hold-phase trend <= 0.0022 mm and production vs half step <= 0.0008 mm; the residual is part of the measured time-step term',
                increments_density_20261105='DECISIONS 2026-11-05 18:08: p062 extension at the intact ROM 0.446-0.566 mm across increment counts / density under the FEBio friction law that resets the stick point every increment '
                                            '(physio_fric3). Superseded by the stick-memory law of every current window (PI 2026-11-09 decision 2, NUM-13 pass 2026-11-18); what is left of the effect is the time-step term above',
                mesh='not measured for this read-out; the guard band room left is reported as mesh_allowance',
                model_form='outside the numerical budget: friction coefficient, material law, boundary conditions, validation accuracy, and the uncertainty of the 0.5 mm limit itself (FDA 2023 names them next to calculation verification)')
u_c = float(np.sqrt(sum(c['u_mm'] ** 2 for c in comp.values()))); U = K * u_c; w = LIMIT - PASS_LINE
mesh_allow = float(np.sqrt(max((w / K) ** 2 - u_c ** 2, 0)))

# read-outs near the lines
v = json.load(open(F + 'verdicts.json')); near = []
for p, d in v.items():
    if p.startswith('_') or not isinstance(d, dict): continue
    for wn, x in d.get('windows', {}).items():
        if not isinstance(x, dict) or not x.get('eval_point'): continue
        post = x.get('post_at_rom') if x['eval_point'] == 'ROM' else x.get('post_at_1p5Nm')
        if post is None: continue
        L = min((PASS_LINE, FAIL_LINE), key=lambda L: abs(post - L))
        if abs(post - L) <= U: near.append(dict(design=p, verdict=d.get('verdict'), window=wn, eval_point=x['eval_point'], post_mm=round(post, 4), line=L))
out = dict(generated=time.strftime('%Y-%m-%dT%H:%M'), quantity='posterior translation of the cage relative to the C4 endplate at the evaluation point (mm)', components=comp, excluded=excluded,
           combined_standard_uncertainty_mm=u_c, coverage_factor=K, expanded_uncertainty_U95_mm=U,
           repeatability=dict(s_r_mm=s_r, repeatability_limit_r_mm=r_lim, pairs=len(pairs), pairs_over_r=int(sum(x > r_lim for x in pairs)), expected_fraction_over_r=0.05),
           guard_band=dict(nominal_limit_mm=LIMIT, pass_line_mm=PASS_LINE, guard_band_w_mm=w, U_over_w=U / w, guarded_acceptance_limit_mm=LIMIT - U, pass_line_is_stricter=bool(PASS_LINE <= LIMIT - U),
                           mesh_allowance_standard_uncertainty_mm=mesh_allow, note='w = distance from the PI pass line 0.45 to the PI nominal limit 0.5 mm (PI 2026-11-03 04:30, grey zone PI 2026-11-10); guarded acceptance needs w >= U'),
           near_lines_within_U=sorted(near, key=lambda q: abs(q['post_mm'] - q['line'])), n_designs_near=len({q['design'] for q in near}),
           references=['FDA, Assessing the Credibility of Computational Modeling and Simulation in Medical Device Submissions, final guidance, Nov 2023 (section on post-study adequacy: proximity of predictions to decision or safety thresholds, with uncertainty)',
                       'ASME V&V 40-2018, Assessing Credibility of Computational Modeling through Verification and Validation: Application to Medical Devices',
                       'JCGM 100:2008 (GUM), Evaluation of measurement data - Guide to the expression of uncertainty in measurement',
                       'ISO 5725-6:1994 (confirmed 2022), Accuracy (trueness and precision) of measurement methods and results - Part 6: Use in practice of accuracy values (repeatability limit r = 2.8 s_r)',
                       'JCGM 106:2012, Evaluation of measurement data - The role of measurement uncertainty in conformity assessment; ILAC-G8:09/2019, Guidelines on Decision Rules and Statements of Conformity',
                       'Richardson extrapolation for spatial / temporal convergence (Roache 1998, as summarised by the NASA NPARC Alliance CFD V&V tutorial, https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html)',
                       'Campbell JQ et al., J Biomech 2016, Automated finite element meshing of the lumbar spine: verification and validation with 18 specimen-specific models (mesh doubling changes key outputs < 5 %)',
                       'Nabhan A et al., Eur Spine J 2007;16:423-430 (cervical radiostereometry, 99 % confidence limit of anterior-posterior translation 0.45 mm; ISO 16087:2013 governs RSA)'])
json.dump(out, open(F + 'precision_budget.json', 'w'), indent=1)
print(json.dumps({k: (round(c['u_mm'], 4)) for k, c in comp.items()}), f"u_c {u_c:.4f} U95 {U:.4f} | s_r {s_r:.4f} r {r_lim:.4f} pairs over r {out['repeatability']['pairs_over_r']}/{len(pairs)} | w {w} U/w {U / w:.2f} accept-limit {LIMIT - U:.3f} mesh allowance {mesh_allow:.4f} | near {out['n_designs_near']}")
print('time step: RMS last degree %.4f, 1-7.8 deg %.4f, at ROM %s | penalty: RMS last degree %.4f, 1-7.8 deg %.4f, at ROM %s' % (rms(diff_near['time_step']), rms(diff['time_step']), [round(x, 4) for x in at_rom['time_step']], rms(diff_near['penalty']), rms(diff['penalty']), [round(x, 4) for x in at_rom['penalty']]))
for q in out['near_lines_within_U']: print(q)
