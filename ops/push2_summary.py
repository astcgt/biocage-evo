"""Summary of the carried push-out runs (h53 add2, windows w_push_post2; e09 files results/method/e09/<p>_push_post2.json) against the
one-wall runs (<p>_push_post.json). A run counts as RESOLVED when its force maximum is followed by at least 0.5 mm of further push
without a higher force (the peak is then the interface resistance, whether or not the run reached the full 3 mm); a run whose
largest force is at its last states is a LOWER BOUND only. usage: python ops/push2_summary.py -> results/method/e09/push2_summary.json"""
import os, json, glob
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(E, 'results/method/e09'); AFTER = 0.5
def read(f):
    if not os.path.exists(f): return None
    r = json.load(open(f)); s = r['states']; push = [-x['push_mm'] for x in s]; F = [x['force_push_dir_N'] for x in s]
    k = max(range(len(F)), key=lambda i: F[i]); fm = s[-1].get('cage_free_mean_mm'); fm = fm[0] if isinstance(fm, list) else fm
    return dict(peak_N=F[k], peak_at_mm=push[k], end_mm=push[-1], end_N=F[-1], resolved=bool(push[-1] - push[k] >= AFTER), full=bool(push[-1] >= 2.9),
                free_mean_end_mm=(-fm if fm is not None else None), plateau_N=(sum(F[i] for i in range(len(F)) if push[i] >= push[k] + AFTER) / max(1, sum(1 for i in range(len(F)) if push[i] >= push[k] + AFTER))) if push[-1] - push[k] >= AFTER else None)
rows = []
for f in sorted(glob.glob(os.path.join(D, 'p???_push_post2.json'))):
    p = os.path.basename(f)[:4]; rows.append(dict(design=p, carried=read(f), one_wall=read(os.path.join(D, p + '_push_post.json'))))
ok = [r for r in rows if r['carried']['resolved']]
pairs = [(r['design'], r['one_wall']['peak_N'], r['carried']['peak_N']) for r in ok if r['one_wall'] and r['one_wall']['resolved'] and r['one_wall']['full']]
out = dict(rule=f'resolved = at least {AFTER} mm of push after the force maximum', n=len(rows), n_resolved=len(ok), n_full_3mm=sum(r['carried']['full'] for r in rows),
           ranking=sorted([(r['design'], round(r['carried']['peak_N'], 1)) for r in ok], key=lambda x: -x[1]), lower_bound_only=[(r['design'], round(r['carried']['peak_N'], 1)) for r in rows if not r['carried']['resolved']],
           same_quantity_check=[dict(design=p, one_wall_N=round(a, 1), carried_N=round(b, 1), diff_pct=round(100 * (b - a) / a, 1)) for p, a, b in pairs], rows=rows)
json.dump(out, open(os.path.join(D, 'push2_summary.json'), 'w'), indent=1)
print(json.dumps({k: out[k] for k in ('n', 'n_resolved', 'n_full_3mm', 'ranking', 'lower_bound_only', 'same_quantity_check')}, indent=1))
