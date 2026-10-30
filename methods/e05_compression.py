"""Soft-PLCL compression check on a physio_rot run (PI 2026-10-31, interim limits until bench data on our PLCL grades).

Rule (literature: no compression-set data for bulk PLCL; rubber-spring / elastomeric-bearing practice, PLCL relaxation ~30 %):
  sustained (after insertion, release and the 100 N follower load, t = 3.5): compression <= 15 %
  peak (any window, up to the state where the driving moment reaches the target 1.5 N m): compression <= 25 %
compression of an element = 1 - minimum principal stretch (from the Lagrange strain); the measure of a state is the worst
1 % (99th percentile) over the cage elements that contain soft PLCL (blocks not 100 % hard), robust to single distorted
elements at edges. A run that stopped early gives a lower bound for the windows it did not finish.
usage: python e05_compression.py <case_dir> [out.json]
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
    sch = json.load(open(os.path.join(cd, 'physio_schedule.json'))); tt = e3.target_times(cd, sch)
    meas = lambda st: float(np.percentile(np.concatenate([comp(st['elem']['Lagrange strain'][b]) for b in soft
                                                          if b in st['elem']['Lagrange strain']]), Q))
    t_sus = sch['t_follower'][1]
    sus = [s for s in states if abs(s['time'] - t_sus) < 1e-3]
    res = dict(sustained=meas(sus[0]) if sus else None, t_last=states[-1]['time'], windows={})
    for w in sch['windows']:
        tgt, reached, _ = tt[w['name']]
        up = [s for s in states if w['t0'] + 1e-6 < s['time'] <= min(tgt, w['t_peak']) + 1e-6]
        res['windows'][w['name']] = dict(peak=max(meas(s) for s in up) if up else None, reached=reached, t_eval=tgt)
    pk = [v['peak'] for v in res['windows'].values() if v['peak'] is not None]
    res['peak'] = max(pk) if pk else None
    res['pass_sustained'] = None if res['sustained'] is None else res['sustained'] <= SUSTAINED
    res['pass_peak'] = None if res['peak'] is None else res['peak'] <= PEAK
    res['provenance'] = e3.provenance(cd)
    if out: json.dump(res, open(out, 'w'), indent=1)
    return res


if __name__ == '__main__':
    r = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None); r.pop('provenance'); print(json.dumps(r, indent=1))
