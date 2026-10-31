"""Real-friction check of the tied-interface shortcut (gate 4, 2026-10-31).

For every ended window of al_v2/physio_fric (contact_type elastic, mu 0.35, non-symmetric stiffness, slow dynamic, independent
windows) run e04 (its cage_translation_tied_mm is, on a frictional run, the actual rigid-body translation of the cage relative
to C4 at the evaluated state; mu_squeeze is still computed from the face tractions) and compare with the tied result of the
same design and window (results/method/split/best_by_design_merged.json). Prints a table and writes
results/method/fric/compare.json. Dislocation criterion (PI): rigid-body translation <= 1 mm any direction, <= 0.5 mm posterior.
usage: python ops/fric_compare.py [workers]
"""
import os, sys, glob, json, subprocess, math
from concurrent.futures import ThreadPoolExecutor

E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1/human_study/al_v2/'
OUT = os.path.join(E, 'results/method/fric'); os.makedirs(OUT, exist_ok=True)
WIN = ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right')
ended = lambda log: os.path.exists(log) and any(k in open(log, errors='ignore').read()[-4000:] for k in ('N O R M A L', 'E R R O R'))
wds = [w for w in sorted(glob.glob(R + 'physio_fric/p*/w_*')) if ended(w + '/case.log') and os.path.exists(w + '/case.xplt')]

def one(w):
    tag = os.path.basename(os.path.dirname(w)) + '__' + os.path.basename(w)[2:]; o = os.path.join(OUT, tag + '.e04.json')
    if not os.path.exists(o):
        r = subprocess.run(['timeout', '1500', sys.executable, os.path.join(E, 'methods/e04_dislocation.py'), w, o], capture_output=True, text=True)
        if r.returncode: open(o[:-5] + '.err', 'w').write(r.stderr[-3000:]); return None
    return o

with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3) as ex: files = [f for f in ex.map(one, wds) if f]
tied = json.load(open(os.path.join(E, 'results/method/split/best_by_design_merged.json')))
rows = []
for f in sorted(files):
    j = json.load(open(f)); dd = os.path.basename(f).split('__')[0]; p = dd[:4]
    for wn, r in j['windows'].items():
        if not isinstance(r, dict): rows.append(dict(design=p, window=wn, note=r)); continue
        t = tied.get(p, {}).get(wn)
        u = r['cage_translation_tied_mm']; horiz = math.hypot(u[0], u[1])
        rows.append(dict(design=p, window=wn, fric_reached=r['target_reached'], fric_M=r['M_at_target'], fric_translation_mm=horiz, fric_posterior_mm=-u[0],
                         fric_mu_from_tractions=r['mu_squeeze'], tied_mu_squeeze=t['mu_squeeze'] if t else None, tied_slip_bound_mm=t['one_face_slip_bound_mm'] if t else None,
                         tied_translation_mm=math.hypot(*t['cage_translation_tied_mm'][:2]) if t else None, tied_source=t['source'] if t else None))
json.dump(rows, open(os.path.join(OUT, 'compare.json'), 'w'), indent=1)
print(f"{'design':6s} {'window':9s} {'reached':7s} {'|M|':>6s} {'fric u_h':>9s} {'fric post':>9s} {'tied bound':>10s} {'tied mu':>8s}")
for r in rows:
    if 'note' in r: print(f"{r['design']:6s} {r['window']:9s} {r['note']}"); continue
    print(f"{r['design']:6s} {r['window']:9s} {str(r['fric_reached']):7s} {abs(r['fric_M'] or 0):6.0f} {r['fric_translation_mm']:9.3f} {r['fric_posterior_mm']:9.3f} "
          f"{(r['tied_slip_bound_mm'] if r['tied_slip_bound_mm'] is not None else float('nan')):10.3f} {(r['tied_mu_squeeze'] if r['tied_mu_squeeze'] is not None else float('nan')):8.3f}")
ok = [r for r in rows if 'note' not in r and r['fric_reached']]
if ok:
    worst = max(ok, key=lambda r: r['fric_translation_mm'])
    print(f"\n{len(ok)} windows reached 1.5 N m with real friction; largest cage translation {worst['fric_translation_mm']:.3f} mm ({worst['design']} {worst['window']}); "
          f"all <= 1 mm: {all(r['fric_translation_mm'] <= 1.0 for r in ok)}; posterior <= 0.5 mm: {all(r['fric_posterior_mm'] <= 0.5 for r in ok)}")
