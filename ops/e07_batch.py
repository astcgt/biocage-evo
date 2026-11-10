"""Interface-shear (e07) over the frictional flexion / extension windows of al_v2/physio_fric3 (PI 2026-11-04: shear large
enough to delaminate the printed hard / soft interface = safety failure). Per window: e07 state series -> value at the
intact-ROM state (t_rom from results/method/fric/compare.json), the maximum up to that state, and the insertion value
(first state, t 3.5, follower on). Writes results/method/fric/e07/<case>__<window>.json and results/method/fric/e07_summary.csv.
Verdict (second part of this file): PI 2026-11-04 threshold 3 MPa on the soft-side p99 at the intact-ROM state, PROVISIONAL (bond strength
of the co-printed interface not measured). 2026-11-04 QA fix: the ROM-state value and max-to-ROM are interpolated over the VALID states only
(NUM-14 two-layer filter, e3.target_bracket valid_times), as gate 4 does; before, rejected micro-step / dynamic-residual states entered the interpolation.
usage: python ops/e07_batch.py [workers]
"""
import os, sys, glob, json, csv, subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'methods')); import e03_mu_req as e3

E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026/human_study/al_v2/'
OUT = os.path.join(E, 'results/method/fric/e07'); os.makedirs(OUT, exist_ok=True)
ended = lambda log: os.path.exists(log) and any(k in open(log, errors='ignore').read()[-4000:] for k in ('N O R M A L', 'E R R O R'))
SETS = ('physio_fric3', 'physio_fric5', 'physio_relG'); RANK = {s_: i for i, s_ in enumerate(SETS)}   # 2026-11-09 (PI decision 1): fric5 = the same windows recomputed with the stick-memory law; it supersedes fric3 per (design, window) in the shear gate too
wds = [w for s_ in SETS for w in sorted(glob.glob(R + s_ + '/p*/w_*')) if ended(w + '/case.log') and os.path.exists(w + '/case.xplt')]
set_of = lambda w: w.split('/al_v2/')[1].split('/')[0]


def one(w):
    tag = ('' if set_of(w) == 'physio_fric3' else set_of(w) + '__') + os.path.basename(os.path.dirname(w)) + '__' + os.path.basename(w)[2:]; o = os.path.join(OUT, tag + '.json')   # fric5 dirs are bare pNNN like 13 fric3 dirs: the set prefix keeps them apart
    if not os.path.exists(o):
        r = subprocess.run(['timeout', '1800', sys.executable, os.path.join(E, 'methods/e07_interface_shear.py'), w, o], capture_output=True, text=True)
        if r.returncode: open(o[:-5] + '.err', 'w').write(r.stderr[-3000:]); return None
    return w, o


with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3) as ex: done = [x for x in ex.map(one, wds) if x]
rows = {(r['set'], r['case_dir'], r['window']): r for r in json.load(open(os.path.join(E, 'results/method/fric/compare.json'))) if r.get('set') in SETS and 'note' not in r}
out = []
for w, o in done:
    cd, wn = os.path.basename(os.path.dirname(w)), os.path.basename(w)[2:]; j = json.load(open(o)); r = rows.get((set_of(w), cd, wn), {})
    t_all = np.array([s['time'] for s in j['states']])
    try:
        vt = np.array(e3.target_bracket(w, json.load(open(os.path.join(w, 'physio_schedule.json'))))[wn]['valid_times'])
        keep = np.isin(np.round(t_all, 6), np.round(vt, 6)) | (t_all <= 3.5 + 1e-9)     # insertion states (t <= 3.5) are kept for the insertion value
    except Exception as ex:
        keep = np.ones(len(t_all), bool); print('valid-state filter unavailable for', w, ex)
    t = t_all[keep]
    def series(cls, key): return np.array([s[cls][key] if cls in s else np.nan for s in j['states']])[keep]
    rec = dict(design=cd[:4], set=set_of(w), case_dir=cd, window=wn, n_faces=j['n_faces'], rom_reached=r.get('rom_reached'), t_rom=r.get('t_rom'), u_h_at_rom=r.get('u_h_at_rom'))
    for cls in ('horizontal', 'vertical'):
        if cls + '_max_over_states' not in j: continue
        for key in ('shear_p99', 'shear_max', 'peel_max'):
            v = series(cls, key); rec[f'{cls}_{key}_insertion'] = float(v[int(np.argmin(np.abs(t - 3.5)))])   # state at t 3.5 (the restart's first states can be t 0 / t 3)
            if r.get('t_rom'):
                tr = r['t_rom']; m = t <= tr + 1e-9
                rec[f'{cls}_{key}_at_rom'] = float(np.interp(tr, t, v)); rec[f'{cls}_{key}_max_to_rom'] = float(np.nanmax(v[m])) if m.any() else None
            rec[f'{cls}_{key}_max_window'] = float(np.nanmax(v))
    out.append(rec)
