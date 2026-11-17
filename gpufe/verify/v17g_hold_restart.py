"""V17(g): restart hold pilots (DECISIONS 2026-11-07/08). The extension (or flexion) hold window restarted from the t 3.5 checkpoints
of pilot_holdA (coarse hold, dtmax 0.05) and pilot_holdE (fine hold, dtmax 0.002) with the patch-6/7 FEBio build; arms per design:
ctl (options off = production law), sm (BIOCAGE_STICK_MEMORY=1), smR (sm + window min_residual 1e-4), al (BIOCAGE_CAGE_LAUGON=0.2,10).
Reports, per window: state, iterations, augmentations, retries, translation at the start and end of the hold (cage relative to C4,
e04 metric), start-to-end drift, and the TREND statistics over the settled hold t 3.95-4.4 (linear-fit slope x hold length,
first / last quarter means, peak-to-peak, std, up / down step counts) - the fine dynamic holds oscillate, so start-to-end
differences are phase samples and the trend is the creep measure. Writes results/gpufe_verify/v2/v17g_hold_restart.json.
usage: python v17g_hold_restart.py [window=extension]"""
import os, sys, re, json, numpy as np
from prov import AL, ROOT, provenance, save
sys.path[:0] = [os.path.join(ROOT, 'methods'), os.path.join(ROOT, 'common')]
import e04_dislocation as e4
WIN = sys.argv[1] if len(sys.argv) > 1 else 'extension'
T0, T1, TS = 3.9, 4.4, 3.95            # hold start / end; settled part starts at TS
REF = [('pilot_holdA', 'p062_gpu1'), ('pilot_holdA', 'p139_gpu2'), ('pilot_holdE', 'p062_gpu1'), ('pilot_holdE', 'p139_gpu2'),
       ('pilot_holdQ', 'p062_gpu1'), ('pilot_holdQ', 'p139_gpu4')]   # pilot_holdQ (2026-11-18): true half-step hold (deck dtmax 0.025 over the hold), joint-driven production-law windows (h18)
ONE_ARM = ('pilot_holdR', 'pilot_holdRh', 'pilot_holdQR')   # route-E + stick-memory classes: one arm, cases carry no arm suffix; pilot_holdQR = half-step hold restarted from pilot_holdQ
ARMS = [(c, d) for c in ('pilot_holdH', 'pilot_holdHf') + ONE_ARM if os.path.isdir(os.path.join(AL, c))
        for d in sorted(os.listdir(os.path.join(AL, c))) if re.match(r'p\d+_[a-zA-Z0-9]+$' if c not in ONE_ARM else r'p\d+$', d)]   # pilot_holdR cases carry no arm suffix (one arm: route E + stick memory)
rep = dict(prov=provenance(), window=WIN, note='trend = linear-fit slope x 0.5 over t 3.95-4.4; fine dynamic holds oscillate (elastic stick contact + '
           '1e-6 density segment, no damping once the friction law stops dissipating), so start/end differences are phase samples', rows=[])
for c, dn in REF + ARMS:
    cd = os.path.join(AL, c, dn, 'w_' + WIN); log = cd + '/case.log'
    if not os.path.exists(log) or os.path.getsize(log) == 0 or not os.path.exists(cd + '/cage_nodes.txt'): continue
    txt = open(log, errors='ignore').read(); st = 'NORMAL' if 'N O R M A L' in txt[-4000:] else ('ERROR' if 'E R R O R' in txt[-4000:] else 'running')
    lj = os.path.join(AL, c, dn, 'launch' + ('' if WIN == 'extension' else '_' + WIN) + '.json'); lj = json.load(open(lj)) if os.path.exists(lj) else {}   # h47 writes launch_<window>.json per window
    cn = e4.read_log(cd + '/cage_nodes.txt'); c4 = e4.read_log(cd + '/C4_endplate_nodes.txt'); ts = sorted(cn.keys())
    U = {t: np.array(list(e4.nearest(cn, t)[0].values())).mean(0) - np.array(list(e4.nearest(c4, t)[0].values())).mean(0) for t in ts}
    H = {t: float(np.hypot(*U[t][:2])) for t in ts}
    hold = [t for t in ts if t >= T0 - 1e-6]; sett = [t for t in ts if t >= TS - 1e-6]
    r = dict(set=c, dir=dn, state=st, iters=len(re.findall(r'Nonlinear solution status', txt)), augs=len(re.findall(r'sliding interface #', txt)),
             retries=len(re.findall(r'Retrying', txt)), t_last=round(ts[-1], 4), env=lj.get('env', {}), febio_sha256=lj.get('febio_sha256'), lib_sha256=lj.get('lib_sha256'),
             u_ramp_end=round(H[min(ts, key=lambda t: abs(t - T0))], 4), n_hold=max(0, len(hold) - 1),
             u_start=round(H[hold[0]], 4) if hold else None, u_end=round(H[hold[-1]], 4) if hold else None,
             drift_start_end=round(H[hold[-1]] - H[hold[0]], 4) if len(hold) > 1 else None)
    if len(sett) > 3:
        t = np.array(sett); h = np.array([H[x] for x in sett]); d = np.diff(h); q = max(1, len(t) // 4)
        r.update(trend_per_hold=round(float(np.polyfit(t, h, 1)[0]) * (T1 - T0), 4), mean_first_q=round(float(h[:q].mean()), 4), mean_last_q=round(float(h[-q:].mean()), 4),
                 peak_to_peak=round(float(h.max() - h.min()), 4), std=round(float(h.std()), 4), steps_up=int((d > 0).sum()), steps_down=int((d < 0).sum()))
    rep['rows'].append(r)
    print(f"{c:12s}{dn:11s}{st:8s} it {r['iters']:5d} aug {r['augs']:4d} rt {r['retries']:2d} hold n {r['n_hold']:3d} u {r['u_start']} -> {r['u_end']} "
          f"start-end {r['drift_start_end']}  trend {r.get('trend_per_hold')}  pp {r.get('peak_to_peak')}  up/down {r.get('steps_up')}/{r.get('steps_down')}")
print('saved', save('v17g_hold_restart' + ('' if WIN == 'extension' else '_' + WIN), rep))
