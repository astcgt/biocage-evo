"""Surrogate validation gate (ROUND2_ARCHITECTURE.md A1-A4 rev 2; PI 2026-11-18: nominal coverage 90 %, grouped by design).

Read-only on the verdict chain: reads results/method/mu_req_field.csv and results/method/fric/verdicts.json, writes only
results/surrogate/. Surrogate numbers never enter verdicts or labels (h37 R21).

Model specification (fixed BEFORE looking at any result; every variant tried is listed in the output file):
  Gaussian process, kernel Constant x Matern-5/2 (one length scale per input) + White noise, normalize_y, inputs standardised
  inside each fold, 2 optimiser restarts, seed 0. 90 % interval = mean +- 1.645 sd (log targets: in log space, then exp).
  Input sets: G = genes (log E_hard, log E_soft, d, theta) + family one-hot; D = genes + geometric descriptors (no family
  label); T (friction targets only) = G + the tied-screening mu_req of the same window (second-stage input, C6 b);
  DT = D + the same tied input (POST-HOC variant, added after the first run to test C6 b under leave-one-family-out).
  Friction targets also get procG (1 = process-G insertion sets), a configuration choice known before the run.
Targets (the quantities fric_compare judges at each window's evaluation point, usable windows only): post_ext = SIGNED
  posterior translation in extension at the intact ROM (limits 0.45 / 0.55 mm; all 72 values are posterior); uh_flex =
  any-direction translation u_h in flexion at 1.5 N m (limit 1 mm; in flexion the cage moves ANTERIORLY - all 70 signed
  posterior values are negative - so the posterior limit never acts there). Correction 2026-11-18: the first run used
  |posterior| for both windows and called the flexion one 'posterior translation'; that label was wrong (a target
  definition fix, not model tuning). y2 = mu_req_max (log; lower-bound rows excluded and counted);
  y3 = shear_req_p99_MPa (log); y5 = not in a compression class (verdict class without 'compression'; it still counts radial-mix-excluded and not-computable designs as 1; classifier, grouped Brier
  score against the base rate); y4 not-computable is only counted (too few positives to validate).
Validation: leave-one-GROUP-out; a group = rows sharing genes + family, merged with rows sharing a replicate list or a
  launched deck hash. Leave-one-FAMILY-out for input set D (proxy for a new geometry region). Baseline = family mean of
  the training fold (global mean for leave-one-family-out). Steering rule: empirical coverage 0.80-0.95 AND skill >= 0.2
  AND median interval width < 5-95 % spread of the training outputs. Pre-declared fallback: cross-conformal rescaling of
  the interval (scores |residual| / sd, quantile taken from the OTHER groups only).

Changes after the layer-B audit QA_AUDIT_2026-11-18 (D-20261118-27 / -35 / -36), run 3:
  - the 12 designs whose mu_req_field row has no genes (no source run) take genes and mesh from al_v2/cases/pNNN_*_params.json;
    all 12 are design-B (planar) cages, so the family label now carries the design letter ('B_radial_mix' ...) and G has it as one-hot.
  - friction rows that are inherited copies of another design's run (same set + case_dir) are dropped and counted.
  - conformal quantile = conservative rank (numpy method 'higher'), not linear interpolation.
  - coverage is also reported per GROUP (mean of per-group coverage) and per family at group level with its 2 SE; a family
    is flagged under_covered when its group-level conformal coverage is below 0.90 - 2 SE.
  - steering rule made explicit: pooled conformal coverage is near 0.90 by construction, so the tests that carry weight are
    skill >= 0.2, width < training spread and the per-family flag. Leave-one-family-out cells carry NO steer flag (decision:
    an unseen family is never promoted or rejected by the surrogate).
usage: python ops/surrogate_fit.py [YYYY-MM-DD]
"""
import os, sys, csv, json, ast, glob, re, time, warnings
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor, GaussianProcessClassifier
from sklearn.gaussian_process.kernels import ConstantKernel as C, Matern, WhiteKernel
from sklearn.preprocessing import StandardScaler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from descriptors import descriptors, NAMES as DNAMES
warnings.filterwarnings('ignore')

