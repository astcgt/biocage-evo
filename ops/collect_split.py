"""Post-process split physio_rot runs (al_v2/physio_rot_split2; physio_rot_split is invalid: rotation not applied) (h30/h31: one insertion, six independent window restarts) and merge them into the
per-design slip (e04) and compression (e05) verdicts.

Each ended window dir w_<name> is a self-contained case (single-window physio_schedule.json), so e04 / e05 run on it as is.
Per design and window the split result replaces the earlier one when it reached the target moment (or when there was none).
Compression rule (user, 2026-10-31): sustained after insertion <= 15 %, peak during each motion <= 25 %, 99th percentile.
2026-11-02: every design gets 'class' / 'reason' (PASS, DESIGN/compression-*, [觀測]/amplitude, [觀測]/integrity,
[多元]/computability, DECISION/T05-lowerbound) -> verdict_classes_merged.json; windows without a valid logged state are
rejected (window_check from e04); old folder names in result files are normalised.
usage: python ops/collect_split.py [workers]   (incremental: windows already processed are skipped)
"""
import os, sys, glob, json, subprocess
from concurrent.futures import ThreadPoolExecutor

E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026/human_study/al_v2/'
OLD_R = ('/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1/human_study/al_v2/',       # folder renamed 2026-11-01 / 11-02
         '/raid/jupyter-alz.ee09/projects/claude-work/biocage_stimulation_test_oct2026/human_study/al_v2/')
def norm_case(case):
    for o in OLD_R: case = case.replace(o, R)
    return case
OUT = os.path.join(E, 'results/method/split'); os.makedirs(OUT, exist_ok=True)
WIN = ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right')
SUS, PEAK = 0.15, 0.25
ended = lambda log: os.path.exists(log) and any(k in open(log, errors='ignore').read()[-4000:] for k in ('N O R M A L', 'E R R O R'))

SETS = ('physio_rot_split2', 'physio_rot_split3', 'physio_rot_split4')   # split3 / split4 = second / third pass with retargeted amplitudes (2026-10-31)
wds = [w for s in SETS for w in sorted(glob.glob(R + s + '/p*/w_*')) if ended(w + '/case.log') and os.path.exists(w + '/case.xplt')]
set_of = lambda w: w.split('/al_v2/')[1].split('/')[0]

def one(w):
    # file tag: <design dir>__<window> for the original split2 set, <set>__<design dir>__<window> for later sets
    tag = (('' if set_of(w) == 'physio_rot_split2' else set_of(w) + '__') + os.path.basename(os.path.dirname(w)) + '__' + os.path.basename(w)[2:])
    rc = 0
    for m, s, to in (('e04', 'methods/e04_dislocation.py', 1500), ('e05', 'methods/e05_compression.py', 2400)):
        o = os.path.join(OUT, f'{tag}.{m}.json')
        if os.path.exists(o): continue
        r = subprocess.run(['timeout', str(to), sys.executable, os.path.join(E, s), w, o], capture_output=True, text=True)
        if r.returncode: open(os.path.join(OUT, f'{tag}.{m}.err'), 'w').write(r.stderr[-3000:]); rc = 1
    return rc

with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3) as ex: rc = list(ex.map(one, wds))

