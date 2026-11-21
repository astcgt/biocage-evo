"""Arm A proposals (ROUND2_ARCHITECTURE.md A5). The estimator only chooses WHAT to simulate; nothing here enters a verdict.

PI 2026-11-18 (three decisions on the cage height): (1) designs are compared at the SAME height above the natural disc space
(gene d, called 撐高量 in reports) - d is no longer a free gene of a proposal; (2) a 'loosened' condition tests fixation that
does not rely on the tissue squeeze force; (3) wording. Implemented as: every proposed design = family + material set, and
it is simulated at two fixed heights: REFERENCE 0.8 mm (squeeze force about 24 N) and LOOSENED 0.5 mm (about 9 N).
The PI delegated the two numbers (「你幫忙最佳化」); evidence in results/round2/settings_optimisation_2026-11-18.json:
  heights - at 1.0 mm every candidate of the usable families is predicted to pass (no information) and only 4 archive designs
  sit there; at 0.8 mm 61 % of the candidates are undecided, 5 archive designs (all PASS) support it, it is the lower, clinically
  more modest height, and its squeeze force is still 2.6 x that of the loosened height, so the two runs test different things;
  designs - adding designs inside the families barely narrows the estimator (mean interval 0.165 -> 0.163 mm after 12 designs),
  so arm A is cut to what it is needed for: 4 new designs x 2 heights + 2 replicates = 10 runs (3 steered + 1 exploration).

Models (as validated by ops/surrogate_fit.py, input set G = genes + family one-hot), refitted here from the tables:
  post_ext / uh_flex with the insertion process as an input; each candidate is predicted under BOTH processes and the less
  favourable one is used. mu_req (log) with the screening pass type as an input, predicted at the reference pass 'split
  windows'. Intervals: cross-conformal scale from the leave-one-group-out residuals of the same model (nominal 90 %).
P(limits) = P(post_ext < 0.45) x P(uh_flex < 1.0) at the REFERENCE height x family rate of 'not a compression class' x family
           rate of 'computable'. It is NOT the probability of the final class PASS (it ignores the shear flag and the grey zone of
           other windows; in radial_interleave 15 of 30 designs are PASS); it ranks candidates inside a family.
mu_req model: the pass-type variant is POST-HOC (results/surrogate/posthoc_2026-11-18_mu_req_pass_type.json), not part of the
           run-3 validation file: Gaussian coverage 0.70, cross-conformal 0.91 (the conformal scale is what is used here).
Fixation score (LOOSENED height) = mean of 1 - post_ext / 0.55 and 1 - mu_req / 0.35, both clipped to 0-1 (0.55 mm = upper
           edge of the grey zone, 0.35 = friction coefficient of the production runs).
Utility  = 0.8 x fixation score + 0.2 x space score (PI: 80 : 20; space score = (void fraction - 0.5) / 0.5, the same for
           every design-A candidate today).
Score    = P(pass) x utility + 0.3 x (interval width of post_ext at the loosened height / training spread); picked greedily
           with a distance penalty in material space.
Candidate pool: design-A families whose designs are not almost always in a compression class (rate >= 0.3) and that are not
the excluded radial_mix class; material genes drawn inside the box each family has been sampled in. Steered picks only from
families with >= 10 friction rows and inside the data at both heights; exploration = the material set farthest from every
simulated design, one in each pool family. Replicates: the existing designs closest to each of the two fixed heights whose
posterior translation is nearest the 0.45 mm limit.
usage: python ops/propose_round.py <out_dir> [n_candidates=4000] [seed=0]      (dry run: writes files, launches nothing)
"""
import os, sys, json, time, collections
import numpy as np
from scipy.stats import norm
from sklearn.preprocessing import StandardScaler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surrogate_fit as S

