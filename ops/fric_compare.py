"""Real-friction check of the tied-interface shortcut (gate 4, 2026-10-31).

For every ended window of al_v2/physio_fric (contact_type elastic, mu 0.35, non-symmetric stiffness, slow dynamic, independent
windows) run e04 (its cage_translation_tied_mm is, on a frictional run, the actual rigid-body translation of the cage relative
to C4 at the evaluated state; mu_squeeze is still computed from the face tractions) and compare with the tied result of the
same design and window (results/method/split/best_by_design_merged.json). Prints a table and writes
results/method/fric/compare.json. Dislocation criterion (PI): rigid-body translation <= 1 mm any direction, <= 0.5 mm posterior.
usage: python ops/fric_compare.py [workers]
"""
import os, sys, glob, json, subprocess, math, re
from concurrent.futures import ThreadPoolExecutor

E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026/human_study/al_v2/'
OUT = os.path.join(E, 'results/method/fric'); os.makedirs(OUT, exist_ok=True)
WIN = ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right')
ended = lambda log: os.path.exists(log) and any(k in open(log, errors='ignore').read()[-4000:] for k in ('N O R M A L', 'E R R O R'))
SETS = ('physio_fric', 'physio_fric2', 'physio_fric3', 'physio_fric5', 'physio_relG_pl', 'physio_relG', 'physio_fric5r', 'physio_relGr')   # physio_relG (PI 2026-11-10, issue 2 option a): process-G insertion of the designs whose production insertion stopped; different designs, so it supersedes nothing in practice
PROCESS = {s: 'production (release at t 3.0 with the static->dynamic switch; production friction law in the insertion)' for s in ('physio_fric', 'physio_fric2', 'physio_fric3', 'physio_fric5')}
PROCESS['physio_relG'] = 'G (all steps dynamic, stored moment ramped to zero under the follower load, stick-memory law in the insertion; PI 2026-11-10 option a)'
WINDOW_LAW = {'physio_fric': 'production', 'physio_fric2': 'production', 'physio_fric3': 'production', 'physio_fric5': 'stick memory (patch 6+7)', 'physio_relG': 'stick memory (patch 6+7)'}
# physio_relG_pl (DECISIONS 2026-11-10 14:45, built by h51): the physio_relG windows restarted from the SAME process-G t 3.5 checkpoint with the
# production friction law (BIOCAGE_STICK_MEMORY=0). Fallback SOURCE only: it never wins a (design, window) slot; an unusable physio_relG window
# that did not fold in the first increments takes its read-out + margin, flagged (PI 2026-11-10 item 1 extended to process G).
PROCESS['physio_relG_pl'] = PROCESS['physio_relG']; WINDOW_LAW['physio_relG_pl'] = 'production'
# physio_fric5r / physio_relGr (PI 2026-11-11 decision 1a, route E): the physio_fric5 / physio_relG windows restarted from the SAME checkpoints with the
# window drive as a RELATIVE prescribed rotation of the C3 pot (h30 window_drive_mode rigid_relative; no rigid joint, no activation snap, Rx/Rz held
# relative 0); stick-memory law unchanged. Highest rank: they supersede the joint-driven windows per (design, window). Drive provenance in WINDOW_DRIVE.
PROCESS['physio_fric5r'] = PROCESS['physio_fric5']; PROCESS['physio_relGr'] = PROCESS['physio_relG']
WINDOW_LAW['physio_fric5r'] = WINDOW_LAW['physio_relGr'] = 'stick memory (patch 6+7)'
WINDOW_DRIVE = {s: 'absolute rigid joint (Lagrange multipliers; snaps C3 to its t=0 orientation at activation: insertion tilt measured over the 70 checkpoints - production 0.08-1.53 deg, median 0.21; process G 0.46-1.31 deg, median 0.87)' for s in SETS}
WINDOW_DRIVE['physio_fric5r'] = WINDOW_DRIVE['physio_relGr'] = 'relative prescribed rotation of the C3 pot (route E, PI 2026-11-11 1a; drive moment = rigid-body reaction)'
STICK_SETS = ('physio_fric5', 'physio_relG', 'physio_fric5r', 'physio_relGr')   # stick-memory-law sets (joint drive and route-E drive)
FALLBACK_SRC = {'physio_fric5': 'physio_fric3', 'physio_relG': 'physio_relG_pl', 'physio_fric5r': 'physio_fric3', 'physio_relGr': 'physio_relG_pl'}   # stick-law set -> production-law set of the same checkpoints (route-E sets: the production-law windows are joint-driven; the margin was measured on joint pairs - approximation, flagged in margin_basis)
FALLBACK_ONLY = ('physio_relG_pl',)                                                 # sets that exist only as a fallback source
LOCK_T, LOCK_NJ = 3.52, 100   # first-increment pattern (last converged time < 3.52, > 100 negative-Jacobian warnings). 2026-11-11: noted only (first_increment_pattern), no veto - the identical decks p050 / p068 / p084 / p127 differ in this outcome (run-to-run variability, not a design property)
REPL_NOISE = 0.02   # PI 2026-11-17: replicate read-outs within this band are one result on the limit -> grey
GREY_LO, GREY_HI = 0.45, 0.55   # PI 2026-11-10: posterior translation in [0.45, 0.55] mm at the evaluation point is GREY - analysis only, never a final design   # 2026-11-09 PI decision 1: fric5 = fric3 windows recomputed from the same checkpoints with the stick-memory law; it SUPERSEDES fric3 per window (RANK)
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
        if not isinstance(r, dict): rows.append(dict(set=set_, design=p, case_dir=dd, window=wn, note=r, insertion_process=PROCESS.get(set_), window_law=WINDOW_LAW.get(set_), window_drive=WINDOW_DRIVE.get(set_))); continue   # case_dir kept (2026-11-10 17:xx): the soft-face-locking scan reads this window's log
        t = tied.get(p, {}).get(wn)
        u = r['cage_translation_tied_mm']; horiz = math.hypot(u[0], u[1])
        rows.append(dict(set=set_, design=p, case_dir=dd, window=wn, insertion_process=PROCESS.get(set_), window_law=WINDOW_LAW.get(set_), window_drive=WINDOW_DRIVE.get(set_), fric_reached=r['target_reached'], fric_M=r['M_at_target'], fric_translation_mm=horiz, fric_posterior_mm=-u[0],
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
    # QA audit 2026-11-10 不符 #1: a window of a higher-ranked set that produced NO e04 result (note 'missing': the run died before any valid
    # state) must still occupy its (design, window) slot, otherwise the superseded production-law row silently wins (p036 / p148 flexion
    # passed on physio_fric3 values without flag or margin). The placeholder is unusable; the PI 2026-11-10 fallback (below) may replace it.
    if 'note' in r: r = dict(r, fric_reached=False, rom_reached=False, fric_M=None, fric_translation_mm=None, fric_posterior_mm=None, u_h_at_rom=None, post_at_rom=None, placeholder=True)
    k = (r['design'], r['window'])
    if r['set'] in FALLBACK_ONLY: continue                                        # fallback source only (below)
    # 2026-11-13 (audit 不符 D-20261113-6): per (design, window) the STICK-LAW rows (fric5 / relG / fric5r / relGr) always beat the production-law rows
    # (so the fallback + margin logic below still governs when the stick-law window stopped); among stick-law rows one that REACHED an evaluation point
    # beats one that did not, then the later set in SETS wins (route E over the joint drive) - a route-E window that failed keeps the joint-driven row.
    _usable = bool(r.get('fric_reached') or r.get('rom_reached')); _key = (r['set'] in STICK_SETS, _usable if r['set'] in STICK_SETS else False, RANK[r['set']])
    if k not in best: best[k] = r; _bk = {}
    else:
        b = best[k]; _bkey = (b['set'] in STICK_SETS, bool(b.get('fric_reached') or b.get('rom_reached')) if b['set'] in STICK_SETS else False, RANK[b['set']])
        if _key > _bkey: best[k] = r
# PI 2026-11-10 item 1 (fallback, thin cages): when the stick-memory-law window (physio_fric5) stopped before its evaluation point and the
# production-law window (physio_fric3) of the same design and window reached one, the verdict uses the production-law read-out PLUS the
# p90 of the law-change shift (fric3_to_fric5_shift.json abs_p90, 0.043 mm) on every translation, flagged 'fallback' with source and margin.
_shift = os.path.join(OUT, 'fric3_to_fric5_shift.json'); _rshift = os.path.join(OUT, 'relG_law_shift.json')
_m35 = round(json.load(open(_shift)).get('abs_p90', 0.043), 4) if os.path.exists(_shift) else 0.043
_rs = json.load(open(_rshift)) if os.path.exists(_rshift) else {}
# 2026-11-11: the margin is per fallback source. Production-inserted checkpoints (fric5 <- fric3): abs_p90 of the 74 fric3/fric5 pairs (0.0431).
# Process-G checkpoints (relG <- relG_pl): the control pairs (p039, p052 both windows; p061 has none, its production-law restarts died early)
# shift by up to 0.0581 > 0.0431, so the larger of the two is used: max(abs_p90 fric3->fric5, abs_max relG pairs). PI confirmed 2026-11-11 (「3確認」).
FALLBACK_MARGIN = {'physio_fric3': _m35, 'physio_relG_pl': round(max(_m35, _rs.get('abs_max') or 0.0), 4)}
MARGIN_BASIS = {'physio_fric3': 'abs_p90 of fric3_to_fric5_shift.json (74 production-inserted checkpoint pairs)',
                'physio_relG_pl': f"max(abs_p90 fric3_to_fric5_shift.json {_m35}, abs_max relG_law_shift.json {_rs.get('abs_max')}) over n {_rs.get('n')} process-G control pairs (ops/law_shift.py)"}
byset = {(r['set'], r['design'], r['window']): r for r in rows if 'note' not in r}
allrows = {(r['set'], r['design'], r['window']): r for r in rows}                        # placeholders included (a window that died before any valid state)
def log_tail(set_, case_dir, wn):
    """(ended with E R R O R, last converged time, negative-Jacobian warnings) of a window log; (None, None, 0) when there is no log"""
    lg = R + f"{set_}/{case_dir}/w_{wn}/case.log"
    if not case_dir or not os.path.exists(lg): return None, None, 0
    t = open(lg, errors='ignore').read(); tt = re.findall(r'Nonlinear solution status: time= *([0-9.]+)', t)
    return 'E R R O R' in t[-4000:], (float(tt[-1]) if tt else None), t.count('Negative jacobian')
def folded_early(r):
    """the stick-law window folded in the first increments (pattern note only since 2026-11-11; it used to veto the fallback)"""
    err, tl, nj = log_tail(r['set'], r.get('case_dir'), r['window'])
    return bool(err) and tl is not None and tl < LOCK_T and nj > LOCK_NJ
for k, r in list(best.items()):
    if r.get('rom_reached') or r['fric_reached'] or r['set'] not in FALLBACK_SRC: continue   # 2026-11-11: the folded_early veto is withdrawn (see LOCK_T note)
    src = FALLBACK_SRC[r['set']]; f3 = byset.get((src,) + k)
    if f3 and (f3.get('rom_reached') or f3['fric_reached']):
        fb = dict(f3)
        for kk in ('fric_translation_mm', 'fric_posterior_mm', 'u_h_at_rom', 'post_at_rom'):
            if fb.get(kk) is not None: fb[kk] = fb[kk] + FALLBACK_MARGIN[src]
        fb['window_law'] = (fb.get('window_law') or 'production') + ' (fallback)'
        fb['fallback'] = dict(source=f'{src} (production law, same checkpoint)', margin_mm=FALLBACK_MARGIN[src], rule='PI 2026-11-10 item 1: production-law read-out + law-change shift margin, flagged',
                              margin_basis=MARGIN_BASIS[src] + ('; applied to a route-E (relative-drive) stick-law window although the margin was measured on joint-driven pairs - approximation (audit 2026-11-13 S5)' if r['set'] in ('physio_fric5r', 'physio_relGr') else ''), first_increment_pattern=folded_early(r),
                              superseded=dict(set=r['set'], case_dir=r.get('case_dir'), t_last=log_tail(r['set'], r.get('case_dir'), r['window'])[1]))
        best[k] = fb
verd = {}
for (p, wn), r in sorted(best.items()):
    d = verd.setdefault(p, dict(verdict=None, reasons=[], windows={}, missing=[]))
    usable = bool(r.get('rom_reached') or r['fric_reached'])
    bad = []
    # PI 2026-11-05 (item 1, confirming the 04:30 wording): the evaluation point is the 1.5 N m state (in-vitro standard moment)
    # whenever the window transmits it; ONLY a window that never reaches 1.5 N m is judged at the intact-ROM state. Before
    # 2026-11-05 both points were judged when reached (every fail then came from the ROM point).
    ev_point = '1.5Nm' if r['fric_reached'] else ('ROM' if r.get('rom_reached') else None)
    # PI 2026-11-10 grey zone: posterior in [GREY_LO, GREY_HI] is grey (analysis only, not a final design), posterior > GREY_HI or any-direction
    # translation > LIM_ANY is a fail; the strict 0.5 mm line (LIM_POST) is kept as the nominal limit inside the grey band.
    grey = []
    uh, post = (r['fric_translation_mm'], r['fric_posterior_mm']) if ev_point == '1.5Nm' else ((r['u_h_at_rom'], r['post_at_rom']) if ev_point == 'ROM' else (None, None))
    if ev_point and (uh > LIM_ANY or post > GREY_HI): bad.append(f'{wn}@{ev_point} u_h {uh:.2f} post {post:.2f}')
    elif ev_point and GREY_LO <= post <= GREY_HI: grey.append(f'{wn}@{ev_point} post {post:.3f} in grey zone [{GREY_LO}, {GREY_HI}]')
    d['windows'][wn] = dict(set=r['set'], case_dir=r.get('case_dir'), window_drive=r.get('window_drive'), grey_sub=(None if post is None else ('grey-low' if GREY_LO <= post < 0.50 else 'grey-high' if 0.50 <= post <= GREY_HI else None)), usable=usable, eval_point=ev_point, monotonic=(r.get('window_check') or {}).get('monotonic'),
                            u_h_at_rom=r.get('u_h_at_rom'), post_at_rom=r.get('post_at_rom'), u_h_at_1p5Nm=r.get('fric_translation_mm'), post_at_1p5Nm=r.get('fric_posterior_mm'),
                            rot_max_deg=r.get('rot_max_deg'), bad=bad, grey=grey, fallback=r.get('fallback'), insertion_process=r.get('insertion_process'), window_law=r.get('window_law'))
    d['reasons'] += bad; d.setdefault('grey', []).extend(grey)
for p, d in verd.items():
    d['missing'] = [w for w in REQ if not d['windows'].get(w, {}).get('usable')]
    d['verdict'] = 'fail' if d['reasons'] else ('open' if d['missing'] else ('grey' if d.get('grey') else 'pass'))
    if d['verdict'] == 'grey': d['grey_note'] = '灰區：僅供分析，不得作為 final design (PI 2026-11-10; posterior 0.45-0.55 mm)'
    procs = {w.get('insertion_process') for wn_, w in d['windows'].items() if w.get('insertion_process') and wn_ in REQ}; d['insertion_process'] = procs.pop() if len(procs) == 1 else (sorted(procs) if procs else None)   # 2026-11-17 audit S10: only the required windows define the design's process (old LB/AR rows of physio_fric2 made p109 a list)
    if d['verdict'] == 'open':
        died = []                                   # 2026-11-04: a required window that STOPPED (ERROR) before an evaluation point is a computability gap
        for w in d['missing']:
            x = d['windows'].get(w) or next(iter(d['windows'].values()), None)     # a window that died at its first step has no row: use the design's run dir
            lg = R + f"{x['set']}/{x['case_dir']}/w_{w}/case.log" if x else None
            if x is not d['windows'].get(w): x = dict(x or {}, rot_max_deg=0.0)
            if lg and os.path.exists(lg) and 'E R R O R' in open(lg, errors='ignore').read()[-4000:]:
                died.append(f"{w} stopped at {x.get('rot_max_deg') or 0:.1f} deg (negative jacobians)")
                # PI 2026-11-10 item 2: a window that folds in the first increments (last time < LOCK_T, > LOCK_NJ negative-Jacobian warnings) under the
                # reference law - and, where tested, under the production law too (p068 control) - is the soft cage face locking under the
                # 100 N follower load: not computable in any friction law, the design is outside the physio-window envelope. 2026-11-10 17:xx: a window
                # whose production-law restart of the same checkpoint (fallback source) ALSO stopped with an error before an evaluation point is the
                # same class ('both laws'), whatever the time it reached.
                _err, _tl, _nj = log_tail(x['set'], x.get('case_dir'), w); early = _tl is not None and _tl < LOCK_T and _nj > LOCK_NJ
                _src = FALLBACK_SRC.get(x['set']); _f = allrows.get((_src, p, w)) if _src else None
                _ferr, _ftl, _fnj = log_tail(_src, _f.get('case_dir'), w) if _f is not None else (None, None, 0)
                both = _f is not None and not (_f.get('rom_reached') or _f.get('fric_reached')) and bool(_ferr)
                # 2026-11-11: only 'both laws' classes a window as not computable (key soft_face_locking kept for h37 R17 / h51 / QA_SPEC compatibility;
                # the material hypothesis is not asserted any more - the identical decks p050 / p068 / p084 / p127 differ in their first-increment
                # outcome). A first-increment stick-law failure without a production-law attempt stays a plain computability gap (open), noted only.
                if early: d.setdefault('first_increment_pattern', []).append(w)
                if both: d.setdefault('soft_face_locking', []).append(w); d.setdefault('soft_face_locking_evidence', {})[w] = f'not computable under either friction law (stick-memory t_last {_tl}, production-law restart t_last {_ftl}' + (', first increments' if early else '') + ')'
        d['open_reason'] = ('; '.join(died) + '; ' if died else '') + 'window(s) ' + ', '.join(d['missing']) + ' did not reach the intact ROM or 1.5 N m (or missing)'
        if died: d['computability'] = True
        if d.get('soft_face_locking'): d['soft_face_locking_note'] = '生理窗口算不出：兩種摩擦律（黏滯記憶律、參考律）從同一檢查點重啟都在評估點前中止 (PI 2026-11-10 item 2 class; 2026-11-11: the soft-face-locking hypothesis is not supported by the replicate evidence, see replicates; windows ' + ', '.join(d['soft_face_locking']) + ')'
# designs attempted in physio_fric3 whose insertion run stopped before the windows (largest final time over the run dirs)
for cdir in sorted(glob.glob(R + 'physio_fric3/p*')):
    p = os.path.basename(cdir)[:4]; lg = cdir + '/case.log'
    if (p in verd and (verd[p].get('windows') or not verd[p].get('computability'))) or not os.path.exists(lg): continue   # keep the run dir with the largest final time; 2026-11-10 17:xx: a design with window rows (physio_relG, or production windows next to a stale failed attempt dir) is never overwritten by this scan
    txt = open(lg, errors='ignore').read(); tt = re.findall(r'Time = ([0-9.eE+-]+)', txt); t_end = float(tt[-1]) if tt else 0.0
    if 'E R R O R' not in txt[-4000:] or t_end == 0.0: continue
    prev = verd.get(p, {}).get('t_end', -1)
    if t_end > prev:
        verd[p] = dict(verdict='open', reasons=[], windows={}, missing=list(REQ), t_end=t_end, case_dir=os.path.basename(cdir), insertion_process='production (insertion stopped before the windows; PI 2026-11-10 option a: to be rerun with process G as physio_relG)',
                       open_reason=(f'frictional insertion run stopped at t {t_end:.3f} in the static release step, before the follower load (platform problem, cluster 1 of DECISIONS 2026-11-03 22:30; not the C3 release impact)' if t_end < 3.0 else
                                    f'frictional insertion run stopped at t {t_end:.3f} in the first dynamic step after the C3 hold release (release impact, DECISIONS 2026-11-04 01:30)'), computability=True, stop_phase='static_release' if t_end < 3.0 else 'c3_release_impact')
# process-G insertion (physio_relG run dirs) that stopped before the windows: supersedes the fric3 'to be rerun with process G' record of that design
for rd in sorted(glob.glob(R + 'physio_relG/p*_gpu*')):
    p = os.path.basename(rd)[:4]; lg = rd + '/case.log'
    if not os.path.exists(lg) or (p in verd and verd[p].get('windows')): continue
    txt = open(lg, errors='ignore').read()
    if 'E R R O R' not in txt[-4000:]: continue
    tt = re.findall(r'Time = ([0-9.eE+-]+)', txt); t_end = float(tt[-1]) if tt else 0.0
    if t_end >= 3.499 or (str(verd.get(p, {}).get('insertion_process', '')).startswith('G') and verd[p].get('t_end', -1) >= t_end): continue
    verd[p] = dict(verdict='open', reasons=[], windows={}, missing=list(REQ), t_end=t_end, case_dir=os.path.basename(rd), insertion_process=f'G (insertion stopped at t {t_end:.3f}; PI 2026-11-10 option a)',
                   open_reason=f'process-G frictional insertion run stopped at t {t_end:.3f}, before the windows', computability=True, stop_phase='G_insertion')
# 2026-11-11 replicates: designs built from byte-identical decks (same launched_feb.sha256 / case.feb hash of the production build) are one design;
# their outcomes differ only by run-to-run numerical variability (p050 / p068 / p084 / p127: one passes both windows, three have a window that
# stopped in the first increments). Verdicts stay per design id (PI decision pending); every such design lists its replicates and their verdicts.
import hashlib as _hl
def _deck(p):
    for s in ('physio_fric3', 'physio_fric5', 'physio_relG'):
        for d in [R + f'{s}/{p}'] + sorted(glob.glob(R + f'{s}/{p}_gpu*')):
            f = os.path.join(d, 'launched_feb.sha256')
            if os.path.exists(f): return open(f).read().split()[0]
            f = os.path.join(d, 'case.feb')
            if os.path.exists(f): return _hl.sha256(open(f, 'rb').read()).hexdigest()
_groups = {}
for p in verd: _groups.setdefault(_deck(p), []).append(p)
for h, ps in _groups.items():
    if h is None or len(ps) < 2: continue
    for p in ps: verd[p]['replicates'] = dict(deck_sha256=h[:16], designs=[q for q in ps if q != p], verdicts={q: verd[q]['verdict'] for q in ps}, consistent=len({verd[q]['verdict'] for q in ps}) == 1)
# PI 2026-11-11 decision 4 (「需區分設計本身的模擬結果和平台對於部分設計的數值不穩定問題，結果可以留下但是最後希望是同一個設計能有穩定的模擬結果數值」):
# DESIGN layer - a deck-hash replicate group is one design: a replicate whose required window is not computable under either friction law
# inherits the computed replicate's windows and verdict (the most conservative one if several computed), recorded as verdict_source; its own
# partial result stays under 'own'. PLATFORM layer - the inheritance is flagged numerical_flags ['replicate-not-reproduced'], and a group whose
# computed replicates disagree in verdict gets 'replicate-inconsistent' on every member; results stay, the flags are the open [數值] items.
_order = {'fail': 0, 'grey': 1, 'pass': 2}
for h, ps in _groups.items():
    if h is None or len(ps) < 2: continue
    computed = [q for q in ps if verd[q]['verdict'] in _order]
    for p in ps:
        d = verd[p]
        if d['verdict'] == 'open' and d.get('soft_face_locking') and computed:
            src = min(computed, key=lambda q: _order[verd[q]['verdict']])
            d['own'] = {k: d.get(k) for k in ('verdict', 'windows', 'missing', 'open_reason', 'computability', 'soft_face_locking', 'soft_face_locking_evidence', 'soft_face_locking_note', 'first_increment_pattern') if d.get(k) is not None}
            d['windows'] = {w: dict(r, inherited_from=src) for w, r in verd[src]['windows'].items()}
            d['verdict'] = verd[src]['verdict']; d['reasons'] = list(verd[src].get('reasons', [])); d['missing'] = []; d['grey'] = list(verd[src].get('grey') or [])
            for k in ('open_reason', 'computability', 'soft_face_locking', 'soft_face_locking_evidence', 'soft_face_locking_note', 'first_increment_pattern'): d.pop(k, None)   # 2026-11-13 audit D-20261111-31: the design-level result is the inherited one; the own result keeps these
            d['verdict_source'] = f'replicate {src} (PI 2026-11-11 decision 4: same deck + same procedure = one design result; own result under own)'
            d.setdefault('numerical_flags', []).append('replicate-not-reproduced')
    if len({verd[q]['verdict'] for q in computed}) > 1:   # computed replicates that disagree (2026-11-13: the deck group takes the MOST CONSERVATIVE verdict - PI 「同個設計同個模擬流程，應認為同個結果」;
        worst = min(computed, key=lambda q: _order[verd[q]['verdict']])   # each member keeps its own windows / read-outs under own_verdict; the disagreement stays a [數值] flag)
        # PI 2026-11-17 (p093 / p145, 0.552 vs 0.539 mm): 「為何會兩次不一樣，可以列為灰區」 - when the disagreeing replicates' posterior read-outs differ by no more
        # than REPL_NOISE, the group sits on a limit within the run-to-run noise and is classed GREY (boundary; analysis only), not fail; larger spreads keep the most conservative member.
        _spread = 0.0
        for _w in REQ:   # per window: the posterior read-out at the window's evaluation point, spread across the computed replicates
            _posts = [abs((x.get('post_at_1p5Nm') if x.get('eval_point') == '1.5Nm' else x.get('post_at_rom')) or 0) for q in computed for _wn, x in verd[q]['windows'].items() if _wn == _w and x.get('usable')]
            _spread = max([_spread] + [abs(a - b) for a in _posts for b in _posts])
        if _spread <= REPL_NOISE and 'grey' in {verd[q]['verdict'] for q in computed} | {'grey' if verd[worst]['verdict'] == 'fail' else ''}:
            worst = next((q for q in computed if verd[q]['verdict'] == 'grey'), worst); boundary = True
        else: boundary = False
        for q in computed:
            verd[q].setdefault('numerical_flags', []).append('replicate-inconsistent')
            if verd[q]['verdict'] != verd[worst]['verdict']:
                verd[q]['own_verdict'] = verd[q]['verdict']; verd[q]['own_reasons'] = list(verd[q].get('reasons', []))
                verd[q]['own_grey'] = list(verd[q].get('grey') or []); verd[q]['grey'] = list(verd[worst].get('grey') or []); verd[q].pop('grey_note', None)
                verd[q]['verdict'] = 'grey' if boundary else verd[worst]['verdict']
                verd[q]['reasons'] = ([f'replicate group on the limit (spread {_spread:.4f} mm <= {REPL_NOISE}): grey by PI 2026-11-17'] if boundary else [f'unified to replicate {worst} (most conservative of the deck group; its reasons: ' + '; '.join(verd[worst].get('reasons', [])) + ')'])
                if boundary: verd[q]['grey'] = verd[q].get('own_grey') or [f'{_w2}: own posterior {abs((x2.get("post_at_1p5Nm") if x2.get("eval_point") == "1.5Nm" else x2.get("post_at_rom")) or 0):.3f} mm on the 0.55 limit (replicate group straddles it; PI 2026-11-17 boundary grey)' for _w2, x2 in verd[q]['windows'].items() if x2.get('usable') and abs((x2.get('post_at_1p5Nm') if x2.get('eval_point') == '1.5Nm' else x2.get('post_at_rom')) or 0) > GREY_LO]; verd[q]['grey_note'] = '灰區（限值邊界）：同模型複本讀值跨在限值兩側、差距在數值雜訊內，PI 2026-11-17 列為灰區；僅供分析，不得作為 final design'
                verd[q]['verdict_source'] = (f'replicate group on the limit -> grey (PI 2026-11-17; own verdict under own_verdict)' if boundary else f'replicate group, most conservative member {worst} (PI 2026-11-11 decision 4; own verdict under own_verdict)')
    # D-20261113-26(c) sign-off (2026-11-17, 授權自行決定): 'consistent' = the members' OWN computed verdicts agree (own_verdict where unified); 'unified' says the group verdict was imposed
    for q in ps: verd[q]['replicates']['verdicts'] = {r: verd[r]['verdict'] for r in ps}; verd[q]['replicates']['own_verdicts'] = {r: verd[r].get('own_verdict', verd[r]['verdict']) for r in ps}; verd[q]['replicates']['consistent'] = len({verd[r].get('own_verdict', verd[r]['verdict']) for r in ps}) == 1; verd[q]['replicates']['unified'] = any('own_verdict' in verd[r] for r in ps)
verd['_meta'] = dict(fallback_margin_mm=FALLBACK_MARGIN, margin_basis=MARGIN_BASIS, window_drive_disclosure='every joint-driven window (sets physio_fric*, physio_relG, physio_relG_pl) starts with a snap of C3 back to its t=0 orientation (insertion tilt: production 0.08-1.53 deg, median 0.21; process G 0.46-1.31 deg, median 0.87; DECISIONS 2026-11-11 01:00) - its read-outs are superseded per window by the route-E sets physio_fric5r / physio_relGr (PI 2026-11-11 1a) where those reached an evaluation point; each window row carries window_drive', grey_sub_rule='analysis only (授權自決 2026-11-13): posterior 0.45-0.50 grey-low, 0.50-0.55 grey-high; verdict unchanged', replicate_rule='PI 2026-11-11 decision 4: a not-computable replicate inherits the computed replicate of the same deck (verdict_source, own); numerical_flags replicate-not-reproduced / replicate-inconsistent mark the platform reproducibility items', not_computable_rule='2026-11-11: a required window is classed not computable (key soft_face_locking, compatibility name) only when the stick-memory window AND the production-law restart of the same checkpoint both stopped before an evaluation point; the first-increment pattern alone is noted (first_increment_pattern) and no longer vetoes a fallback; designs built from identical decks list each other under replicates', set_precedence='per window the highest-ranked set in SETS wins: physio_fric5 (stick-memory law, PI 2026-11-09) supersedes physio_fric3 (production law, NUM-13 artefact); physio_relG (process G, PI 2026-11-10 option a) holds the 27 insertion-stopped designs; physio_relG_pl is a fallback source only (production law on the G checkpoint, + margin, flagged); the insertion-stopped scans: physio_fric3 then physio_relG', rule='PI 2026-11-10: posterior 0.45-0.55 mm at the evaluation point = grey (analysis only, never a final design), > 0.55 or any-direction > 1 mm = fail; every row/design carries insertion_process and window_law (PI 2026-11-10 option a); PI 2026-11-03 04:30, confirmed 2026-11-05: evaluation point = 1.5 N m state when transmitted, else intact ROM; limits 1 mm any / 0.5 mm posterior; PI 2026-11-07 decision 1: this friction result is a CHECK of the mu_req (tied) slip-out verdict, not a gate (collect_split records friction_check); the 2026-11-03 gate-4 role is withdrawn',
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
# QA audit 2026-11-10 不符 #2: the summary counts run over the per-window WINNERS (best), not over all rows - the same window used to be
# counted once per set (89 = fric2 14 + fric3 36 + fric5 39)
ok = [r for r in best.values() if r.get('fric_reached') and (r.get('window_check') or {}).get('monotonic', True)]
rom = [r for r in best.values() if r.get('rom_reached')]
if rom:
    w2 = max(rom, key=lambda r: r['u_h_at_rom']); print(f"{len(rom)} windows reached the intact ROM; largest cage translation there {w2['u_h_at_rom']:.3f} mm ({w2['set']} {w2['design']} {w2['window']}); all <= 1 mm: {all(r['u_h_at_rom'] <= 1.0 for r in rom)}; posterior <= 0.5 mm: {all(r['post_at_rom'] <= 0.5 for r in rom)}")
if ok:
    worst = max(ok, key=lambda r: r['fric_translation_mm'])
    print(f"\n{len(ok)} windows reached 1.5 N m with real friction; largest cage translation {worst['fric_translation_mm']:.3f} mm ({worst['design']} {worst['window']}); "
          f"all <= 1 mm: {all(r['fric_translation_mm'] <= 1.0 for r in ok)}; posterior <= 0.5 mm: {all(r['fric_posterior_mm'] <= 0.5 for r in ok)}")
