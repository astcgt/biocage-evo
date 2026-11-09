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
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026/human_study/al_v2/'
OUT = os.path.join(E, 'results/method/fric'); os.makedirs(OUT, exist_ok=True)
WIN = ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right')
ended = lambda log: os.path.exists(log) and any(k in open(log, errors='ignore').read()[-4000:] for k in ('N O R M A L', 'E R R O R'))
SETS = ('physio_fric', 'physio_fric2', 'physio_fric3', 'physio_fric5')   # 2026-11-09 PI decision 1: fric5 = fric3 windows recomputed from the same checkpoints with the stick-memory law; it SUPERSEDES fric3 per window (RANK)
RANK = {s: i for i, s in enumerate(SETS)}     # fric3: flexion + extension only, every passing design (PI 2026-11-03)             # 2026-11-03: second pass (physrotFr2_, amplitudes retargeted from physio_fric) added
wds = [w for s_ in SETS for w in sorted(glob.glob(R + s_ + '/p*/w_*')) if ended(w + '/case.log') and os.path.exists(w + '/case.xplt')]

def one(w):
    set_ = w.split('/al_v2/')[1].split('/')[0]
    tag = ('' if set_ == 'physio_fric' else set_ + '__') + os.path.basename(os.path.dirname(w)) + '__' + os.path.basename(w)[2:]; o = os.path.join(OUT, tag + '.e04.json')
    if not os.path.exists(o):
        r = subprocess.run(['timeout', '1500', sys.executable, os.path.join(E, 'methods/e04_dislocation.py'), w, o], capture_output=True, text=True)
        if r.returncode: open(o[:-5] + '.err', 'w').write(r.stderr[-3000:]); return None
    return o

with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3) as ex: files = [f for f in ex.map(one, wds) if f]
tied = json.load(open(os.path.join(E, 'results/method/split/best_by_design_merged.json')))
rows = []
for f in sorted(files):
    j = json.load(open(f)); parts = os.path.basename(f).split('__'); set_ = parts[0] if len(parts) == 3 else 'physio_fric'; dd = parts[-2]; p = dd[:4]
    for wn, r in j['windows'].items():
        if not isinstance(r, dict): rows.append(dict(set=set_, design=p, window=wn, note=r)); continue
        t = tied.get(p, {}).get(wn)
        u = r['cage_translation_tied_mm']; horiz = math.hypot(u[0], u[1])
        rows.append(dict(set=set_, design=p, case_dir=dd, window=wn, fric_reached=r['target_reached'], fric_M=r['M_at_target'], fric_translation_mm=horiz, fric_posterior_mm=-u[0],
                         window_check=r.get('window_check'),
                         fric_mu_from_tractions=r['mu_squeeze'], tied_mu_squeeze=t['mu_squeeze'] if t else None, tied_slip_bound_mm=t['one_face_slip_bound_mm'] if t else None,
                         tied_translation_mm=math.hypot(*t['cage_translation_tied_mm'][:2]) if t else None, tied_source=t['source'] if t else None))
