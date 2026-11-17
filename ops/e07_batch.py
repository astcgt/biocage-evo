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
SETS = ('physio_fric3', 'physio_fric5', 'physio_relG_pl', 'physio_relG', 'physio_fric5r', 'physio_relGr'); RANK = {s_: i for i, s_ in enumerate(SETS)}   # physio_relG_pl (2026-11-10 17:xx): production-law fallback source of the process-G windows, ranked below physio_relG   # 2026-11-09 (PI decision 1): fric5 = the same windows recomputed with the stick-memory law; it supersedes fric3 per (design, window) in the shear gate too
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
                rec[f'{cls}_{key}_at_rom'] = float(np.interp(tr, t, v)); rec[f'{cls}_{key}_max_to_rom'] = float(max(np.nanmax(v[m]) if m.any() else -np.inf, np.interp(tr, t, v)))   # audit D-20261118-1: the ROM state itself (interpolated) belongs to 'up to the ROM'
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
best = {}; sets_of = {}
for r in out:                                    # per (design, window) the highest-ranked set THAT REACHED THE INTACT ROM wins (fric5 over fric3), as in fric_compare
    k = (r['design'], r['window']); sets_of.setdefault(k, set()).add(r['set']); cur = best.get(k)
    # PI 2026-11-11 decision 6: a fallback window (production-law restart of the same checkpoint - physio_relG_pl for process G, physio_fric3 where the
    # physio_fric5 window stopped) counts in the shear gate when the stick-law window did not reach the intact ROM; it is flagged below. Before, the
    # higher-ranked stick-law row (not at ROM) blocked the slot and the design stayed open.
    if cur is None or (bool(r.get('rom_reached')), RANK[r['set']]) > (bool(cur.get('rom_reached')), RANK[cur['set']]): best[k] = r
ev = {}
for r in [best[k] for k in sorted(best)]:
    d = ev.setdefault(r['design'], dict(verdict=None, reasons=[], windows={}, missing=[]))
    if not r.get('rom_reached'): continue
    v = max(x for x in (r.get('horizontal_shear_p99_at_rom'), r.get('vertical_shear_p99_at_rom')) if x is not None)
    k = (r['design'], r['window']); fb = r['set'] == 'physio_relG_pl' or (r['set'] == 'physio_fric3' and 'physio_fric5' in sets_of[k])   # production-law window used because the stick-law one did not reach the ROM
    d['windows'][r['window']] = dict(set=r['set'], case_dir=r['case_dir'], shear_p99_at_rom=round(v, 3), horizontal=r.get('horizontal_shear_p99_at_rom'), vertical=r.get('vertical_shear_p99_at_rom'),
                                     window_drive=('relative prescribed rotation of the C3 pot (route E, PI 2026-11-11 1a)' if r['set'] in ('physio_fric5r', 'physio_relGr') else 'absolute rigid joint (snaps C3 to its t=0 orientation at activation)'),   # S8 2026-11-17: provenance as in fric_compare
                                     fallback=fb, **({'fallback_note': 'PI 2026-11-11 decision 6: production-law window of the same checkpoint; no law-shift margin exists for the shear metric (not quantified), flagged only'} if fb else {}),
                                     peel_max_at_rom=max(x for x in (r.get('horizontal_peel_max_at_rom'), r.get('vertical_peel_max_at_rom')) if x is not None))
    if v > THR: d['reasons'].append(f"{r['window']}@ROM shear p99 {v:.1f} MPa > {THR}")
    # PI 2026-11-18 「如果可以完整跑完模擬，就紀錄最大需要承受的剪力」: the required interface strength of the design = the largest soft-side
    # interface shear seen anywhere in a window that ran to the intact ROM (p99 statistic as the gate metric, and the absolute maximum), with the window.
    _p99 = [x for x in (r.get('horizontal_shear_p99_max_to_rom'), r.get('vertical_shear_p99_max_to_rom')) if x is not None]
    _mx = [x for x in (r.get('horizontal_shear_max_max_to_rom'), r.get('vertical_shear_max_max_to_rom')) if x is not None]
    d['windows'][r['window']].update(shear_p99_max_to_rom=round(max(_p99), 3) if _p99 else None, shear_max_to_rom=round(max(_mx), 3) if _mx else None)
for p, d in ev.items():
    d['missing'] = [w for w in REQ if w not in d['windows']]
    d['verdict'] = 'fail' if d['reasons'] else ('open' if d['missing'] else 'pass')
    _w = [(w, x['shear_p99_max_to_rom']) for w, x in d['windows'].items() if x.get('shear_p99_max_to_rom') is not None]
    d['shear_req_p99_MPa'] = max(v for _, v in _w) if _w else None; d['shear_req_window'] = max(_w, key=lambda t: t[1])[0] if _w else None
    d['shear_req_max_MPa'] = max((x['shear_max_to_rom'] for x in d['windows'].values() if x.get('shear_max_to_rom') is not None), default=None)
    d['shear_req_complete'] = not d['missing']   # both required windows ran to the intact ROM: the required strength covers the whole physiological range
    if d['verdict'] == 'open': d['open_reason'] = 'window(s) ' + ', '.join(d['missing']) + ' did not reach the intact ROM (or missing)'
meta = dict(shear_req='PI 2026-11-18: shear_req_p99_MPa / shear_req_max_MPa = largest soft-side interface shear (p99 statistic / absolute max) over the completed windows up to the intact ROM, with its window; shear_req_complete = both required windows completed; the 3 MPa threshold stays as recorded (gate or flag: PI decision pending)', threshold_MPa=THR, metric='soft-side p99 interface shear at the intact-ROM state, max of layer and band-boundary interfaces, flexion and extension (frictional runs; physio_fric5 stick-memory windows supersede physio_fric3 per design and window, PI 2026-11-09 decision 1)',
            provisional='PI 2026-11-04: threshold provisional, pending bond-strength test of the co-printed PLCL hard / soft interface', decided='PI 2026-11-04; PI 2026-11-11 decision 6: fallback (production-law) windows count, flagged fallback=True')
json.dump(dict(meta=meta, designs=ev), open(os.path.join(E, 'results/method/fric/e07_verdicts.json'), 'w'), indent=1)
import collections
print('interface-shear verdicts (3 MPa, provisional):', dict(collections.Counter(d['verdict'] for d in ev.values())))
