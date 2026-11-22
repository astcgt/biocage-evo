"""Ratcheting read-out of a window_cycles window (PI 2026-11-19 test-gap item 4; S9: 3 cycles per direction, no progressive
accumulation). Cage translation = mean of the logged cage nodes minus the mean of the C4 endplate nodes (the e04 definition of
cage_translation), relative to the window start (t 3.5). Read at every return to neutral (t 3.5 + 2k) and at every flexion /
extension peak (t 4.0 + 2k / 5.0 + 2k). Posterior = -X.
Increment per cycle = translation at neutral k minus neutral k-1. Rule used for the reading (proposal, not a PI threshold):
ratcheting when the posterior increment does not shrink from cycle 2 to cycle 3 AND exceeds the replicate noise 0.005 mm (R20).
usage: python e10_cycles.py <w_flexion_dir> <out.json>
"""
import sys, os, json, numpy as np, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import e04_dislocation as e4
NOISE = 0.005          # replicate read-out noise (R20); kept for the old 'ratcheting' field
# 2026-11-22 time-step check (p124, same checkpoint: window_dt 0.001 against the production stepping, penalty x2, full Newton), compared at the
# SAME C3 angle: flexion loading agrees within 0.004 mm, but the sliding half cycle (extension loading and unloading) carries a stick-slip
# texture of +-0.02-0.03 mm whose phase depends on the time step, and the production stepping does not land on the turning point of the
# drive (largest applied angle 98.6-99.6 % of the peak). The state nearest the peak time is therefore not a stable read-out: the peak is read
# as the EXTREME of the posterior translation within +-HALF_WIN of the peak time, and the noise floor of that number is NOISE_PEAK.
# The return to neutral is better conditioned (arms agree within 0.003-0.007 mm): NOISE_NEUTRAL.
NOISE_PEAK = 0.03; NOISE_NEUTRAL = 0.01; HALF_WIN = 0.25
SHRINK = 0.7      # 'settling': each cycle-to-cycle change is at most 0.7 x the one before (proposal)
PLAT = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026'


