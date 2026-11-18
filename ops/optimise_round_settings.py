"""Choice of the two round-2 settings the PI delegated on 2026-11-18 (「你幫忙最佳化」): (a) the two fixed heights at which every
design is simulated, (b) how many NEW designs arm A runs. Evidence only from the archive and the validated estimator;
nothing is launched. Output: results/round2/settings_optimisation_<date>.json.

(a) Heights. For each candidate height h: squeeze force (archive median), number of archive designs at h (support of the
    estimator and of replicates), and - over 600 random material sets in the two usable families - the predicted posterior
    translation in extension, its 90 % interval width, the share of candidates whose outcome is UNDECIDED
    (0.1 < P(post_ext < 0.45) < 0.9) and the spread between candidates relative to the interval (how well designs can be
    told apart). Criteria, declared here: the REFERENCE height should be clinically modest (well below the 2 mm linked with
    subsidence), well supported by archive designs, and not trivially passed; the LOOSENED height should have the lowest
    squeeze force that the archive still covers.
(b) Designs in arm A. Mean interval width of the posterior translation over the pool (both heights) after adding k designs
    chosen one at a time where the uncertainty is largest (the Gaussian process variance does not need the outcomes). The
    design count is taken where one more design lowers the mean width by less than 2 % of the starting width.
usage: python ops/optimise_round_settings.py [YYYY-MM-DD]
"""
import os, sys, json, time, collections
import numpy as np
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surrogate_fit as S
from propose_round import Model, Z, LIM_POST

date = sys.argv[1] if len(sys.argv) > 1 else time.strftime('%Y-%m-%d'); rng = np.random.default_rng(0)
rows, verd, _ = S.load(); G = S.groups(rows, verd); fams = sorted({r['family'] for r in rows}); byd = {r['design']: r for r in rows}
sel, yv, ex, seen = [], [], [], set()
for p, v in sorted(verd.items()):
    w = v['windows'].get('extension')
    if p not in byd or not w or not w.get('usable') or w.get('eval_point') != 'ROM' or w.get('post_at_rom') is None: continue
    key = (w.get('set'), w.get('case_dir'))
    if key in seen: continue
    seen.add(key); sel.append(byd[p]); yv.append(w['post_at_rom']); ex.append((float(w['set'] in S.PROC_G),))
M = Model(sel, yv, ex, np.array([G[r['design']] for r in sel]), np.array([r['family'] for r in sel]), fams, False)
pts = {('p%03d' % p['id']): p for p in json.load(open(os.path.join(S.PLAT, 'human_study/al_v2/points.json')))['points']}
POOL = ['radial_interleave', 'axial_mix']; MAT = ['hp_E_hard', 'hp_E_soft', 'hp_theta']; cands = []
for f in POOL:
    fr_ = [r for r in rows if r['family'] == f]; lo = {k: min(float(r[k]) for r in fr_) for k in MAT}; hi = {k: max(float(r[k]) for r in fr_) for k in MAT}
    for _ in range(300):
        cands.append(dict(family=f, hp_E_hard=float(np.exp(rng.uniform(np.log(lo['hp_E_hard']), np.log(hi['hp_E_hard'])))), hp_E_soft=float(np.exp(rng.uniform(np.log(lo['hp_E_soft']), np.log(hi['hp_E_soft'])))), hp_theta=float(rng.uniform(lo['hp_theta'], hi['hp_theta']))))
def pred(h):
    C = [dict(c, hp_d=h) for c in cands]; a = [M.predict(C, [(p,)] * len(C)) for p in (0.0, 1.0)]; worst = np.argmax([a[0][0], a[1][0]], axis=0)
    return np.where(worst == 0, a[0][0], a[1][0]), np.where(worst == 0, a[0][1], a[1][1])
