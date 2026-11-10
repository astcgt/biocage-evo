"""Read-out shift between the two friction laws on the SAME t 3.5 checkpoint, per (design, window), from results/method/fric/compare.json.

pairs (production law -> stick-memory law, PI 2026-11-09 decision 1 / 2026-11-10 item 1):
  physio_fric3 -> physio_fric5     production-inserted checkpoints; its abs_p90 is the fallback margin (fric_compare FALLBACK_MARGIN)
  physio_relG_pl -> physio_relG    process-G checkpoints (h51 fallback source and its controls); transfer check of that margin
value = the verdict read-out of the window (fric_compare rule): u_h at 1.5 N m when the window transmits it, else posterior at the intact ROM.
A pair counts only when both windows reached an evaluation point. Writes fric3_to_fric5_shift.json (format of the 2026-11-09 file; regenerated,
QA audit 2026-11-10 實作時自選: generator script) and relG_law_shift.json, prints both summaries.
usage: python ops/law_shift.py
"""
import os, json, time, numpy as np
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(E, 'results/method/fric')
rows = [r for r in json.load(open(os.path.join(OUT, 'compare.json'))) if 'note' not in r]
by = {(r['set'], r['design'], r['window']): r for r in rows}
def readout(r):
    if r.get('fric_reached'): return r['fric_translation_mm']
    if r.get('rom_reached'): return r['post_at_rom']
    return None
def shift(a, b, out, note):
    prs = []
    for (s_, p, w), ra in sorted(by.items()):
        if s_ != a: continue
        rb = by.get((b, p, w)); va, vb = readout(ra), readout(rb) if rb else None
        if va is None or vb is None: continue
        prs.append({'design': p, 'window': w, a.split('_')[-1]: va, b.split('_')[-1]: vb, 'delta': vb - va})
    d = np.array([x['delta'] for x in prs]) if prs else np.zeros(0)
    j = dict(generated=time.strftime('%Y-%m-%dT%H:%M'), note=note, n=len(prs), abs_median=float(np.median(abs(d))) if len(d) else None, abs_p90=float(np.percentile(abs(d), 90, method='higher')) if len(d) else None,   # 'higher': the p90 is an OBSERVED shift (the 2026-11-09 file's value; linear interpolation gives 0.0426)
             abs_max=float(abs(d).max()) if len(d) else None, rows=prs)
    json.dump(j, open(os.path.join(OUT, out), 'w'), indent=1)
    print(f"{out}: n {j['n']} abs_median {j['abs_median']} abs_p90 {j['abs_p90']} abs_max {j['abs_max']}")
    return j
shift('physio_fric3', 'physio_fric5', 'fric3_to_fric5_shift.json', 'read-out shift fric3 -> fric5, same design/window, usable in both; extension: posterior at ROM, flexion: u_h at 1.5 N m')
j = shift('physio_relG_pl', 'physio_relG', 'relG_law_shift.json', 'read-out shift production law (physio_relG_pl) -> stick-memory law (physio_relG) on the SAME process-G checkpoint, same design/window, usable in both (h51 controls); transfer check of the fric3->fric5 fallback margin')
f5 = json.load(open(os.path.join(OUT, 'fric3_to_fric5_shift.json')))
if j['n']: print(f"transfer: relG pairs within the fric3->fric5 distribution: abs_p90 {j['abs_p90']:.4f} vs margin {f5['abs_p90']:.4f}; max {j['abs_max']:.4f} vs {f5['abs_max']:.4f}")