LIM_POST, LIM_UH, MU_REAL, BETA, W_FIX, W_SPACE, Z = 0.45, 1.0, 0.3, 0.3, 0.8, 0.2, 1.6449   # MU_REAL 0.35 -> 0.3: PI 2026-11-22 (platform pending item 17; official friction coefficient since PI 2026-11-20 decision 9); amendment results/round2/prereg_amendment_2026-11-22a.json
N_STEER, N_EXPLORE, N_REPL, MIN_ROWS = 3, 1, 2, 10
H_REF, H_LOOSE, LIM_GREY_HI = 0.8, 0.5, 0.55
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
    out_dir = sys.argv[1]; n_c = int(sys.argv[2]) if len(sys.argv) > 2 else 4000; seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
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
    # ---- candidate pool: family + material set (the height is fixed, not proposed)
    fric_rows = collections.Counter(r['family'] for r in fr['post_ext'][0])
    rate = {f: float(np.mean(['compression' not in r['verdict_class'] for r in rows if r['family'] == f])) for f in fams}
    NC = ('unstable-window', 'computability', 'not-computable'); rate_c = {f: float(np.mean([not any(k in r['verdict_class'] for k in NC) for r in rows if r['family'] == f])) for f in fams}
    pool_fams = [f for f in fams if not f.startswith('B_') and f != 'radial_mix' and rate[f] >= 0.3]
    MAT = ['hp_E_hard', 'hp_E_soft', 'hp_theta']; cands = []
    for f in pool_fams:
        fr_ = [r for r in rows if r['family'] == f]; lo = {k: min(float(r[k]) for r in fr_) for k in MAT}; hi = {k: max(float(r[k]) for r in fr_) for k in MAT}
        for _ in range(n_c // len(pool_fams)):
            cands.append(dict(family=f, hp_E_hard=float(np.exp(rng.uniform(np.log(lo['hp_E_hard']), np.log(hi['hp_E_hard'])))), hp_E_soft=float(np.exp(rng.uniform(np.log(lo['hp_E_soft']), np.log(hi['hp_E_soft'])))), hp_theta=float(rng.uniform(lo['hp_theta'], hi['hp_theta']))))
    at = lambda h: [dict(c, hp_d=h) for c in cands]; fc = np.array([c['family'] for c in cands])
    gene = lambda r: np.array([np.log(float(r['hp_E_hard'])), np.log(float(r['hp_E_soft'])), float(r['hp_d']), float(r['hp_theta'])])
    sc = StandardScaler().fit(np.array([gene(r) for r in rows])); Ztr = sc.transform(np.array([gene(r) for r in fr['post_ext'][0]])); ftr = np.array([r['family'] for r in fr['post_ext'][0]])
    Zall = sc.transform(np.array([gene(r) for r in rows])); fall = np.array([r['family'] for r in rows]); thr = {}; nn = {}; nn_all = np.zeros(len(cands))
    for h in (H_REF, H_LOOSE):
        Zc = sc.transform(np.array([gene(c) for c in at(h)])); nn[h] = np.full(len(cands), np.inf)
        for f in pool_fams:
            A = Ztr[ftr == f]
            if len(A) >= 2:
                D_ = np.linalg.norm(A[:, None] - A[None], axis=2); np.fill_diagonal(D_, np.inf); thr[f] = float(D_.min(1).max()); nn[h][fc == f] = np.linalg.norm(Zc[fc == f][:, None] - A[None], axis=2).min(1)
            nn_all[fc == f] = np.maximum(nn_all[fc == f], np.linalg.norm(Zc[fc == f][:, None] - Zall[fall == f][None], axis=2).min(1))
    Zm = sc.transform(np.array([gene(c) for c in at(H_REF)]))[:, [0, 1, 3]]          # material coordinates for the spread penalty
    # ---- predictions at both heights (both insertion processes; the less favourable one counts)
    def predict(h):
        C = at(h); o = {}
        for name, M in (('post_ext', M_post), ('uh_flex', M_uh)):
            a = [M.predict(C, [(p,)] * len(C)) for p in (0.0, 1.0)]; worst = np.argmax([a[0][0], a[1][0]], axis=0)
            o[name] = np.where(worst == 0, a[0][0], a[1][0]); o[name + '_sd'] = np.where(worst == 0, a[0][1], a[1][1])
        m, _ = M_mu.predict(C, [(0.0, 1.0)] * len(C)); o['mu_req'] = np.exp(m); return o
    R, L = predict(H_REF), predict(H_LOOSE)
    p_pass = norm.cdf((LIM_POST - R['post_ext']) / R['post_ext_sd']) * norm.cdf((LIM_UH - R['uh_flex']) / R['uh_flex_sd']) * np.array([rate[f] * rate_c[f] for f in fc])
    fix = 0.5 * np.clip(1 - L['post_ext'] / LIM_GREY_HI, 0, 1) + 0.5 * np.clip(1 - L['mu_req'] / MU_REAL, 0, 1)
    void = 0.597; util = W_FIX * fix + W_SPACE * (void - 0.5) / 0.5
    unc = 2 * Z * L['post_ext_sd'] / M_post.spread; score = p_pass * util + BETA * unc
    has_data = np.array([fric_rows[f] >= MIN_ROWS for f in fc]); ood = np.array([max(nn[H_REF][i], nn[H_LOOSE][i]) > thr.get(fc[i], -1) for i in range(len(cands))]); steerable = has_data & ~ood
    def pick(n, mask, key, chosen, ell=0.7):
        got = []; k = key.copy()
        for _ in range(n):
            idx = np.where(mask & ~np.isin(np.arange(len(cands)), chosen + got))[0]
            if not len(idx): break
            j = idx[np.argmax(k[idx])]; got.append(int(j)); dist = np.linalg.norm(Zm - Zm[j], axis=1); k = k * np.where(fc == fc[j], 1 - np.exp(-(dist / ell) ** 2), 1.0)
        return got
    steer = pick(N_STEER, steerable, score, []); explore = []
    for f in sorted(pool_fams, key=lambda f: -rate[f])[:N_EXPLORE]: explore += pick(1, fc == f, nn_all, steer + explore)
    r3 = lambda a: round(float(a), 3)
    def row(i, source, why):
        c = cands[i]; iv = lambda o: [r3(o['post_ext'][i] - Z * o['post_ext_sd'][i]), r3(o['post_ext'][i] + Z * o['post_ext_sd'][i])]
        return dict(source=source, why=why, family=c['family'], E_hard_MPa=round(c['hp_E_hard'], 1), E_soft_MPa=round(c['hp_E_soft'], 3), theta=round(c['hp_theta'], 3),
            runs=[dict(height_mm=H_REF, role='reference: the verdict is read here', predicted=dict(post_ext_mm=r3(R['post_ext'][i]), post_ext_interval90_mm=iv(R), uh_flex_mm=r3(R['uh_flex'][i]), mu_req=round(float(R['mu_req'][i]), 4))),
                  dict(height_mm=H_LOOSE, role='loosened: fixation without relying on the squeeze force', predicted=dict(post_ext_mm=r3(L['post_ext'][i]), post_ext_interval90_mm=iv(L), uh_flex_mm=r3(L['uh_flex'][i]), mu_req=round(float(L['mu_req'][i]), 4)))],
            predicted=dict(p_limits_reference=r3(p_pass[i]), fixation_score_loosened=r3(fix[i]), utility=r3(util[i]), score=r3(score[i])),
            flags=dict(out_of_distribution=bool(ood[i]), family_has_friction_data=bool(has_data[i]), under_covered_family_for=['uh_flex', 'mu_req'] if c['family'] == 'radial_interleave' else []))
    props = [row(i, 'surrogate', 'highest P(limits met at the reference height) x utility (fixation at the loosened height) + uncertainty bonus, spread over materials') for i in steer] + \
            [row(i, 'exploration', 'material set farthest from every simulated design of its family') for i in explore]
    sel, yv, _ = fr['post_ext']
    for h in (H_LOOSE, H_REF):       # replicates: existing designs at the two fixed heights, nearest the limit
        js = [j for j, r in enumerate(sel) if r['family'] in pool_fams and abs(float(r['hp_d']) - h) < 0.026]
        if js:
            j = min(js, key=lambda j: abs(yv[j] - LIM_POST)); r = sel[j]
            props.append(dict(source='replicate', why=f'existing design at height {h} mm closest to the 0.45 mm limit', replicate_of=r['design'], family=r['family'], E_hard_MPa=float(r['hp_E_hard']), E_soft_MPa=float(r['hp_E_soft']), theta=float(r['hp_theta']),
                              runs=[dict(height_mm=float(r['hp_d']), role='replicate', observed_post_ext_mm=round(float(yv[j]), 3))]))
    for k, p in enumerate(props): p['id'] = f'A-{k + 1:02d}'
    os.makedirs(out_dir, exist_ok=True)
    meta = dict(status='DRY RUN - NOT LAUNCHED (waits for the from-scratch insertion fix and the new-design runner)', arm='A', created=time.strftime('%Y-%m-%d %H:%M'), seed=seed, n_candidates=len(cands),
                heights_mm=dict(reference=H_REF, loosened=H_LOOSE), runs=sum(len(p['runs']) for p in props), weights=dict(fixation=W_FIX, space=W_SPACE), limits=dict(post_ext_mm=LIM_POST, uh_flex_mm=LIM_UH, grey_upper_mm=LIM_GREY_HI), mu_real=MU_REAL, beta=BETA,
                reference_conditions=dict(screening_pass='split windows', insertion_process='both predicted, less favourable used'),
                conformal_scale=dict(post_ext=round(M_post.q / Z, 2), uh_flex=round(M_uh.q / Z, 2), mu_req=round(M_mu.q / Z, 2)), pool_families=pool_fams, friction_rows_per_family=dict(fric_rows), family_rate_not_compression={f: round(rate[f], 2) for f in fams if not f.startswith('B_')}, family_rate_computable={f: round(rate_c[f], 2) for f in pool_fams},
                notes=dict(p_limits='probability that the translation limits are met at the reference height x family rates; not the PASS-class probability', mu_req_model='post-hoc pass-type variant (Gaussian coverage 0.70, conformal 0.91), not in the run-3 validation file',
                           integrator_choices='fixed heights 1.0 / 0.5 mm, run budget 20 = 9 designs x 2 heights + 2 replicates, spread penalty in material space, fixation score formula, space score fixed at void 0.597'),
                pool_summary=dict(candidates=len(cands), steerable=int(steerable.sum()), out_of_distribution=int(ood.sum()), p_limits_reference_gt_0p5=int((p_pass > 0.5).sum()),
                                  fixation_score_loosened_range=[r3(fix.min()), r3(fix.max())], post_ext_loosened_range_mm=[r3(L['post_ext'].min()), r3(L['post_ext'].max())]),
                inputs={f: time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(S.EVO, f)))) for f in ('results/method/mu_req_field.csv', 'results/method/fric/verdicts.json')})
    json.dump(dict(meta=meta, proposals=props), open(os.path.join(out_dir, 'proposals.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(meta['pool_summary']), meta['runs'], 'runs')
    for p in props:
        if p['source'] == 'replicate': print(p['id'], 'replic', p['family'][:17].ljust(17), 'of', p['replicate_of'], 'height', p['runs'][0]['height_mm'], 'observed', p['runs'][0]['observed_post_ext_mm']); continue
        a, b = p['runs'][0]['predicted'], p['runs'][1]['predicted']
        print(p['id'], p['source'][:6], p['family'][:17].ljust(17), 'Eh %6.0f Es %5.2f th %.2f | ref post %.3f mu %.3f P %.2f | loose post %.3f %s mu %.3f fix %.3f %s' % (p['E_hard_MPa'], p['E_soft_MPa'], p['theta'], a['post_ext_mm'], a['mu_req'],
              p['predicted']['p_limits_reference'], b['post_ext_mm'], b['post_ext_interval90_mm'], b['mu_req'], p['predicted']['fixation_score_loosened'], 'OOD' if p['flags']['out_of_distribution'] else ''))


if __name__ == '__main__':
    main()