out = dict(date=date, heights=[], declared=__doc__.split('usage')[0].strip())
for h in (0.5, 0.65, 0.8, 0.9, 1.0, 1.1, 1.2, 1.35, 1.5):
    m, sd = pred(h); P = norm.cdf((LIM_POST - m) / sd)
    arch = [r for r in rows if r['family'] in POOL and abs(float(r['hp_d']) - h) < 0.026]; fric = [r for r in sel if r['family'] in POOL and abs(float(r['hp_d']) - h) < 0.026]
    cl = [pts[r['design']]['res']['clamp_N'] for r in rows if abs(float(r['hp_d']) - h) < 0.026 and r['design'] in pts and pts[r['design']].get('res') and pts[r['design']]['res'].get('clamp_N') is not None]
    d = dict(height_mm=h, squeeze_force_N=round(float(np.median(cl)), 1) if cl else None, archive_designs_pool_families=len(arch), with_friction_windows=len(fric),
             archive_classes=dict(collections.Counter('PASS' if r['verdict_class'] == 'PASS' else 'GREY' if 'GREY' in r['verdict_class'] else 'other' for r in arch)),
             predicted_post_ext_mm=[round(float(np.percentile(m, q)), 3) for q in (5, 50, 95)], interval_width_mm=round(float(np.median(2 * Z * sd)), 3),
             share_undecided=round(float(((P > 0.1) & (P < 0.9)).mean()), 2), share_p_gt_0p9=round(float((P >= 0.9).mean()), 2), share_p_lt_0p1=round(float((P <= 0.1).mean()), 2),
             spread_between_designs_over_interval=round(float((np.percentile(m, 95) - np.percentile(m, 5)) / np.median(2 * Z * sd)), 2))
    out['heights'].append(d); print(json.dumps(d, ensure_ascii=False), flush=True)
# (b) how many new designs: sequential uncertainty sampling, exact GP variance update (no outcomes needed)
def X_of(C, h, proc): return np.array([S.features(dict(c, hp_d=h), fams, 'G', (proc,)) for c in C], float)
def curve(h_ref, h_loose, kmax=18):
    Xtr = M.sc.transform(np.array([S.features(r, fams, 'G', e) for r, e in zip(sel, ex)], float)); K = M.m.kernel_
    blocks = [M.sc.transform(X_of(cands, h, p)) for h in (h_ref, h_loose) for p in (0.0, 1.0)]; Xp = np.vstack(blocks); n = len(cands)
    Xa = Xtr.copy(); widths = []; chosen = []
    for k in range(kmax + 1):
        Kaa = K(Xa); L = np.linalg.cholesky(Kaa + 1e-10 * np.eye(len(Xa))); Ks = K(Xa, Xp); v = np.linalg.solve(L, Ks)
        var = np.clip(K.diag(Xp) - (v ** 2).sum(0), 1e-12, None); sdp = np.sqrt(var).reshape(4, n).max(0) * np.std(yv) * M.q / Z      # worst process and height per design
        widths.append(float(np.mean(2 * Z * sdp)))
        if k == kmax: break
        j = int(np.argmax(np.where(np.isin(np.arange(n), chosen), -1, sdp))); chosen.append(j)
        proc = 0.0      # a new design is run under the production insertion at both heights
        Xa = np.vstack([Xa, M.sc.transform(X_of([cands[j]], h_ref, proc)), M.sc.transform(X_of([cands[j]], h_loose, proc))])
    return widths
out['design_count'] = {}
for h_ref in (0.8, 1.0):
    w = curve(h_ref, 0.5); gain = [(w[k] - w[k + 1]) / w[0] for k in range(len(w) - 1)]; knee = next((k for k, g_ in enumerate(gain) if g_ < 0.02), len(gain))
    out['design_count'][f'reference_{h_ref}'] = dict(mean_interval_width_mm=[round(x, 4) for x in w], relative_gain_per_design=[round(g_, 3) for g_ in gain], designs_until_gain_below_2pct=knee)
    print('reference', h_ref, 'width', [round(x, 3) for x in w[:13]], 'knee', knee, flush=True)
json.dump(out, open(os.path.join(S.EVO, f'results/round2/settings_optimisation_{date}.json'), 'w'), indent=1, ensure_ascii=False)