EVO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAT = os.path.dirname(os.path.dirname(json.load(open(os.path.join(EVO, 'config.json')))['febio_src']))
AL = os.path.join(PLAT, 'human_study', 'al_v2'); MESH = os.path.join(PLAT, 'human_study', 'al', 'meshes')
NOMINAL, Z = 0.90, 1.6449
GENES = ['hp_E_hard', 'hp_E_soft', 'hp_d', 'hp_theta']
PROC_G = ('physio_relG', 'physio_relGr', 'physio_relG_pl')


def load():
    rows = [r for r in csv.DictReader(open(os.path.join(EVO, 'results/method/mu_req_field.csv')))]
    excl, filled = [], []
    for r in rows:
        if not r['family'] or not r['hp_E_hard']:      # no source run in mu_req_field: genes and mesh from the case params
            fs = sorted(glob.glob(os.path.join(AL, 'cases', r['design'] + '_*_params.json')))
            if not fs: excl.append(r['design']); continue
            prm = json.load(open(fs[0])); r['mesh'] = os.path.basename(prm['cage_npz'])
            r.update(hp_E_hard=str(prm['E_hard']), hp_E_soft=str(prm['E_soft']), hp_d=str(prm['d']), hp_theta=str(prm['theta']))
            r['family'] = re.match(r'cage_[AB]_(.+)_d[0-9.]+npz', r['mesh']).group(1); filled.append(r['design'])
        if r['mesh'].startswith('cage_B_'): r['family'] = 'B_' + r['family']
    rows = [r for r in rows if r['design'] not in excl]; excl = dict(excluded=excl, genes_from_params=filled)
    verd = {k: v for k, v in json.load(open(os.path.join(EVO, 'results/method/fric/verdicts.json'))).items() if k != '_meta'}
    dcache = {}
    for r in rows:
        if r['mesh'] not in dcache: dcache[r['mesh']] = descriptors(os.path.join(MESH, r['mesh']))
        r['_desc'] = dcache[r['mesh']]
    return rows, verd, excl


def sha(set_, case_dir):
    f = os.path.join(AL, set_, case_dir, 'launched_feb.sha256')
    return open(f).read().split()[0] if os.path.exists(f) else None


def groups(rows, verd):
    """union-find over: genes + family, replicate lists, launched deck hashes (source dir and judged window dirs)"""
    par = {}
    def find(a):
        par.setdefault(a, a)
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    def union(a, b): par[find(a)] = find(b)
    for r in rows:
        d = r['design']; union(d, 'g:' + '|'.join(r[k] for k in GENES) + '|' + r['family'])
        for q in (ast.literal_eval(r['replicates']) if r['replicates'] else []): union(d, q)
        src = r['source'].split('/')
        if len(src) >= 2 and sha(src[0], src[1]): union(d, 'h:' + sha(src[0], src[1]))
        for w in verd.get(d, {}).get('windows', {}).values():
            if w.get('set') and w.get('case_dir') and sha(w['set'], w['case_dir']): union(d, 'h:' + sha(w['set'], w['case_dir']))
    return {r['design']: find(r['design']) for r in rows}


def features(r, fams, kind, extra=()):
    g = [np.log(float(r['hp_E_hard'])), np.log(float(r['hp_E_soft'])), float(r['hp_d']), float(r['hp_theta'])]
    if kind in ('D', 'DT'): g += [r['_desc'][k] for k in DNAMES]
    else: g += [float(r['family'] == f) for f in fams]
    return g + list(extra)


def gp(dim):
    k = C(1.0, (1e-2, 1e2)) * Matern(length_scale=np.ones(dim), length_scale_bounds=(1e-1, 1e2), nu=2.5) + WhiteKernel(0.1, (1e-5, 1e1))
    return GaussianProcessRegressor(k, normalize_y=True, n_restarts_optimizer=2, random_state=0)