# ---- aggregate from EVERY per-run result file (reproducible; no hand-merged intermediates, 2026-10-31) ----
# A per-run file is keyed by its case directory. Runs in invalid sets are excluded explicitly. Among valid results of one
# design and window: a window that reached 1.5 N m beats one that did not; then the preferred run set (independent dynamic
# windows first); then the larger |M| (closer to / further past the target). The insertion state (sustained compression)
# takes the preferred set that has it. Sources are recorded per value.
import re
INVALID = ('invalid', 'physio_rot_split/', 'physio_rot_split_test', 'cases_invalid', 'physio_test', 'facet_test', 'lb_test', 'physio_rot_facet')
ORDER = ('physio_rot_split4', 'physio_rot_split3', 'physio_rot_split2', 'physio_rot_dyn2', 'physio_rot_dyn', 'physio_rot_r2', 'physio_rot')
rank = lambda case: next((i for i, s in enumerate(ORDER) if f'/{s}/' in case + '/'), len(ORDER))
pid = lambda case: (re.search(r'/(p\d{3})', case) or [None, None])[1]
valid = lambda case: not any(k in case for k in INVALID)
e04c, e05c, rejected = {}, {}, {}                              # design -> window -> [candidates]; rejected windows (integrity)
for f in glob.glob(os.path.join(E, 'results/method/e04_rot/*.json')) + glob.glob(os.path.join(OUT, '*.e04.json')):
    if os.path.basename(f) in ('best_by_design.json', 'failed_runs_lastJ.json'): continue
    j = json.load(open(f)); case = norm_case(j.get('case', ''))
    if not case or not valid(case) or not pid(case): continue
    for wn, r in j['windows'].items():                      # a window can be the string 'missing' (no state near the target)
        if wn not in WIN or not isinstance(r, dict): continue
        chk = r.get('window_check')                          # 2026-11-02: a window without a single valid logged state is not a result
        if chk is not None and chk.get('n_rows', 1) - chk.get('n_invalid', 0) <= 0:
            rejected.setdefault(pid(case), []).append(f'{wn}: no valid drive state ({os.path.relpath(case, R)})'); continue
        e04c.setdefault(pid(case), {}).setdefault(wn, []).append((r, case, rank(case)))
for f in glob.glob(os.path.join(E, 'results/method/e05/*.json')) + glob.glob(os.path.join(OUT, '*.e05.json')):
    b = os.path.basename(f)
    if b in ('by_design.json', 'verdict_lists.json') or '__' not in b: continue
    parts = b.split('__')
    if f.startswith(OUT):                                   # split window result: [<set>__]<design dir>__<window>.e05.json
        st, dd, wn_ = (parts if len(parts) == 3 else ['physio_rot_split2'] + parts)
        case = R + f'{st}/{dd}/w_{wn_[:-9]}'
    else:                                                   # sequential run result: <set>__<design dir>.json
        s, d = parts[0], '__'.join(parts[1:]); case = R + f'{s}/{d[:-5]}'
    if not valid(case) or not pid(case): continue
    j = json.load(open(f)); e05c.setdefault(pid(case), {'sus': [], 'win': {}})
    if j.get('sustained') is not None: e05c[pid(case)]['sus'].append((j['sustained'], case, rank(case)))
    for wn, cw in j['windows'].items():
        if wn in WIN and cw and cw.get('peak') is not None: e05c[pid(case)]['win'].setdefault(wn, []).append((cw, case, rank(case)))
# ---- duplicate designs (PI 2026-11-03, T26): the AL sampled identical cage parameters under different ids (p082=p088,
# p092=p117, p093=p145, p100=p142; only the h28 amplitudes differ). Their window and insertion evidence is pooled, so every
# id of a group is judged on the union; the record says which ids it shares evidence with.
def signature(case_json):
    p = dict(json.load(open(case_json)).get('params', {})); p.pop('physio_rot_rad', None)
    return json.dumps(p, sort_keys=True)
sig = {}
for f in glob.glob(R + 'physio_rot_split*/p*/case.json'):
    if not valid(f): continue
    q = pid(f); sig.setdefault(q, signature(f))
groups = {}
for q, s in sig.items(): groups.setdefault(s, []).append(q)
dup = {q: sorted(g) for g in groups.values() if len(g) > 1 for q in g}
for q, g in dup.items():
    for o in g:
        if o == q: continue
        for wn, cands in e04c.get(o, {}).items(): e04c.setdefault(q, {}).setdefault(wn, []).extend(cands)
        if o in e05c:
            e05c.setdefault(q, {'sus': [], 'win': {}})['sus'].extend(e05c[o]['sus'])
            for wn, cands in e05c[o]['win'].items(): e05c[q]['win'].setdefault(wn, []).extend(cands)
