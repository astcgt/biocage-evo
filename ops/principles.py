"""Principle extraction and search for new design parameters (ROUND2_ARCHITECTURE.md part C, C6; PI 2026-11-18).

Declared BEFORE scoring (2026-11-18):
  Features tried = the 12 geometric descriptors (descriptors.NAMES), the 11 material x geometry composites
  (descriptors.PNAMES) and the 4 genes. No feature value is estimated by a language model; all are computed by code.
  Model variants (same Gaussian process as ops/surrogate_fit.py): D = genes + geometric descriptors (reference, no family
  label); P = genes + composites; DP = genes + descriptors + composites. Friction targets also take the insertion process,
  mu_req the screening pass type.
  Keep rule: the composites are adopted as estimator inputs for a target only if, against D, they lower the
  leave-one-FAMILY-out RMSE by >= 10 % and do not raise the leave-one-group-out RMSE by more than 5 %. Every variant and
  every feature is reported, kept or not. Leave-one-family-out has only 4-5 folds: weak evidence, no error bar.
  Rules: Spearman correlation of every feature with every target, pooled and WITHIN family (rank-centred per family), with
  a bootstrap interval over design groups (300 resamples); a rule is listed when |rho within family| >= 0.3 and its 90 %
  interval excludes 0. Correlation is not causation: rules are hypotheses for the next round.
Changed 2026-11-18 (PI decision: designs are compared at the SAME height; audit D-20261118-43): a rule is now listed only
  when it survives after the height d is removed - partial rank correlation within family controlling for d, |rho| >= 0.3
  and 90 % bootstrap interval excluding 0. The plain within-family correlation is still stored. Reason: softer soft
  material, hard / soft contrast and column compliance looked like rules, but they are themselves correlated with d in
  the archive (-0.43 / +0.43 / +0.62) and vanish once d is removed.
Outputs: results/principles/features_<date>.json, docs/DESIGN_PRINCIPLES.md (generated; do not edit by hand).
usage: python ops/principles.py [YYYY-MM-DD] [--rules-only]   (--rules-only reuses the model variants of the existing file)
usage: python ops/principles.py [YYYY-MM-DD]
"""
import os, sys, json, time, collections
import numpy as np
from scipy.stats import spearmanr, rankdata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surrogate_fit as S, descriptors as D
from propose_round import pass_extra

ZH = dict(hp_E_hard='硬料模數', hp_E_soft='軟料模數', hp_d='撐高量（支架比原本椎間盤空間高出多少）', hp_theta='混料門檻', void_frac='空間比例', mean_height_mm='平均高度', contact_area_mm2='接觸面積', hard_frac='硬料比例',
          face_hard_frac='接觸面硬料比例', core_hard_frac='核心硬料比例', post_hard_frac='後方硬料比例', ant_hard_frac='前方硬料比例', inner_hard_frac='靠窗側硬料比例', outer_hard_frac='外緣硬料比例',
          face_soft_thick_mm='接觸面軟層厚度', binary_material='硬軟分明（交錯列印）', log_k_axial='整體軸向剛度', log_k_face='接觸面附近剛度', log_col_compliance='柱體順應性（越大越軟）',
          log_contrast='硬軟模數對比', log_post_ant_stiffness='後方對前方剛度比', defl_100N_over_d='100 牛頓下高度損失佔撐高量的比例', soft_volume_frac='軟料體積比例', log_E_face='接觸面模數',
          log_k_bend='抗彎剛度', stiff_centre_x_mm='剛度中心的前後位置', face_strain_100N='100 牛頓下接觸面應變')