def main(wd, out):
    sch = json.load(open(os.path.join(wd, 'physio_schedule.json'))); n = int(sch['windows'][0].get('cycles', sch.get('window_cycles', {}).get('n', 1)))
    cn = e4.read_log(os.path.join(wd, 'cage_nodes.txt')); c4 = e4.read_log(os.path.join(wd, 'C4_endplate_nodes.txt'))
    ts = sorted(t for t in cn if t >= 3.5 - 1e-6 and t in c4)
    tr = lambda t: np.array(list(cn[t].values())).mean(0) - np.array(list(c4[t].values())).mean(0)
    t_end = ts[-1]; u0 = tr(min(ts, key=lambda t: abs(t - 3.5))); base = 'log %.3f' % min(ts, key=lambda t: abs(t - 3.5))
    # 2026-11-19 (advisor): the window log starts at its first step (t 3.55 = 10 % into the flexion ramp); take the t 3.5 baseline
    # from the plot file (the restart appends to the insertion's xplt, so the t 3.5 state is there) with the same node sets
    # 2026-11-20: first the insertion run's own logs (the window's parent dir = h31 insertion, or params restart_source = h47
    # source): they hold the t 3.5 row of the same node sets, without reading a 10-20 GB plot file
    srcs = [os.path.dirname(os.path.abspath(wd))]
    try: srcs.append(os.path.join(PLAT, json.load(open(os.path.join(wd, 'case.json')))['params']['restart_source']))
    except (OSError, KeyError, ValueError): pass
    for sd in srcs:
        try:
            cn0 = e4.read_log(os.path.join(sd, 'cage_nodes.txt')); c40 = e4.read_log(os.path.join(sd, 'C4_endplate_nodes.txt'))
            k = min((t for t in cn0 if t in c40), key=lambda t: abs(t - 3.5))
            if abs(k - 3.5) < 1e-3:
                u0 = np.array(list(cn0[k].values())).mean(0) - np.array(list(c40[k].values())).mean(0); base = 'insertion log %.4f (%s)' % (k, os.path.relpath(sd, PLAT)); break
        except (OSError, ValueError): continue
    if base.startswith('insertion log'): pass
    else:
      try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'common')); import xplt
        ids = {nd.get('file'): np.array([int(v) for v in nd.text.split(',')]) for nd in ET.parse(os.path.join(wd, 'case.feb')).getroot().iter('node_data')}
        pf = xplt.read(os.path.join(wd, 'case.xplt')); st = min(pf['states'], key=lambda s: abs(s['time'] - 3.5))
        if abs(st['time'] - 3.5) < 1e-3:
            U = next(iter(st['node']['displacement'].values()))
            u0 = U[ids['cage_nodes.txt'] - 1].mean(0) - U[ids['C4_endplate_nodes.txt'] - 1].mean(0); base = 'xplt %.4f' % st['time']
      except (OSError, KeyError, ImportError) as ex: base += ' (xplt baseline failed: %r)' % ex
    tsa = np.array(ts); _U = None
    def at(t, interp=False):
        if t > t_end + 1e-3: return None
        k = min(ts, key=lambda a: abs(a - t)); u = tr(k) - u0; tk = k
        if interp and ts[0] < t < ts[-1]:                       # linear interpolation between the two bracketing states (neutral: smooth part of the drive)
            i = int(np.searchsorted(tsa, t)); a, b = ts[i - 1], ts[i]; fr = (t - a) / (b - a) if b > a else 0.0
            u = (1 - fr) * tr(a) + fr * tr(b) - u0; tk = t
        return dict(t=tk, t_nearest_state=k, u_mm=u.tolist(), posterior_mm=float(-u[0]), inplane_mm=float(np.hypot(u[0], u[1])))
    def extreme(tp, sign):
        # largest posterior (sign +1, extension) / anterior (sign -1, flexion) translation among the states within +-HALF_WIN of the peak time
        sel = [a for a in ts if tp - HALF_WIN <= a <= tp + HALF_WIN]
        if not sel or t_end < tp + HALF_WIN - 1e-3: return None   # the whole window around the peak must be computed
        k = max(sel, key=lambda a: sign * -(tr(a) - u0)[0]); u = tr(k) - u0
        return dict(t=k, posterior_mm=float(-u[0]), inplane_mm=float(np.hypot(u[0], u[1])), n_states=len(sel))
    neutral = [at(3.5 + 2 * k, interp=True) for k in range(n + 1)]
    if base.startswith(('xplt', 'insertion log')): neutral[0] = dict(t=3.5, u_mm=[0.0, 0.0, 0.0], posterior_mm=0.0, inplane_mm=0.0)   # the baseline state itself
    peaks = [dict(flexion=at(4.0 + 2 * k), extension=at(5.0 + 2 * k)) for k in range(n)]
    for k, p in enumerate(peaks):
        for w, tp, sg in (('flexion', 4.0 + 2 * k, -1), ('extension', 5.0 + 2 * k, 1)):
            if p[w] is not None: p[w]['extreme'] = extreme(tp, sg)
    inc = [None if (neutral[k] is None or neutral[k - 1] is None) else neutral[k]['posterior_mm'] - neutral[k - 1]['posterior_mm'] for k in range(1, n + 1)]
    done = [x for x in inc if x is not None]
    ratchet = None
    if len(done) >= 3: ratchet = bool(abs(done[2]) >= abs(done[1]) - 1e-9 and abs(done[2]) > NOISE)
    # PI 2026-11-22 (pending item 14, principle for S9): what matters is whether the cage reaches a STEADY STATE under repeated motion or keeps
    # moving with every cycle - 「如果本質穩定就不怕限制內的隨意運動」. Classification on the posterior translation at the extension peak of each cycle
    # (the state the dislocation limit is read at) and, as a second view, at the return to neutral:
    #   steady      the last two cycle-to-cycle changes are both within the read-out noise (NOISE)
    #   settling    the changes shrink by at least SHRINK each cycle; the geometric limit of the series is reported (projected_limit_mm)
    #   ratcheting  the changes do not shrink (constant or growing)
    # Proposal for the read-out; the pass rule itself is the PI's (to be fixed after the 8-cycle runs).
    def steady(series, noise):
        v = [x for x in series if x is not None]; d = [b - a for a, b in zip(v[:-1], v[1:])]
        if len(d) < 2: return dict(state=None, values=v, changes=d, noise_mm=noise, note='fewer than 3 cycles')
        if abs(d[-1]) <= noise and abs(d[-2]) <= noise: return dict(state='steady', values=v, changes=d, noise_mm=noise)
        r = [abs(b) / abs(a) if abs(a) > 1e-12 else None for a, b in zip(d[:-1], d[1:])]
        if all(x is not None and x <= SHRINK for x in r[-2:]) and (d[-1] > 0) == (d[-2] > 0):
            q = r[-1]; return dict(state='settling', values=v, changes=d, noise_mm=noise, shrink_ratio=q, projected_limit_mm=float(v[-1] + d[-1] * q / (1 - q)))
        return dict(state='ratcheting', values=v, changes=d, noise_mm=noise, last_ratio=r[-1], total_drift_mm=float(v[-1] - v[0]), drift_over_noise=float(abs(v[-1] - v[0]) / noise))
    ss_ext = steady([p['extension']['extreme']['posterior_mm'] if (p.get('extension') and p['extension'].get('extreme')) else None for p in peaks], NOISE_PEAK)
    ss_near = steady([p['extension']['posterior_mm'] if p.get('extension') else None for p in peaks], NOISE_PEAK)   # old read-out (state nearest the peak time), kept for comparison
    ss_neu = steady([x['posterior_mm'] if x else None for x in neutral[1:]], NOISE_NEUTRAL)
    res = dict(window=wd, baseline=base, cycles=n, t_end=t_end, completed_cycles=len(done), neutral=neutral, peaks=peaks, posterior_increment_per_cycle_mm=inc,
               steady_state=dict(at_extension_peak=ss_ext, at_neutral=ss_neu, at_extension_peak_nearest_state=ss_near, noise_peak_mm=NOISE_PEAK, noise_neutral_mm=NOISE_NEUTRAL, shrink=SHRINK,
                                 read_out='extension peak = extreme posterior translation within +-%.2f s of the peak time; neutral = linear interpolation at the return to neutral' % HALF_WIN,
                                 noise_basis='p124 time-step check 2026-11-22 (window_dt 0.001 vs production stepping vs penalty x2 vs full Newton, same checkpoint)',
                                 principle='PI 2026-11-22: a design that reaches a steady state under repeated motion is safe for any motion inside the limits; one that moves further with every cycle is not'),
               ratcheting=ratchet, rule=f'ratcheting = cycle-3 posterior increment >= cycle-2 increment and > {NOISE} mm (proposal)',
               max_inplane_mm=max((p[w]['inplane_mm'] for p in peaks for w in p if p[w]), default=None))
    json.dump(res, open(out, 'w'), indent=1); return res


if __name__ == '__main__':
    r = main(sys.argv[1], sys.argv[2])
    print(json.dumps({k: r[k] for k in ('cycles', 't_end', 'completed_cycles', 'posterior_increment_per_cycle_mm', 'ratcheting', 'max_inplane_mm')}))
    print('steady state at the extension peak:', json.dumps({k: (round(v, 4) if isinstance(v, float) else ([round(x, 4) for x in v] if isinstance(v, list) else v)) for k, v in r['steady_state']['at_extension_peak'].items()}))
