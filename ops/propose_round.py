"""Arm A proposals (ROUND2_ARCHITECTURE.md A5; PI 2026-11-18: weight fixation 80 : space 20; batch 20 = 14 steered + 4 pure
exploration + 2 replicates). The estimator only chooses WHAT to simulate; nothing here enters a verdict or a label.

Models (as validated by ops/surrogate_fit.py, input set G = genes + family one-hot), refitted here from the tables:
  post_ext  posterior translation in extension (limit 0.45 mm) and uh_flex translation in flexion (limit 1.0 mm), each with
            the insertion process as an input. The process is confounded with the distraction d in the data, so every
            candidate is predicted under BOTH processes and the less favourable one is used (both are stored).
  mu_req    required friction coefficient (log), with the screening pass type as an input (post-hoc finding 2026-11-18);
            candidates are predicted at the reference pass 'split windows' (the production pass of highest precedence).
Intervals: cross-conformal scale from the leave-one-group-out residuals of the same model (nominal 90 %).
Not modelled: 'not a compression class' = family rate from the table; computability (6 cases) and shear (flag) are ignored.
P(pass) = P(post_ext < 0.45) x P(uh_flex < 1.0) x family rate.
Utility  = 0.8 x fixation score + 0.2 x space score; fixation score = mean of (0.45 - post_ext) / 0.45 and
           1 - mu_req / 0.35 (0.35 = friction coefficient of the production runs), both clipped to 0-1; space score =
           (void fraction - 0.5) / 0.5 (the same 0.597 for every design-A candidate today).
Score    = P(pass) x utility + 0.3 x (interval width of post_ext / training spread); the batch is picked greedily with a
           distance penalty so that picks spread out.
Candidate pool: design-A families only; radial_mix is left out (excluded class). Genes are drawn inside the box each family
has been sampled in; d on a 0.05 mm grid. Steered picks only from families with >= 10 friction rows and inside the data
(nearest-neighbour distance not larger than the largest one seen among the training designs of that family); everything
else is exploration-only. Steered picks: at most 2 per distraction value (without this cap the first dry run put all 14 at
d 1.45-1.50 mm: the estimator's main lesson is 'more distraction holds better'). Exploration: 2 picks in radial_interleave at
d 0.9-1.2 mm (where the flexion model misses) + 2 space-filling picks in the other families that do not almost always fail
the compression class. Replicates: the existing design closest to the 0.45 mm limit and the median one, pool families only.
usage: python ops/propose_round.py <out_dir> [n_candidates=5000] [seed=0]      (dry run: writes files, launches nothing)
"""
import os, sys, json, time, collections
import numpy as np
from scipy.stats import norm
from sklearn.preprocessing import StandardScaler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surrogate_fit as S

LIM_POST, LIM_UH, MU_REAL, BETA, W_FIX, W_SPACE, Z = 0.45, 1.0, 0.35, 0.3, 0.8, 0.2, 1.6449
N_STEER, N_EXPLORE, N_REPL, MIN_ROWS, MAX_PER_D = 14, 4, 2, 10, 2
PASS_KIND = {'physio_rot': 'static', 'physio_rot_r2': 'static', 'physio_rot_dyn': 'dyn', 'physio_rot_dyn2': 'dyn'}
pass_extra = lambda src: (float(PASS_KIND.get(src.split('/')[0], 'split') == 'dyn'), float(PASS_KIND.get(src.split('/')[0], 'split') == 'split'))


class Model:
    def __init__(self, sel, y, extra, grp, fam, fams, log):
        self.fams, self.log = fams, log; y = np.array(y, float); X = np.array([S.features(r, fams, 'G', e) for r, e in zip(sel, extra)], float)
        mu, sd, _, spread = S.validate(X, y, grp, fam, log, 'group'); t = np.log(y) if log else y
        s = np.abs(t - mu) / np.maximum(sd, 1e-12); self.q = float(np.quantile(s, min(1.0, 0.9 * (1 + 1.0 / len(s))), method='higher'))
        self.spread = float(np.percentile(y, 95) - np.percentile(y, 5)); self.sc = StandardScaler().fit(X); self.m = S.gp(X.shape[1]).fit(self.sc.transform(X), t)

    def predict(self, cands, extra):
        X = np.array([S.features(c, self.fams, 'G', e) for c, e in zip(cands, extra)], float); mu, sd = self.m.predict(self.sc.transform(X), return_std=True)
        return mu, sd * self.q / Z          # mean and conformal-scaled standard deviation (model space)