# 2026-11-03: with real friction the extension / flexion moment saturates at ~ mu N x lever (~530-580 N mm at mu 0.35, 100 N),
# so the 1.5 N m target is never reached and the retargeted drive rotates C3 far past physiology (p060 extension 15.7 deg,
# 1.40 mm). Second evaluation point: the state where |C3 rotation| reaches the INTACT segment's rotation at 1.5 N m (h14 TH).
INTACT = dict(flexion=0.1009, extension=0.1286, LB_right=0.0713, LB_left=0.0717, AR_left=0.0905, AR_right=0.0907)
sys.path.insert(0, os.path.join(E, 'methods')); import e03_mu_req as e3, e04_dislocation as e4, numpy as np
def at_intact_rom(cd, wn):
    sch = json.load(open(os.path.join(cd, 'physio_schedule.json'))); w = sch['windows'][0]
    br = e3.target_bracket(cd, sch)[wn]; c3 = e4.read_log(os.path.join(cd, 'C3pot.txt')); cn = e4.read_log(os.path.join(cd, 'cage_nodes.txt')); c4 = e4.read_log(os.path.join(cd, 'C4_endplate_nodes.txt'))
    pts = []
    for t in br['valid_times']:
        th = float(np.linalg.norm(e4.nearest(c3, t)[0][2][3:6])); u = np.array(list(e4.nearest(cn, t)[0].values())).mean(0) - np.array(list(e4.nearest(c4, t)[0].values())).mean(0)
        pts.append((th, t, float(np.hypot(u[0], u[1])), float(-u[0])))
    R0 = INTACT[wn]; k = next((i for i, p in enumerate(pts) if p[0] >= R0), None)
    if k is None: return dict(rom_reached=False, rot_max_deg=np.degrees(pts[-1][0]) if pts else None, u_h_at_rom=pts[-1][2] if pts else None, post_at_rom=pts[-1][3] if pts else None)
    a, b = (pts[k - 1], pts[k]) if k > 0 else (pts[k], pts[k]); fr = (R0 - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0   # 2026-11-04 QA: tuple parenthesised (was a=pts[k-1], b=conditional -> TypeError -> rom_error when k == 0)
    return dict(rom_reached=True, rot_max_deg=np.degrees(pts[-1][0]), t_rom=a[1] + fr * (b[1] - a[1]), u_h_at_rom=a[2] + fr * (b[2] - a[2]), post_at_rom=a[3] + fr * (b[3] - a[3]))
for r in rows:
    if 'note' in r: continue
    cd = R + f"{r['set']}/{r['case_dir']}/w_{r['window']}"      # 2026-11-03 fix: the first dir starting with the id was the never-run build dir (p110 vs p110_gpu3) -> rom_error, vacuous pass
    try: r.update(at_intact_rom(cd, r['window']))
    except Exception as ex: r['rom_error'] = str(ex)[:120]
json.dump(rows, open(os.path.join(OUT, 'compare.json'), 'w'), indent=1)
# PI 2026-11-03 / 2026-11-05: friction-run dislocation rule per design - any window where the cage translation exceeds the limit
# (1 mm any direction, 0.5 mm posterior) at ITS evaluation point (the 1.5 N m state when the window transmits that moment,
# otherwise the intact-ROM state) is a FAIL; the latest set wins for the same window. Verdicts are PROVISIONAL (R03 superseded
# 2026-11-05; numerical convergence of the friction results NUM-16 / NUM-17 and the density reference (item 8) still open).
# 2026-11-04 (no pass by absence): a window counts when it reached an evaluation point (intact ROM or 1.5 N m) among the valid
# states (same convention as collect_split: a window is unusable only when it did not reach its evaluation point; a |M| that
# drops > 2 % after saturating under friction is reported, not discarded - before, p072 passed because its extension window,
# 0.55 mm posterior at ROM, was dropped as non-monotonic). A design PASSES only when flexion AND extension both reached an
# evaluation point and none exceeds the limit; a missing / unreached required window leaves it OPEN; designs whose
# frictional insertion run stopped before any window are OPEN with reason 'insertion not computable'.
LIM_ANY, LIM_POST = 1.0, 0.5
REQ = ('flexion', 'extension')                              # physio_fric3 windows (PI 2026-11-03)
best = {}
for r in rows:
    if 'note' in r: continue
    k = (r['design'], r['window'])
    if k not in best or RANK[r['set']] > RANK[best[k]['set']]: best[k] = r     # later set in SETS wins (fric5 over fric3), not string order
verd = {}
for (p, wn), r in sorted(best.items()):
    d = verd.setdefault(p, dict(verdict=None, reasons=[], windows={}, missing=[]))
    usable = bool(r.get('rom_reached') or r['fric_reached'])
    bad = []
    # PI 2026-11-05 (item 1, confirming the 04:30 wording): the evaluation point is the 1.5 N m state (in-vitro standard moment)
    # whenever the window transmits it; ONLY a window that never reaches 1.5 N m is judged at the intact-ROM state. Before
    # 2026-11-05 both points were judged when reached (every fail then came from the ROM point).
    ev_point = '1.5Nm' if r['fric_reached'] else ('ROM' if r.get('rom_reached') else None)
    if ev_point == '1.5Nm' and (r['fric_translation_mm'] > LIM_ANY or r['fric_posterior_mm'] > LIM_POST): bad.append(f"{wn}@1.5Nm u_h {r['fric_translation_mm']:.2f} post {r['fric_posterior_mm']:.2f}")
    if ev_point == 'ROM' and (r['u_h_at_rom'] > LIM_ANY or r['post_at_rom'] > LIM_POST): bad.append(f"{wn}@ROM u_h {r['u_h_at_rom']:.2f} post {r['post_at_rom']:.2f}")
    d['windows'][wn] = dict(set=r['set'], case_dir=r.get('case_dir'), usable=usable, eval_point=ev_point, monotonic=(r.get('window_check') or {}).get('monotonic'),
                            u_h_at_rom=r.get('u_h_at_rom'), post_at_rom=r.get('post_at_rom'), u_h_at_1p5Nm=r.get('fric_translation_mm'), post_at_1p5Nm=r.get('fric_posterior_mm'),
                            rot_max_deg=r.get('rot_max_deg'), bad=bad)
    d['reasons'] += bad
for p, d in verd.items():
    d['missing'] = [w for w in REQ if not d['windows'].get(w, {}).get('usable')]
    d['verdict'] = 'fail' if d['reasons'] else ('open' if d['missing'] else 'pass')
    if d['verdict'] == 'open':
        died = []                                   # 2026-11-04: a required window that STOPPED (ERROR) before an evaluation point is a computability gap
        for w in d['missing']:
            x = d['windows'].get(w) or next(iter(d['windows'].values()), None)     # a window that died at its first step has no row: use the design's run dir
            lg = R + f"{x['set']}/{x['case_dir']}/w_{w}/case.log" if x else None
            if x is not d['windows'].get(w): x = dict(x or {}, rot_max_deg=0.0)
            if lg and os.path.exists(lg) and 'E R R O R' in open(lg, errors='ignore').read()[-4000:]:
                died.append(f"{w} stopped at {x.get('rot_max_deg') or 0:.1f} deg (negative jacobians)")
        d['open_reason'] = ('; '.join(died) + '; ' if died else '') + 'window(s) ' + ', '.join(d['missing']) + ' did not reach the intact ROM or 1.5 N m (or missing)'
        if died: d['computability'] = True
# designs attempted in physio_fric3 whose insertion run stopped before the windows (largest final time over the run dirs)
import re
for cdir in sorted(glob.glob(R + 'physio_fric3/p*')):
    p = os.path.basename(cdir)[:4]; lg = cdir + '/case.log'
    if (p in verd and not verd[p].get('computability')) or not os.path.exists(lg): continue   # keep the run dir with the largest final time
    txt = open(lg, errors='ignore').read(); tt = re.findall(r'Time = ([0-9.eE+-]+)', txt); t_end = float(tt[-1]) if tt else 0.0
    if 'E R R O R' not in txt[-4000:] or t_end == 0.0: continue
    prev = verd.get(p, {}).get('t_end', -1)
    if t_end > prev:
        verd[p] = dict(verdict='open', reasons=[], windows={}, missing=list(REQ), t_end=t_end, case_dir=os.path.basename(cdir),
                       open_reason=(f'frictional insertion run stopped at t {t_end:.3f} in the static release step, before the follower load (platform problem, cluster 1 of DECISIONS 2026-11-03 22:30; not the C3 release impact)' if t_end < 3.0 else
                                    f'frictional insertion run stopped at t {t_end:.3f} in the first dynamic step after the C3 hold release (release impact, DECISIONS 2026-11-04 01:30)'), computability=True, stop_phase='static_release' if t_end < 3.0 else 'c3_release_impact')
verd['_meta'] = dict(set_precedence='per window the highest-ranked set in SETS wins: physio_fric5 (stick-memory law, PI 2026-11-09) supersedes physio_fric3 (production law, NUM-13 artefact); the insertion-stopped scan stays on physio_fric3', rule='PI 2026-11-03 04:30, confirmed 2026-11-05: evaluation point = 1.5 N m state when transmitted, else intact ROM; limits 1 mm any / 0.5 mm posterior; PI 2026-11-07 decision 1: this friction result is a CHECK of the mu_req (tied) slip-out verdict, not a gate (collect_split records friction_check); the 2026-11-03 gate-4 role is withdrawn',
                     provisional='verdicts provisional: physio_fric3 windows carry the FEBio stick-point artefact (NUM-13); PI 2026-11-09 decision 1 recomputes them as physio_fric5 (stick-memory law, same checkpoints) which supersedes fric3 per window here; NUM-17 (0.5 mm grey zone) and the density reference (DECISIONS 2026-11-05 item 8) still open', generated=__import__('time').strftime('%Y-%m-%d %H:%M'))
json.dump(verd, open(os.path.join(OUT, 'verdicts.json'), 'w'), indent=1)
import collections as _c; print('\nfriction verdicts (PI rule 2026-11-03 / 2026-11-05, no pass by absence 2026-11-04):', dict(_c.Counter(v['verdict'] for p, v in verd.items() if p != '_meta')))
for p, v in sorted((k, x) for k, x in verd.items() if not k.startswith('_')): print(f"  {p} {v['verdict']:5s} {'; '.join(v['reasons']) or v.get('open_reason', '')}")
print(f"{'set':12s} {'design':6s} {'window':9s} {'reached':7s} {'|M|':>6s} {'fric u_h':>9s} {'fric post':>9s} {'tied bound':>10s} {'tied mu':>8s}  window_check")
for r in rows:
    if 'note' in r: print(f"{r['set']:12s} {r['design']:6s} {r['window']:9s} {r['note']}"); continue
    wc = r.get('window_check') or {}
    print(f"{r['set']:12s} {r['design']:6s} {r['window']:9s} {str(r['fric_reached']):7s} {abs(r['fric_M'] or 0):6.0f} {r['fric_translation_mm']:9.3f} {r['fric_posterior_mm']:9.3f} "
          f"{(r['tied_slip_bound_mm'] if r['tied_slip_bound_mm'] is not None else float('nan')):10.3f} {(r['tied_mu_squeeze'] if r['tied_mu_squeeze'] is not None else float('nan')):8.3f}  "
          f"inv {wc.get('n_invalid')} dyn {wc.get('n_dyn')} mono {wc.get('monotonic')} complete {wc.get('complete')}  | at intact ROM: {'reached' if r.get('rom_reached') else 'NOT reached'} rot_max {r.get('rot_max_deg', float('nan')):.1f} deg u_h {r.get('u_h_at_rom', float('nan')):.3f} post {r.get('post_at_rom', float('nan')):.3f}")
ok = [r for r in rows if 'note' not in r and r['fric_reached'] and (r.get('window_check') or {}).get('monotonic', True)]
rom = [r for r in rows if 'note' not in r and r.get('rom_reached')]
if rom:
    w2 = max(rom, key=lambda r: r['u_h_at_rom']); print(f"{len(rom)} windows reached the intact ROM; largest cage translation there {w2['u_h_at_rom']:.3f} mm ({w2['set']} {w2['design']} {w2['window']}); all <= 1 mm: {all(r['u_h_at_rom'] <= 1.0 for r in rom)}; posterior <= 0.5 mm: {all(r['post_at_rom'] <= 0.5 for r in rom)}")
if ok:
    worst = max(ok, key=lambda r: r['fric_translation_mm'])
    print(f"\n{len(ok)} windows reached 1.5 N m with real friction; largest cage translation {worst['fric_translation_mm']:.3f} mm ({worst['design']} {worst['window']}); "
          f"all <= 1 mm: {all(r['fric_translation_mm'] <= 1.0 for r in ok)}; posterior <= 0.5 mm: {all(r['fric_posterior_mm'] <= 0.5 for r in ok)}")