def validate(X, y, grp, fam, log, by='group'):
    """leave-one-group-out (or leave-one-family-out) predictions; returns per-row mean, sd (model space), baseline"""
    X = np.asarray(X, float); t = np.log(y) if log else y.copy(); keys = grp if by == 'group' else fam
    mu = np.zeros(len(y)); sd = np.zeros(len(y)); base = np.zeros(len(y)); spread = np.zeros(len(y))
    for k in sorted(set(keys)):
        te = keys == k; tr = ~te
        assert not set(grp[te]) & set(grp[tr]), 'a group spans train and test'
        sc = StandardScaler().fit(X[tr]); m = gp(X.shape[1]).fit(sc.transform(X[tr]), t[tr])
        mu[te], sd[te] = m.predict(sc.transform(X[te]), return_std=True)
        for i in np.where(te)[0]:
            same = tr & (fam == fam[i]) if by == 'group' else tr
            base[i] = y[same].mean() if same.any() else y[tr].mean()
        spread[te] = np.percentile(y[tr], 95) - np.percentile(y[tr], 5)
    return mu, sd, base, spread


def report(y, mu, sd, base, spread, grp, fam, log, by='group'):
    back = np.exp if log else (lambda a: a)
    pred = back(mu); lo, hi = back(mu - Z * sd), back(mu + Z * sd); cov = (y >= lo) & (y <= hi); ng = len(set(grp))
    rmse = float(np.sqrt(np.mean((y - pred) ** 2))); rb = float(np.sqrt(np.mean((y - base) ** 2)))
    out = dict(n_rows=int(len(y)), n_groups=ng, empirical_coverage=round(float(cov.mean()), 3),
               coverage_2se=round(2 * float(np.sqrt(NOMINAL * (1 - NOMINAL) / ng)), 3) if by == 'group' else None, n_folds=ng if by == 'group' else len(set(fam)),
               width_median=round(float(np.median(hi - lo)), 4), width_p90=round(float(np.percentile(hi - lo, 90)), 4),
               train_spread_5_95=round(float(np.median(spread)), 4), mae=round(float(np.mean(np.abs(y - pred))), 4), rmse=round(rmse, 4),
               rmse_baseline=round(rb, 4), skill=round(1 - rmse / rb, 3) if rb > 0 else None)
    # pre-declared fallback: cross-conformal rescaling, quantile from the other groups only
    s = np.abs((np.log(y) if log else y) - mu) / np.maximum(sd, 1e-12); q = np.zeros(len(y))
    for g in set(grp):
        o = s[grp != g]; q[grp == g] = np.quantile(o, min(1.0, NOMINAL * (1 + 1.0 / len(o))), method='higher')
    lo2, hi2 = back(mu - q * sd), back(mu + q * sd); cov2 = (y >= lo2) & (y <= hi2)
    out['conformal'] = dict(empirical_coverage=round(float(((y >= lo2) & (y <= hi2)).mean()), 3), width_median=round(float(np.median(hi2 - lo2)), 4),
                            scale_vs_gaussian=round(float(np.median(q)) / Z, 2))
    gcov = lambda c, m: [float(c[m & (grp == g)].mean()) for g in sorted(set(grp[m]))]
    allm = np.ones(len(y), bool); out['coverage_by_group'] = round(float(np.mean(gcov(cov, allm))), 3)
    out['conformal']['coverage_by_group'] = round(float(np.mean(gcov(cov2, allm))), 3)
    def gate(c, w): return bool(0.80 <= c <= 0.95 and (out['skill'] or -1) >= 0.2 and w < out['train_spread_5_95']) if by == 'group' else None
    out['steer_gaussian'] = gate(out['empirical_coverage'], out['width_median'])
    out['steer_conformal'] = gate(out['conformal']['empirical_coverage'], out['conformal']['width_median'])
    out['per_family'] = {f: dict(n=int((fam == f).sum()), coverage=round(float(cov[fam == f].mean()), 2), conformal_coverage=round(float(cov2[fam == f].mean()), 2), mae=round(float(np.abs(y - pred)[fam == f].mean()), 4),
                                 rmse=round(float(np.sqrt(((y - pred)[fam == f] ** 2).mean())), 4), width_median=round(float(np.median((hi - lo)[fam == f])), 4))
                         if (fam == f).sum() >= 5 else dict(n=int((fam == f).sum()), note='too few for a number') for f in sorted(set(fam))}
    for f, d in out['per_family'].items():
        if 'coverage' not in d: continue
        gc, gc2 = gcov(cov, fam == f), gcov(cov2, fam == f); se2 = 2 * float(np.sqrt(NOMINAL * (1 - NOMINAL) / len(gc)))
        d.update(n_groups=len(gc), group_coverage=round(float(np.mean(gc)), 2), group_conformal_coverage=round(float(np.mean(gc2)), 2), group_2se=round(se2, 2),
                 under_covered=bool(np.mean(gc2) < NOMINAL - se2) if by == 'group' else None)
    return out, pred, lo, hi