keys = sorted({k for r in out for k in r}, key=lambda k: (k not in ('design', 'set', 'case_dir', 'window'), k))
with open(os.path.join(E, 'results/method/fric/e07_summary.csv'), 'w', newline='') as f:
    wtr = csv.DictWriter(f, fieldnames=keys); wtr.writeheader(); wtr.writerows(out)
print(f'{len(out)} windows; summary results/method/fric/e07_summary.csv')
for r in sorted(out, key=lambda r: (r['design'], r['window'])):
    g = lambda k: f"{r[k]:6.2f}" if r.get(k) is not None else '   -  '
    print(f"{r['design']} {r['window']:9s} ROM {str(r['rom_reached']):5s} | horiz p99 ins {g('horizontal_shear_p99_insertion')} @ROM {g('horizontal_shear_p99_at_rom')} max<=ROM {g('horizontal_shear_p99_max_to_rom')} | vert p99 ins {g('vertical_shear_p99_insertion')} @ROM {g('vertical_shear_p99_at_rom')} max<=ROM {g('vertical_shear_p99_max_to_rom')} | peel max@ROM h {g('horizontal_peel_max_at_rom')} v {g('vertical_peel_max_at_rom')} MPa")

# ---- design verdict (PI 2026-11-04): threshold 3 MPa on the soft-side p99 interface shear at the intact-ROM state, the larger
# of the layer (horizontal) and band-boundary (vertical) interfaces, in flexion and extension; PROVISIONAL until the bond
# strength of the co-printed hard / soft interface is measured. Window rule: a window counts only if it reached the intact ROM
# (stricter than gate 4, which also accepts a window that reached 1.5 N m: implementation choice, PI sign-off pending, QA 2026-11-04);
# a design passes only if both windows count and neither exceeds the threshold; a missing / unreached window leaves it open. No pass by absence.
THR = 3.0; REQ = ('flexion', 'extension')
best = {}
for r in out:                                    # per (design, window) the highest-ranked set wins (fric5 over fric3), as in fric_compare
    k = (r['design'], r['window'])
    if k not in best or RANK[r['set']] > RANK[best[k]['set']]: best[k] = r
ev = {}
for r in [best[k] for k in sorted(best)]:
    d = ev.setdefault(r['design'], dict(verdict=None, reasons=[], windows={}, missing=[]))
    if not r.get('rom_reached'): continue
    v = max(x for x in (r.get('horizontal_shear_p99_at_rom'), r.get('vertical_shear_p99_at_rom')) if x is not None)
    d['windows'][r['window']] = dict(set=r['set'], case_dir=r['case_dir'], shear_p99_at_rom=round(v, 3), horizontal=r.get('horizontal_shear_p99_at_rom'), vertical=r.get('vertical_shear_p99_at_rom'),
                                     peel_max_at_rom=max(x for x in (r.get('horizontal_peel_max_at_rom'), r.get('vertical_peel_max_at_rom')) if x is not None))
    if v > THR: d['reasons'].append(f"{r['window']}@ROM shear p99 {v:.1f} MPa > {THR}")
for p, d in ev.items():
    d['missing'] = [w for w in REQ if w not in d['windows']]
    d['verdict'] = 'fail' if d['reasons'] else ('open' if d['missing'] else 'pass')
    if d['verdict'] == 'open': d['open_reason'] = 'window(s) ' + ', '.join(d['missing']) + ' did not reach the intact ROM (or missing)'
meta = dict(threshold_MPa=THR, metric='soft-side p99 interface shear at the intact-ROM state, max of layer and band-boundary interfaces, flexion and extension (frictional runs; physio_fric5 stick-memory windows supersede physio_fric3 per design and window, PI 2026-11-09 decision 1)',
            provisional='PI 2026-11-04: threshold provisional, pending bond-strength test of the co-printed PLCL hard / soft interface', decided='PI 2026-11-04')
json.dump(dict(meta=meta, designs=ev), open(os.path.join(E, 'results/method/fric/e07_verdicts.json'), 'w'), indent=1)
import collections
print('interface-shear verdicts (3 MPa, provisional):', dict(collections.Counter(d['verdict'] for d in ev.values())))