FZH = dict(radial_interleave='徑向交錯', radial_mix='徑向混合（已排除的類別）', axial_interleave='軸向交錯', axial_mix='軸向混合', both_interleave='雙向交錯', both_mix='雙向混合')
TZH = dict(post_ext='後伸的後方位移', uh_flex='屈曲的位移', mu_req='所需摩擦係數')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]; rules_only = '--rules-only' in sys.argv
    date = args[0] if args else time.strftime('%Y-%m-%d'); old = json.load(open(os.path.join(S.EVO, f'results/principles/features_{date}.json'))) if rules_only else None
    rows, verd, _ = S.load(); G = S.groups(rows, verd); byd = {r['design']: r for r in rows}
    for r in rows:
        r['_phys'] = D.physics_features(os.path.join(S.MESH, r['mesh']), float(r['hp_E_hard']), float(r['hp_E_soft']), float(r['hp_theta']), float(r['hp_d']))
    feat = lambda r: dict({g: (np.log(float(r[g])) if 'E_' in g else float(r[g])) for g in S.GENES}, **r['_desc'], **r['_phys'])
    names = S.GENES + D.NAMES + D.PNAMES; sets = dict(D=S.GENES + D.NAMES, P=S.GENES + D.PNAMES, DP=names)
    targets = {}
    for wn, ev, name in (('extension', 'ROM', 'post_ext'), ('flexion', '1.5Nm', 'uh_flex')):
        sel, yv, ex, seen = [], [], [], set()
        for p, v in sorted(verd.items()):
            w = v['windows'].get(wn)
            if p not in byd or not w or not w.get('usable') or w.get('eval_point') != ev: continue
            val = w['u_h_at_1p5Nm'] if wn == 'flexion' else w['post_at_rom']; key = (w.get('set'), w.get('case_dir'))
            if val is None or key in seen: continue
            seen.add(key); sel.append(byd[p]); yv.append(val); ex.append([float(w['set'] in S.PROC_G)])
        targets[name] = (sel, np.array(yv, float), ex, False)
    sel = [r for r in rows if r['mu_req_max'] and r['lower_bound'] != 'True']
    targets['mu_req'] = (sel, np.array([float(r['mu_req_max']) for r in sel]), [list(pass_extra(r['source'])) for r in sel], True)
    out = dict(date=date, declared=__doc__.split('Outputs')[0].strip(), features=names, variants={}, correlations={}, kept={})
    rng = np.random.default_rng(0)
    for name, (sel, y, ex, log) in targets.items():
        grp = np.array([G[r['design']] for r in sel]); fam = np.array([r['family'] for r in sel]); F = [feat(r) for r in sel]; res = {}
        for vn, cols in ({} if rules_only else sets).items():
            X = [[f[c] for c in cols] + e for f, e in zip(F, ex)]
            for by in ('group', 'family'):
                mu, sd, base, spread = S.validate(X, y, grp, fam, log, by); rep, *_ = S.report(y, mu, sd, base, spread, grp, fam, log, by)
                res[f'{vn}/leave-one-{by}-out'] = dict(rmse=rep['rmse'], mae=rep['mae'], coverage=rep['empirical_coverage'], skill=rep['skill'], rmse_baseline=rep['rmse_baseline'])
                print(name, vn, by, res[f'{vn}/leave-one-{by}-out'], flush=True)
        if rules_only: res = old['variants'][name]
        out['variants'][name] = res
        gain = lambda v: 1 - res[f'{v}/leave-one-family-out']['rmse'] / res['D/leave-one-family-out']['rmse']
        cost = lambda v: res[f'{v}/leave-one-group-out']['rmse'] / res['D/leave-one-group-out']['rmse'] - 1
        out['kept'][name] = {v: dict(family_out_rmse_gain=round(gain(v), 3), group_out_rmse_change=round(cost(v), 3), adopted=bool(gain(v) >= 0.10 and cost(v) <= 0.05)) for v in ('P', 'DP')}
        # correlations: pooled and within family, bootstrap over groups
        ug = sorted(set(grp)); cor = {}
        def within(v): 
            o = np.zeros(len(v))
            for f in set(fam): m = fam == f; o[m] = rankdata(v[m]) - rankdata(v[m]).mean() if m.sum() > 2 else 0.0
            return o
        yw = within(y); dw = within(np.array([f['hp_d'] for f in F]))
        def partial(a, b, idx=None):      # correlation of a and b after removing the height (all rank-centred within family)
            a_, b_, d_ = (a, b, dw) if idx is None else (a[idx], b[idx], dw[idx])
            if np.std(d_) == 0: return float('nan')
            ra = a_ - np.polyval(np.polyfit(d_, a_, 1), d_); rb = b_ - np.polyval(np.polyfit(d_, b_, 1), d_)
            return float(np.corrcoef(ra, rb)[0, 1]) if np.std(ra) > 1e-9 and np.std(rb) > 1e-9 else float('nan')
        for c in names:
            v = np.array([f[c] for f in F])
            if np.std(v) < 1e-12: cor[c] = dict(note='constant in this data'); continue
            vw = within(v); r_p = spearmanr(v, y)[0]; r_w = float(np.corrcoef(vw, yw)[0, 1]) if np.std(vw) > 0 else float('nan'); bs = []; bp = []
            r_d = float(np.corrcoef(vw, dw)[0, 1]) if np.std(vw) > 0 else float('nan'); r_part = float('nan') if c == 'hp_d' else partial(vw, yw)
            for _ in range(300):
                pick = rng.choice(len(ug), len(ug)); idx = np.concatenate([np.where(grp == ug[k])[0] for k in pick])
                if np.std(vw[idx]) > 0 and np.std(yw[idx]) > 0: bs.append(np.corrcoef(vw[idx], yw[idx])[0, 1])
                if c != 'hp_d':
                    pr = partial(vw, yw, idx)
                    if not np.isnan(pr): bp.append(pr)
            lo, hi = (np.percentile(bs, [5, 95]) if bs else (np.nan, np.nan)); plo, phi_ = (np.percentile(bp, [5, 95]) if bp else (np.nan, np.nan))
            cor[c] = dict(rho_pooled=round(float(r_p), 2), rho_within_family=round(r_w, 2), ci90=[round(float(lo), 2), round(float(hi), 2)], rho_with_height=round(r_d, 2),
                          rho_at_same_height=None if np.isnan(r_part) else round(r_part, 2), ci90_at_same_height=None if np.isnan(r_part) else [round(float(plo), 2), round(float(phi_), 2)],
                          rule=bool(not np.isnan(r_part) and abs(r_part) >= 0.3 and (plo > 0 or phi_ < 0)),
                          by_family_at_same_height={f_: round(partial(vw, yw, np.where(fam == f_)[0]), 2) for f_ in sorted(set(fam)) if (fam == f_).sum() >= 8 and c != 'hp_d'})
        out['correlations'][name] = cor; out.setdefault('n', {})[name] = dict(rows=len(y), groups=len(ug), families={f: int((fam == f).sum()) for f in sorted(set(fam))})
    os.makedirs(os.path.join(S.EVO, 'results/principles'), exist_ok=True)
    json.dump(out, open(os.path.join(S.EVO, f'results/principles/features_{date}.json'), 'w'), indent=1, ensure_ascii=False)
    # ---- generated plain-language page
    L = [f'# 設計原則（自動產生 {date}；不要手改）', '', '由 `ops/principles.py` 從模擬結果算出。**這些是相關性，不是因果**：每一條都是下一輪要用模擬去檢驗的假設。', '',
         '**撐高量**＝支架比原本椎間盤空間高出多少。它是既有設計裡影響最大的因素（越高，被周圍組織夾得越緊）。PI 2026-11-18 決定：設計要在**同一撐高量**下比較，',
         '所以下表只列「把撐高量的影響扣掉之後」仍然成立的規則。門檻（等級相關絕對值 ≥ 0.3、90 % 區間不跨 0）是事前宣告的；「扣掉撐高量」這一步是看過第一次結果後才加的修正（稽核 D-20261118-43）。',
         '**合併的數字可能只來自部分家族**，請看「各家族分開看」一欄：一條規則在某個家族接近 0，就表示它在那個家族不成立。', '']
    for name, cor in out['correlations'].items():
        n = out['n'][name]; rules = sorted([(c, d) for c, d in cor.items() if d.get('rule')], key=lambda a: -abs(a[1]['rho_at_same_height']))
        L += [f'## {TZH[name]}（{n["rows"]} 筆、{n["groups"]} 組設計）', '', f"- 撐高量本身：家族內相關 {cor['hp_d']['rho_within_family']:+.2f}（越高，{TZH[name]}越小）。", '',
              '| 特徵 | 同一撐高量下的相關（各家族合併） | 90 % 區間 | 各家族分開看 | 白話 |', '|---|---|---|---|---|']
        for c, d in rules:
            bf = '、'.join(f'{FZH.get(k, k)} {v:+.2f}' for k, v in d['by_family_at_same_height'].items() if v == v)
            L.append(f"| {ZH.get(c, c)} | {d['rho_at_same_height']:+.2f} | {d['ci90_at_same_height'][0]:+.2f} ～ {d['ci90_at_same_height'][1]:+.2f} | {bf} | 同一撐高量下，{ZH.get(c, c)}越大，{TZH[name]}越{'大' if d['rho_at_same_height'] > 0 else '小'} |")
        if not rules: L.append('| （扣掉撐高量後，沒有特徵達到門檻） | | | | |')
        gone = [ZH.get(c, c) for c, d in cor.items() if not d.get('rule') and d.get('rho_at_same_height') is not None and abs(d.get('rho_within_family') or 0) >= 0.3]
        L += ['', '原本看起來有關、扣掉撐高量後不成立的特徵：' + ('、'.join(gone) if gone else '無') + '。', '']
    L += ['## 新特徵能不能幫估算器預測「沒看過的家族」', '', '事前宣告的留用規則：整個家族留出時誤差至少降 10 %，且一般驗證誤差不升超過 5 %。只有 4–5 個家族可留出，證據偏弱。', '',
          '| 預測目標 | 輸入組合 | 留出家族的誤差變化 | 一般驗證的誤差變化 | 是否採用 |', '|---|---|---|---|---|']
    for name, k in out['kept'].items():
        for v, d in k.items():
            L.append(f"| {TZH[name]} | {'基因＋材料幾何複合特徵' if v == 'P' else '基因＋幾何描述＋複合特徵'} | {-100 * d['family_out_rmse_gain']:+.0f} % | {100 * d['group_out_rmse_change']:+.0f} % | {'採用' if d['adopted'] else '不採用'} |")
    L += ['', f'來源：`results/principles/features_{date}.json`（含每一個試過的特徵與組合）。', '']
    open(os.path.join(S.EVO, 'docs/DESIGN_PRINCIPLES.md'), 'w').write('\n'.join(L) + '\n')
    print('kept', json.dumps(out['kept']))


if __name__ == '__main__':
    main()
