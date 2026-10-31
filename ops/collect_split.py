"""Post-process split physio_rot runs (al_v2/physio_rot_split2; physio_rot_split is invalid: rotation not applied) (h30/h31: one insertion, six independent window restarts) and merge them into the
per-design slip (e04) and compression (e05) verdicts.

Each ended window dir w_<name> is a self-contained case (single-window physio_schedule.json), so e04 / e05 run on it as is.
Per design and window the split result replaces the earlier one when it reached the target moment (or when there was none).
Compression rule (user, 2026-10-31): sustained after insertion <= 15 %, peak during each motion <= 25 %, 99th percentile.
usage: python ops/collect_split.py [workers]   (incremental: windows already processed are skipped)
"""
import os, sys, glob, json, subprocess
from concurrent.futures import ThreadPoolExecutor

E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1/human_study/al_v2/'
OUT = os.path.join(E, 'results/method/split'); os.makedirs(OUT, exist_ok=True)
WIN = ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right')
SUS, PEAK = 0.15, 0.25
ended = lambda log: os.path.exists(log) and any(k in open(log, errors='ignore').read()[-4000:] for k in ('N O R M A L', 'E R R O R'))

wds = [w for w in sorted(glob.glob(R + 'physio_rot_split2/p*_*/w_*')) if ended(w + '/case.log') and os.path.exists(w + '/case.xplt')]

def one(w):
    tag = os.path.basename(os.path.dirname(w)) + '__' + os.path.basename(w)[2:]
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
ORDER = ('physio_rot_split2', 'physio_rot_dyn2', 'physio_rot_dyn', 'physio_rot_r2', 'physio_rot')
rank = lambda case: next((i for i, s in enumerate(ORDER) if f'/{s}/' in case + '/'), len(ORDER))
pid = lambda case: (re.search(r'/(p\d{3})', case) or [None, None])[1]
valid = lambda case: not any(k in case for k in INVALID)
e04c, e05c = {}, {}                                            # design -> window -> [candidates]
for f in glob.glob(os.path.join(E, 'results/method/e04_rot/*.json')) + glob.glob(os.path.join(OUT, '*.e04.json')):
    if os.path.basename(f) in ('best_by_design.json', 'failed_runs_lastJ.json'): continue
    j = json.load(open(f)); case = j.get('case', '')
    if not case or not valid(case) or not pid(case): continue
    for wn, r in j['windows'].items():                      # a window can be the string 'missing' (no state near the target)
        if wn in WIN and isinstance(r, dict): e04c.setdefault(pid(case), {}).setdefault(wn, []).append((r, case, rank(case)))
for f in glob.glob(os.path.join(E, 'results/method/e05/*.json')) + glob.glob(os.path.join(OUT, '*.e05.json')):
    b = os.path.basename(f)
    if b in ('by_design.json', 'verdict_lists.json') or '__' not in b: continue
    s, d = b.split('__', 1)
    case = R + (f'physio_rot_split2/{s}/w_{d[:-9]}' if f.startswith(OUT) else f'{s}/{d[:-5]}')
    if not valid(case) or not pid(case): continue
    j = json.load(open(f)); e05c.setdefault(pid(case), {'sus': [], 'win': {}})
    if j.get('sustained') is not None: e05c[pid(case)]['sus'].append((j['sustained'], case, rank(case)))
    for wn, cw in j['windows'].items():
        if wn in WIN and cw and cw.get('peak') is not None: e05c[pid(case)]['win'].setdefault(wn, []).append((cw, case, rank(case)))
best, comp = {}, {}
for p, ws in e04c.items():
    for wn, cands in ws.items():
        r, case, _ = max(cands, key=lambda c: (bool(c[0]['target_reached']), -c[2], abs(c[0]['M_at_target'])))
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

lists = {'both': [], 'comp_pass_slip_open': [], 'open': [], 'fail': []}
for p in sorted(set(best) | set(comp)):
    c = comp.get(p); b = best.get(p, {})
    if c is None: lists['open'].append(p); continue
    pk = [w.get('peak') for w in c['windows'].values() if w.get('peak') is not None]
    sus = c.get('sustained')                                   # None when the insertion state could not be evaluated
    fail = (sus is not None and sus > SUS) or any(x > PEAK for x in pk)
    reached = all(b.get(w, {}).get('target_reached') for w in WIN)
    c['verdict'] = 'fail' if fail else ('pass' if sus is not None and all(c['windows'].get(w, {}).get('reached') for w in WIN) else 'open')
    if fail: lists['fail'].append(p)
    elif c['verdict'] == 'pass' and reached: lists['both'].append(p)
    elif c['verdict'] == 'pass': lists['comp_pass_slip_open'].append(p)
    else: lists['open'].append(p)
json.dump(best, open(os.path.join(OUT, 'best_by_design_merged.json'), 'w'), indent=1)
json.dump(comp, open(os.path.join(OUT, 'comp_by_design_merged.json'), 'w'), indent=1)
json.dump(lists, open(os.path.join(OUT, 'verdict_lists_merged.json'), 'w'), indent=1)
bo = [p for p in lists['both']]
mu = max((best[p][w]['mu_squeeze'] for p in bo for w in WIN), default=None)
sl = max((best[p][w]['one_face_slip_bound_mm'] for p in bo for w in WIN), default=None)
print(f'{len(wds)} windows ({sum(rc)} with errors); ' + ', '.join(f'{k} {len(v)}' for k, v in lists.items()) + f'; both: max mu {mu}, max slip {sl} mm')
