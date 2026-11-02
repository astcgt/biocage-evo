"""Soft-PLCL compression check on a physio_rot run (PI 2026-10-31, interim limits until bench data on our PLCL grades).

Rule (literature: no compression-set data for bulk PLCL; rubber-spring / elastomeric-bearing practice, PLCL relaxation ~30 %):
  sustained (after insertion, release and the 100 N follower load, t = 3.5): compression <= 15 %
  peak (any window, up to the state where the driving moment reaches the target 1.5 N m): compression <= 25 %
compression of an element = 1 - minimum principal stretch (from the Lagrange strain); the measure of a state is the worst
1 % (99th percentile) over the cage elements that contain soft PLCL (blocks not 100 % hard), robust to single distorted
elements at edges. A run that stopped early gives a lower bound for the windows it did not finish.
Evaluation states (2026-11-02): the window peak is the maximum over the valid logged states up to the target bracket and the
value interpolated to the target moment (e03.target_bracket: no overshoot; micro-step, rigid-body-residual (NUM-14) and jump
states excluded).
usage: python e05_compression.py <case_dir> [out.json]     python e05_compression.py --test
"""
import sys, os, json, numpy as np, xml.etree.ElementTree as ET
sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p) for p in ('common', 'methods')]
import e03_mu_req as e3
SUSTAINED, PEAK, Q = 0.15, 0.25, 99.0


def comp(e):
    """Lagrange strain rows (xx yy zz xy yz xz) -> 1 - minimum principal stretch."""
    e = np.asarray(e); C = np.empty((len(e), 3, 3))
    C[:, 0, 0], C[:, 1, 1], C[:, 2, 2] = 1 + 2 * e[:, 0], 1 + 2 * e[:, 1], 1 + 2 * e[:, 2]
    C[:, 0, 1] = C[:, 1, 0] = 2 * e[:, 3]; C[:, 1, 2] = C[:, 2, 1] = 2 * e[:, 4]; C[:, 0, 2] = C[:, 2, 0] = 2 * e[:, 5]
    return 1 - np.sqrt(np.clip(np.linalg.eigvalsh(C)[:, 0], 0, None))


def main(cd, out=None):
    import xplt
    root = ET.parse(os.path.join(cd, 'case.feb')).getroot()
    names = [eb.get('name') for eb in root.find('Geometry').findall('Elements')]
    soft = [i + 1 for i, n in enumerate(names) if n.startswith('cage') and not n.endswith('_1.0')]
    states = xplt.read(os.path.join(cd, 'case.xplt'))['states']
    sch = json.load(open(os.path.join(cd, 'physio_schedule.json'))); br = e3.target_bracket(cd, sch)
    meas = lambda st: float(np.percentile(np.concatenate([comp(st['elem']['Lagrange strain'][b]) for b in soft
                                                          if b in st['elem']['Lagrange strain']]), Q))
    t_sus = sch['t_follower'][1]
    sus = [s for s in states if abs(s['time'] - t_sus) < 1e-3]
    res = dict(sustained=meas(sus[0]) if sus else None, t_last=states[-1]['time'], windows={})
    for w in sch['windows']:
        # peak over the valid logged states up to the bracket's lower state, plus the value interpolated to the target
        # (2026-11-02: micro-step / jump states excluded, no overshoot; e03.target_bracket)
        k = br[w['name']]; ok_t = k['valid_times'] or [s['time'] for s in states]
        up = [s for s in states if w['t0'] + 1e-6 < s['time'] <= k['t_a'] + 1e-6 and any(abs(s['time'] - t) <= 1e-3 for t in ok_t)]
        vals = [meas(s) for s in up]
        if k['reached'] and k['frac'] > 0:
            sa, sb = e3.state_at(states, k['t_a']), e3.state_at(states, k['t_b'])
            if sb is not None: vals.append(meas(sa) + k['frac'] * (meas(sb) - meas(sa)) if sa is not None else meas(sb))
        res['windows'][w['name']] = dict(peak=max(vals) if vals else None, reached=k['reached'], t_eval=k['t'], window_check=k['check'])
    pk = [v['peak'] for v in res['windows'].values() if v['peak'] is not None]
    res['peak'] = max(pk) if pk else None
    res['pass_sustained'] = None if res['sustained'] is None else res['sustained'] <= SUSTAINED
    res['pass_peak'] = None if res['peak'] is None else res['peak'] <= PEAK
    res['provenance'] = e3.provenance(cd)
    if out: json.dump(res, open(out, 'w'), indent=1)
    return res


def selftest():
    """comp(): uniaxial stretch lambda_z = 0.8 (E_zz = (0.64 - 1)/2 = -0.18) -> 20 % compression; a 30 deg rotated copy of
    the same strain gives the same value (principal stretch is frame-independent); plus the e03 bracket tests."""
    E = np.array([[0, 0, -0.18, 0, 0, 0.0]]); c1 = comp(E)[0]
    th = np.radians(30); R = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1.0]])
    Em = np.zeros((3, 3)); Em[2, 2] = -0.18; R2 = np.array([[1, 0, 0], [0, np.cos(th), -np.sin(th)], [0, np.sin(th), np.cos(th)]])
    Er = R2 @ Em @ R2.T; c2 = comp(np.array([[Er[0, 0], Er[1, 1], Er[2, 2], Er[0, 1], Er[1, 2], Er[0, 2]]]))[0]
    ok = abs(c1 - 0.2) < 1e-9 and abs(c2 - 0.2) < 1e-9
    print(f'comp uniaxial 0.8     got {c1:.6f} want 0.200000; rotated {c2:.6f}')
    ok &= e3.bracket_selftest()
    print('SELFTEST', 'PASS' if ok else 'FAIL'); return ok


if __name__ == '__main__':
    if sys.argv[1] == '--test': sys.exit(0 if selftest() else 1)
    r = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None); r.pop('provenance'); print(json.dumps(r, indent=1))