best, comp = {}, {}
for p, ws in e04c.items():
    for wn, cands in ws.items():
        r, case, _ = max(cands, key=lambda c: (bool(c[0]['target_reached']), -c[2], abs(c[0].get('M_at_target') or 0)))
        best.setdefault(p, {})[wn] = dict(r, source=os.path.relpath(case, R))
for p, c in e05c.items():
    d = comp.setdefault(p, {'sustained': None, 'windows': {}})
    if c['sus']: v, case, _ = min(c['sus'], key=lambda x: x[2]); d['sustained'] = v; d['source'] = os.path.relpath(case, R)
    for wn, cands in c['win'].items():
        cw, case, _ = max(cands, key=lambda x: (bool(x[0]['reached']), -x[2])); d['windows'][wn] = dict(cw, source=os.path.relpath(case, R))

# manual overrides with provenance (results/method/split/manual_overrides.json): designs whose insertion state was evaluated
# from a run outside physio_rot_split2 (e.g. the split v1 insertion run, which is valid: the load-curve bug affected only the windows)
ov = os.path.join(OUT, 'manual_overrides.json')
for p, o in (json.load(open(ov)).items() if os.path.exists(ov) else []):
    d = comp.setdefault(p, {'windows': {}})
    if d.get('sustained') is None and o.get('sustained') is not None: d['sustained'] = o['sustained']; d['source'] = o['source']; d['override_reason'] = o['reason']

# ---- verdict + class (PI 2026-11-01: every non-pass design carries the capability label of its cause, or DESIGN / DECISION) ----
# failed_runs_lastJ.json (e04_rot): [t_last, min J, max soft z-compression %, E_soft, family, run] of insertion runs that
# stopped (negative Jacobians) before any window: the only evidence for designs without an insertion state.
LASTJ = os.path.join(E, 'results/method/e04_rot/failed_runs_lastJ.json')
lastj = {}
for t_, J_, cz_, Es_, fam_, run_ in (json.load(open(LASTJ)) if os.path.exists(LASTJ) else []):
    q = pid('/' + run_)
    if q and (q not in lastj or t_ > lastj[q][0]): lastj[q] = (t_, cz_)