def main():
    out_dir = sys.argv[1]; n_c = int(sys.argv[2]) if len(sys.argv) > 2 else 5000; seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    rng = np.random.default_rng(seed); rows, verd, _ = S.load(); G = S.groups(rows, verd); fams = sorted({r['family'] for r in rows}); byd = {r['design']: r for r in rows}
    # ---- training sets (same selection as surrogate_fit)
    fr = {}
    for wn, ev, name in (('extension', 'ROM', 'post_ext'), ('flexion', '1.5Nm', 'uh_flex')):
        sel, yv, ex, seen = [], [], [], set()
        for p, v in sorted(verd.items()):
            w = v['windows'].get(wn)
            if p not in byd or not w or not w.get('usable') or w.get('eval_point') != ev: continue
            val = w['u_h_at_1p5Nm'] if wn == 'flexion' else w['post_at_rom']; key = (w.get('set'), w.get('case_dir'))
            if val is None or key in seen: continue
            seen.add(key); sel.append(byd[p]); yv.append(val); ex.append((float(w['set'] in S.PROC_G),))
        fr[name] = (sel, yv, ex)
    def model(sel, yv, ex, log): return Model(sel, yv, ex, np.array([G[r['design']] for r in sel]), np.array([r['family'] for r in sel]), fams, log)
    M_post, M_uh = model(*fr['post_ext'], False), model(*fr['uh_flex'], False)
    sel2 = [r for r in rows if r['mu_req_max'] and r['lower_bound'] != 'True']
    M_mu = model(sel2, [float(r['mu_req_max']) for r in sel2], [pass_extra(r['source']) for r in sel2], True)
    # ---- candidate pool
    fric_rows = collections.Counter(r['family'] for r in fr['post_ext'][0])
    rate = {f: float(np.mean(['compression' not in r['verdict_class'] for r in rows if r['family'] == f])) for f in fams}
    pool_fams = [f for f in fams if not f.startswith('B_') and f != 'radial_mix']
    cands = []
    for f in pool_fams:
        fr_ = [r for r in rows if r['family'] == f]; lo = {k: min(float(r[k]) for r in fr_) for k in S.GENES}; hi = {k: max(float(r[k]) for r in fr_) for k in S.GENES}
        for _ in range(n_c // len(pool_fams)):
            cands.append(dict(family=f, hp_E_hard=float(np.exp(rng.uniform(np.log(lo['hp_E_hard']), np.log(hi['hp_E_hard'])))), hp_E_soft=float(np.exp(rng.uniform(np.log(lo['hp_E_soft']), np.log(hi['hp_E_soft'])))),
                              hp_d=float(np.round(rng.uniform(lo['hp_d'], hi['hp_d']) / 0.05) * 0.05), hp_theta=float(rng.uniform(lo['hp_theta'], hi['hp_theta']))))
    for c in cands: c['hp_d'] = round(min(max(c['hp_d'], 0.5), 1.5), 2)
    gene = lambda r: np.array([np.log(float(r['hp_E_hard'])), np.log(float(r['hp_E_soft'])), float(r['hp_d']), float(r['hp_theta'])])
    Xtr = np.array([gene(r) for r in fr['post_ext'][0]]); sc = StandardScaler().fit(np.array([gene(r) for r in rows])); Ztr = sc.transform(Xtr); ftr = np.array([r['family'] for r in fr['post_ext'][0]])
    Zc = sc.transform(np.array([gene(c) for c in cands])); fc = np.array([c['family'] for c in cands])
    nn = np.full(len(cands), np.inf); thr = {}
    for f in pool_fams:
        A = Ztr[ftr == f]
        if len(A) < 2: continue
        D = np.linalg.norm(A[:, None] - A[None], axis=2); np.fill_diagonal(D, np.inf); thr[f] = float(D.min(1).max())
        nn[fc == f] = np.linalg.norm(Zc[fc == f][:, None] - A[None], axis=2).min(1)
    # ---- predictions (both insertion processes; the less favourable one counts)
    P = {}
    for name, M in (('post_ext', M_post), ('uh_flex', M_uh)):
        a = [M.predict(cands, [(p,)] * len(cands)) for p in (0.0, 1.0)]; worst = np.argmax([a[0][0], a[1][0]], axis=0)
        P[name] = dict(mean=np.where(worst == 0, a[0][0], a[1][0]), sd=np.where(worst == 0, a[0][1], a[1][1]), production=a[0][0], process_G=a[1][0])
    mu_m, mu_s = M_mu.predict(cands, [(0.0, 1.0)] * len(cands)); mu_req = np.exp(mu_m)
    p_post = norm.cdf((LIM_POST - P['post_ext']['mean']) / P['post_ext']['sd']); p_uh = norm.cdf((LIM_UH - P['uh_flex']['mean']) / P['uh_flex']['sd'])
    p_pass = p_post * p_uh * np.array([rate[f] for f in fc])
    fix = 0.5 * np.clip((LIM_POST - P['post_ext']['mean']) / LIM_POST, 0, 1) + 0.5 * np.clip(1 - mu_req / MU_REAL, 0, 1)
    void = 0.597; util = W_FIX * fix + W_SPACE * (void - 0.5) / 0.5
    unc = 2 * Z * P['post_ext']['sd'] / M_post.spread; score = p_pass * util + BETA * unc
    has_data = np.array([fric_rows[f] >= MIN_ROWS for f in fc]); ood = np.array([nn[i] > thr.get(fc[i], -1) for i in range(len(cands))])
    steerable = has_data & ~ood
    dval = np.array([c['hp_d'] for c in cands])
    def pick(n, mask, key, chosen, ell=0.5, cap=None):
        got = []; k = key.copy()
        for _ in range(n):
            full = [d_ for d_, m_ in collections.Counter(dval[got].tolist()).items() if cap and m_ >= cap]
            idx = np.where(mask & ~np.isin(np.arange(len(cands)), chosen + got) & ~np.isin(dval, full))[0]
            if not len(idx): break
            j = idx[np.argmax(k[idx])]; got.append(int(j)); dist = np.linalg.norm(Zc - Zc[j], axis=1); k = k * np.where(fc == fc[j], 1 - np.exp(-(dist / ell) ** 2), 1.0)
        return got
    steer = pick(N_STEER, steerable, score, [], cap=MAX_PER_D)      # at most 2 picks per distraction value, so the batch does not collapse onto the largest d
    zone = (fc == 'radial_interleave') & (np.array([c['hp_d'] for c in cands]) >= 0.9) & (np.array([c['hp_d'] for c in cands]) <= 1.2)
    unc_uh = P['uh_flex']['sd'] / M_uh.spread
    ex1 = pick(N_EXPLORE // 2, zone, unc_uh, steer)
    # space filling outside radial_interleave: candidates farthest from every simulated design of their family (whole table),
    # in the families that do not almost always fail the compression class (rate >= 0.3)
    nn_all = np.zeros(len(cands))
    for f in pool_fams:
        A = sc.transform(np.array([gene(r) for r in rows if r['family'] == f])); nn_all[fc == f] = np.linalg.norm(Zc[fc == f][:, None] - A[None], axis=2).min(1)
    ok_f = np.array([f != 'radial_interleave' and rate[f] >= 0.3 for f in fc])
    ex2 = pick(N_EXPLORE - len(ex1), ok_f, nn_all, steer + ex1)
    def row(i, source, why):
        c = cands[i]; return dict(source=source, why=why, family=c['family'], d_mm=c['hp_d'], E_hard_MPa=round(c['hp_E_hard'], 1), E_soft_MPa=round(c['hp_E_soft'], 3), theta=round(c['hp_theta'], 3),
            predicted=dict(post_ext_mm=round(float(P['post_ext']['mean'][i]), 3), post_ext_interval90_mm=[round(float(P['post_ext']['mean'][i] - Z * P['post_ext']['sd'][i]), 3), round(float(P['post_ext']['mean'][i] + Z * P['post_ext']['sd'][i]), 3)],
                           post_ext_production_vs_G=[round(float(P['post_ext']['production'][i]), 3), round(float(P['post_ext']['process_G'][i]), 3)], uh_flex_mm=round(float(P['uh_flex']['mean'][i]), 3),
                           mu_req=round(float(mu_req[i]), 4), p_pass=round(float(p_pass[i]), 3), utility=round(float(util[i]), 3), score=round(float(score[i]), 3)),
            flags=dict(out_of_distribution=bool(ood[i]), family_has_friction_data=bool(has_data[i]), under_covered_family_for=['uh_flex', 'mu_req'] if c['family'] == 'radial_interleave' else [],
                       base_mesh_exists=bool(any(r['family'] == c['family'] and abs(float(r['hp_d']) - c['hp_d']) < 1e-6 for r in rows))))
    props = [row(i, 'surrogate', 'highest P(pass) x utility + uncertainty bonus, spread out') for i in steer] + \
            [row(i, 'exploration', 'radial_interleave, d 0.9-1.2 mm: largest flexion uncertainty (miss zone of the estimator)') for i in ex1] + \
            [row(i, 'exploration', 'space filling: farthest from every simulated design of its family (families other than radial_interleave)') for i in ex2]
    # replicates: existing designs, the one closest to the limit and the median one (complete windows)
    keep = [j for j, r in enumerate(fr['post_ext'][0]) if r['family'] in pool_fams]; sel = [fr['post_ext'][0][j] for j in keep]; yv = [fr['post_ext'][1][j] for j in keep]
    order = np.argsort(np.abs(np.array(yv) - LIM_POST)); med = int(np.argsort(yv)[len(yv) // 2])
    for j, why in ((int(order[0]), 'existing design closest to the 0.45 mm limit'), (med, 'existing design at the median posterior translation')):
        r = sel[j]; props.append(dict(source='replicate', why=why, replicate_of=r['design'], family=r['family'], d_mm=float(r['hp_d']), E_hard_MPa=float(r['hp_E_hard']), E_soft_MPa=float(r['hp_E_soft']), theta=float(r['hp_theta']), observed_post_ext_mm=round(float(yv[j]), 3)))
    for k, p in enumerate(props): p['id'] = f'A-{k + 1:02d}'
    os.makedirs(out_dir, exist_ok=True)
    meta = dict(status='DRY RUN - NOT LAUNCHED (waits for the from-scratch insertion fix and the new-design runner)', arm='A', created=time.strftime('%Y-%m-%d %H:%M'), seed=seed, n_candidates=len(cands),
                weights=dict(fixation=W_FIX, space=W_SPACE), limits=dict(post_ext_mm=LIM_POST, uh_flex_mm=LIM_UH), mu_real=MU_REAL, beta=BETA, reference_conditions=dict(screening_pass='split windows', insertion_process='both predicted, less favourable used'),
                conformal_scale=dict(post_ext=round(M_post.q / Z, 2), uh_flex=round(M_uh.q / Z, 2), mu_req=round(M_mu.q / Z, 2)), pool_families=pool_fams, friction_rows_per_family=dict(fric_rows), family_rate_not_compression={f: round(rate[f], 2) for f in pool_fams},
                pool_summary=dict(steerable=int(steerable.sum()), out_of_distribution=int(ood.sum()), p_pass_gt_0p5=int((p_pass > 0.5).sum())),
                inputs={f: time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(S.EVO, f)))) for f in ('results/method/mu_req_field.csv', 'results/method/fric/verdicts.json')})
    json.dump(dict(meta=meta, proposals=props), open(os.path.join(out_dir, 'proposals.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(meta['pool_summary']), meta['conformal_scale'])
    for p in props:
        pr = p.get('predicted', {}); print(p['id'], p['source'][:6], p['family'][:17].ljust(17), 'd %.2f Eh %6.0f Es %5.2f th %.2f' % (p['d_mm'], p['E_hard_MPa'], p['E_soft_MPa'], p['theta']),
              ('post %.3f %s uh %.2f mu %.3f P %.2f' % (pr['post_ext_mm'], pr['post_ext_interval90_mm'], pr['uh_flex_mm'], pr['mu_req'], pr['p_pass'])) if pr else 'replicate of ' + p['replicate_of'], 'OOD' if p.get('flags', {}).get('out_of_distribution') else '')


if __name__ == '__main__':
    main()