def noise_sd(X, y, log):
    t = np.log(y) if log else y; m = gp(np.asarray(X).shape[1]).fit(StandardScaler().fit_transform(np.asarray(X, float)), t)
    return round(float(np.sqrt(m.kernel_.k2.noise_level) * t.std()), 4)


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else time.strftime('%Y-%m-%d')
    rows, verd, excl = load(); G = groups(rows, verd); fams = sorted({r['family'] for r in rows}); byd = {r['design']: r for r in rows}
    out = dict(date=date, nominal_coverage=NOMINAL, spec=__doc__.split('usage')[0].strip(), rows_with_genes=len(rows), rows_excluded_no_genes=excl,
               n_groups_all=len(set(G.values())), descriptor_names=DNAMES, targets={}, variants_tried=[])
    preds = []
    def run(name, sel, yv, log, extra=None, sets=('G', 'D'), unit=''):
        d = dict(unit=unit, log_target=log, n_rows=len(sel)); out['targets'][name] = d
        y = np.array(yv, float); grp = np.array([G[r['design']] for r in sel]); fam = np.array([r['family'] for r in sel])
        for kind in sets:
            ex = extra if extra is not None else [()] * len(sel)
            X = [features(r, fams, {'T': 'G', 'DT': 'D'}.get(kind, kind), tuple(e) if kind in ('T', 'DT') else tuple(e[:1])) for r, e in zip(sel, ex)]
            for by in (('group', 'family') if kind in ('D', 'DT') else ('group',)):
                mu, sd, base, spread = validate(X, y, grp, fam, log, by)
                rep, pred, lo, hi = report(y, mu, sd, base, spread, grp, fam, log, by)
                key = f'{kind}/leave-one-{by}-out'; d[key] = rep; out['variants_tried'].append(f'{name}:{key}')
                if by == 'group': rep['fitted_noise_sd_all_data'] = noise_sd(X, y, log)
                preds.extend([dict(target=name, variant=key, design=r['design'], group=g, family=f, y=float(a), pred=float(b), lo=float(c), hi=float(e_))
                          for r, g, f, a, b, c, e_ in zip(sel, grp, fam, y, pred, lo, hi)])
                print(f"{name:5s} {key:28s} n {len(y):3d} groups {rep['n_groups']:3d} cov {rep['empirical_coverage']:.2f}+-{rep['coverage_2se'] or 0:.2f} width {rep['width_median']:.3f} "
                      f"(spread {rep['train_spread_5_95']:.3f}) mae {rep['mae']:.3f} rmse {rep['rmse']:.3f} base {rep['rmse_baseline']:.3f} skill {rep['skill']:+.2f} "
                      f"steer {rep['steer_gaussian']} | conformal cov {rep['conformal']['empirical_coverage']:.2f} (by group {rep['conformal']['coverage_by_group']:.2f}) width {rep['conformal']['width_median']:.3f} steer {rep['steer_conformal']} under {[f for f, d in rep['per_family'].items() if d.get('under_covered')]}", flush=True)
    # friction targets (judged quantity at each window's evaluation point)
    for wn, ev, name in (('extension', 'ROM', 'post_ext'), ('flexion', '1.5Nm', 'uh_flex')):
        sel, yv, ex = [], [], []; seen = {}; copies = []; other = []
        for p, v in sorted(verd.items()):
            w = v['windows'].get(wn)
            if p not in byd or not w or not w.get('usable') or w.get('eval_point') != ev: continue
            val = w['u_h_at_1p5Nm'] if wn == 'flexion' else w['post_at_rom']      # flexion: any-direction translation; extension: signed posterior
            if val is None: continue
            key = (w.get('set'), w.get('case_dir'))
            if key in seen: copies.append(f'{p} = copy of {seen[key]}'); continue
            seen[key] = p
            if w.get('fallback') or w.get('set') == 'physio_fric2': other.append(p)
            tied = byd[p].get('mu_req_' + wn)
            sel.append(byd[p]); yv.append(val); ex.append((float(w['set'] in PROC_G), float(tied) if tied else np.nan))
        run(name, sel, yv, False, ex, ('G', 'D', 'T', 'DT') if not any(np.isnan(e[1]) for e in ex) else ('G', 'D'), 'mm')
        out['targets'][name].update(inherited_copies_dropped=copies, rows_not_stick_memory_law=other)
    sel = [r for r in rows if r['mu_req_max'] and r['lower_bound'] != 'True']
    run('y2', sel, [float(r['mu_req_max']) for r in sel], True, unit='friction coefficient')
    out['targets']['y2']['lower_bound_rows_excluded'] = sum(1 for r in rows if r['mu_req_max'] and r['lower_bound'] == 'True')
    sel = [r for r in rows if r['shear_req_p99_MPa']]
    run('y3', sel, [float(r['shear_req_p99_MPa']) for r in sel], True, unit='MPa')
    out['targets']['y3']['incomplete_readout_rows'] = sum(1 for r in sel if r['shear_req_complete'] != 'True')
    # y5 classifier: tied gate passed
    y = np.array([0.0 if 'compression' in r['verdict_class'] else 1.0 for r in rows]); grp = np.array([G[r['design']] for r in rows]); fam = np.array([r['family'] for r in rows])
    d5 = dict(n_rows=len(rows), positives=int(y.sum()), note='classifier: grouped Brier score against base rates (no interval coverage)'); out['targets']['y5'] = d5
    for kind in ('G', 'D'):
        X = np.array([features(r, fams, kind) for r in rows], float); p = np.zeros(len(y)); b = np.zeros(len(y)); bf = np.zeros(len(y))
        for g in sorted(set(grp)):
            te = grp == g; tr = ~te; sc = StandardScaler().fit(X[tr])
            m = GaussianProcessClassifier(C(1.0) * Matern(length_scale=np.ones(X.shape[1]), length_scale_bounds=(1e-1, 1e2), nu=2.5), random_state=0).fit(sc.transform(X[tr]), y[tr])
            p[te] = m.predict_proba(sc.transform(X[te]))[:, 1]; b[te] = y[tr].mean()
            for i in np.where(te)[0]: s_ = tr & (fam == fam[i]); bf[i] = y[s_].mean() if s_.any() else y[tr].mean()
        d5[kind + '/leave-one-group-out'] = dict(brier=round(float(((p - y) ** 2).mean()), 4), brier_base_rate=round(float(((b - y) ** 2).mean()), 4),
                                                 brier_family_rate=round(float(((bf - y) ** 2).mean()), 4), accuracy=round(float(((p > 0.5) == (y > 0.5)).mean()), 3))
        out['variants_tried'].append(f'y5:{kind}/leave-one-group-out'); print('y5', kind, d5[kind + '/leave-one-group-out'], flush=True)
    nc = [r['design'] for r in rows if any(s in r['verdict_class'] for s in ('unstable-window', 'computability', 'not-computable'))]
    out['targets']['y4'] = dict(positives=len(nc), designs=nc, note='too few positives to validate a classifier; counted only')
    os.makedirs(os.path.join(EVO, 'results/surrogate'), exist_ok=True)
    json.dump(out, open(os.path.join(EVO, f'results/surrogate/validation_{date}.json'), 'w'), indent=1, ensure_ascii=False)
    with open(os.path.join(EVO, f'results/surrogate/loo_predictions_{date}.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(preds[0])); w.writeheader(); w.writerows(preds)
    print('groups', out['n_groups_all'], 'rows', len(rows), 'excluded', excl, '-> results/surrogate/validation_%s.json' % date)


if __name__ == '__main__':
    main()