lists = {'both': [], 'comp_pass_slip_open': [], 'open': [], 'fail': []}; classes = {}
for p in sorted(set(best) | set(comp) | set(lastj)):
    c = comp.setdefault(p, {'sustained': None, 'windows': {}}); b = best.get(p, {})
    # an UNSTABLE window (2026-11-02): spurious states were dropped AND |M| is not monotonic, i.e. the moment collapsed or
    # chattered (p027 extension: 1434 -> spike 1742 -> 992 -> -137 N mm, bone elements inverted). Its states after the collapse
    # are not a lower bound of anything, so it counts neither as reached nor towards a compression fail; the design stays open
    # with the [數值] label until the window is recomputed. A window that merely STOPPED early (ERROR) keeps its lower bound.
    # 2026-11-02 evening: also when the dropped states were the end of the ramp (complete False), i.e. the window died in
    # dynamic residual / chatter before the target (p027 extension after the NUM-14 filter).
    unstable = [w for w, v in c['windows'].items() if (v.get('window_check') or {}).get('n_invalid', 0) > 0
                and not ((v.get('window_check') or {}).get('monotonic', True) and (v.get('window_check') or {}).get('complete', True)) and not v.get('reached')]
    pk = [v.get('peak') for w, v in c['windows'].items() if v.get('peak') is not None and w not in unstable]
    sus = c.get('sustained')                                   # None when the insertion state could not be evaluated
    fail = (sus is not None and sus > SUS) or any(x > PEAK for x in pk)
    reached = all(b.get(w, {}).get('target_reached') for w in WIN)
    c['verdict'] = 'fail' if fail else ('pass' if sus is not None and all(c['windows'].get(w, {}).get('reached') for w in WIN) else 'open')
    if unstable: c['unstable_windows'] = unstable
    if fail:
        lists['fail'].append(p)
        bad = [w for w, v in c['windows'].items() if (v.get('peak') or 0) > PEAK and w not in unstable]
        lb = [w for w in bad if not c['windows'][w].get('reached')]
        c['class'] = 'DESIGN/compression-sustained' if sus is not None and sus > SUS else 'DESIGN/compression-peak' + ('-lowerbound' if lb else '')
        c['reason'] = (f'sustained {sus:.3f} > {SUS}' if sus is not None and sus > SUS else '') + (f' peak > {PEAK} in {bad}' if bad else '') + (f' (lower bound: window(s) {lb} did not reach the target)' if lb else '')
    elif c['verdict'] == 'pass' and reached: lists['both'].append(p); c['class'] = 'PASS'; c['reason'] = ''
    elif c['verdict'] == 'pass':
        lists['comp_pass_slip_open'].append(p); low = [w for w in WIN if not b.get(w, {}).get('target_reached')]
        c['class'] = '[觀測]/amplitude'; c['reason'] = f'compression pass; e04 window(s) {low} below the target moment (R02: never a design verdict)'
    else:
        lists['open'].append(p)
        if sus is None:
            if p in lastj:
                t_, cz_ = lastj[p]
                if t_ >= 3.0 and cz_ > 100 * SUS:              # PI 2026-11-03: a run that stops under the follower load with the soft layer already past the limit FAILS by lower bound
                    c['verdict'] = 'fail'; lists['open'].remove(p); lists['fail'].append(p)
                    c['class'] = 'DESIGN/compression-sustained-lowerbound'; c['reason'] = f'insertion run stopped at t {t_} under the follower load, soft z-compression {cz_:.0f} % > {100 * SUS:.0f} % at the last state: fail by lower bound (PI decision 2026-11-03)'
                else: c['class'] = '[多元]/computability'; c['reason'] = f'insertion run stopped at t {t_} (compression {cz_:.0f} %): not computable in any solve mode'
            else: c['class'] = '[觀測]/integrity'; c['reason'] = 'no insertion state (no e05 result, no failed-run record)' + (f'; rejected: {rejected[p]}' if p in rejected else '')
        else:
            low = [w for w in WIN if not c['windows'].get(w, {}).get('reached') and w not in unstable]
            miss = [w for w in WIN if w not in c['windows']]
            if unstable: c['class'] = '[數值]/unstable-window'; c['reason'] = f'window(s) {unstable}: spurious states dropped and the moment is not monotonic or the ramp did not end in a valid state (contact / element instability); recompute before any verdict'
            elif miss: c['class'] = '[觀測]/integrity'; c['reason'] = f'window(s) {miss} missing' + (f'; rejected: {rejected[p]}' if p in rejected else '')
            else: c['class'] = '[觀測]/amplitude'; c['reason'] = f'window(s) {low} below the target moment (R02: never a design verdict)'
    if p in dup: c['duplicates'] = [q for q in dup[p] if q != p]
    classes.setdefault(c['class'], []).append(p)
json.dump(best, open(os.path.join(OUT, 'best_by_design_merged.json'), 'w'), indent=1)
json.dump(comp, open(os.path.join(OUT, 'comp_by_design_merged.json'), 'w'), indent=1)
json.dump(lists, open(os.path.join(OUT, 'verdict_lists_merged.json'), 'w'), indent=1)
json.dump(dict(classes=classes, rejected_windows=rejected), open(os.path.join(OUT, 'verdict_classes_merged.json'), 'w'), indent=1)
bo = [p for p in lists['both']]
mu = max((best[p][w]['mu_squeeze'] for p in bo for w in WIN), default=None)
sl = max((best[p][w]['one_face_slip_bound_mm'] for p in bo for w in WIN), default=None)
print(f'{len(wds)} windows ({sum(rc)} with errors); ' + ', '.join(f'{k} {len(v)}' for k, v in lists.items()) + f'; both: max mu {mu}, max slip {sl} mm')
print('classes: ' + ', '.join(f'{k} {len(v)}' for k, v in sorted(classes.items())) + f'; rejected windows: {sum(len(v) for v in rejected.values())}')
