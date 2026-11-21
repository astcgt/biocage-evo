"""Replicate agreement under one window set (PI 2026-11-11 decision 4, platform layer: 「同一個設計能有穩定的模擬結果數值」).

Designs built from the identical deck (verdicts.json replicates.deck_sha256, from fric_compare) are one design; this script measures, per deck
group and window, how far the read-outs of the replicates lie apart in the given set(s) - the acceptance check of the route-E re-run
(physio_fric5r / physio_relGr): replicates should agree within the read-out noise (validation 2026-11-11..13: 0.0001-0.0002 mm).
Read-out = the evaluation-point translation of fric_compare (u_h / posterior at 1.5 N m when reached, else at the intact ROM).
usage: python ops/replicate_agreement.py [set ...]   (default physio_fric5r physio_relGr) -> results/method/fric/replicate_agreement.json
"""
import os, sys, json, math, collections
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(E, 'results/method/fric')
sets = tuple(sys.argv[1:]) or ('physio_fric5r', 'physio_relGr')
verd = json.load(open(os.path.join(OUT, 'verdicts.json'))); rows = json.load(open(os.path.join(OUT, 'compare.json')))
groups = collections.defaultdict(set)
for p, d in verd.items():
    if p.startswith('_') or not d.get('replicates'): continue
    groups[d['replicates']['deck_sha256']].update([p] + list(d['replicates']['designs']))
MU = lambda s: 0.3 if 'mu03' in s else 0.35      # pilot_mu03r / pilot_mu03Gr = the route-E recipe at mu 0.3 (PI 2026-11-20 decision 9)
def readout(r):
    if r.get('fric_reached'): return 'fric', r.get('fric_translation_mm'), r.get('fric_posterior_mm')
    if r.get('rom_reached'): return 'rom', r.get('u_h_at_rom'), r.get('post_at_rom')
    return None, None, None
byk = {(r['set'], r['design'], r['window']): r for r in rows if r['set'] in sets and 'note' not in r}
out = dict(sets=sets, groups=[], note=__doc__.split('\n')[0])
worst = 0.0; n_pairs = 0; n_disagree = 0
for h, ps in sorted(groups.items()):
    g = dict(deck_sha256=h, designs=sorted(ps), windows={})
    for w, mu in [(w, mu) for w in ('flexion', 'extension') for mu in sorted({MU(s) for s in sets}, reverse=True)]:
        vals = {}
        for p in sorted(ps):
            for s in sets:
                if MU(s) != mu: continue                # 2026-11-21: replicates are compared at ONE friction coefficient (a mu 0.3 window against a
                r = byk.get((s, p, w))                  # mu 0.35 window of its replicate is a mu effect, not a reproducibility defect)
                if r:
                    ep, uh, post = readout(r)
                    if ep: vals[p] = dict(set=s, eval_point=ep, u_h=uh, post=post)
        w = w if mu == 0.35 else f'{w}@mu{mu:g}'
        if len(vals) >= 2:
            eps = {v['eval_point'] for v in vals.values()}
            spread_u = max(v['u_h'] for v in vals.values()) - min(v['u_h'] for v in vals.values()) if len(eps) == 1 else None
            spread_p = max(v['post'] for v in vals.values()) - min(v['post'] for v in vals.values()) if len(eps) == 1 else None
            n_pairs += 1
            if spread_u is None or spread_u > 0.005: n_disagree += 1
            if spread_u is not None: worst = max(worst, spread_u)
            g['windows'][w] = dict(values=vals, same_eval_point=len(eps) == 1, spread_u_h_mm=spread_u, spread_post_mm=spread_p)
        else:
            g['windows'][w] = dict(values=vals, computed=len(vals), note='fewer than two replicates computed in these sets')
    out['groups'].append(g)
out['summary'] = dict(groups=len(groups), windows_with_two_or_more=n_pairs, windows_disagreeing_over_0p005_or_mixed_eval_point=n_disagree, worst_spread_u_h_mm=worst,
                      criterion='same evaluation point and |spread| <= 0.005 mm (read-out noise seen in the validation); larger spreads are platform [數值] items, not design results')
json.dump(out, open(os.path.join(OUT, 'replicate_agreement.json'), 'w'), indent=1)
print(f"replicate agreement over {sets}: {len(groups)} deck groups, {n_pairs} windows with >= 2 computed replicates, {n_disagree} disagree (> 0.005 mm or mixed evaluation point), worst spread {worst:.4f} mm")
for g in out['groups']:
    for w, x in g['windows'].items():
        if 'spread_u_h_mm' in x: print(f"  {g['deck_sha256'][:12]} {','.join(g['designs'])} {w}: {x['eval_point'] if 'eval_point' in x else ''}spread u_h {x['spread_u_h_mm']} post {x['spread_post_mm']} same_ep {x['same_eval_point']}")
