"""e06: hard-phase sustained stress read-out on a physio run or window (OBS-01 failure mode 'hard-phase sustained stress / creep').

PI 2026-11-03 item 7: threshold = 18 % of the short-term strength, SECONDARY indicator (read-out only; it does not enter the
design classes). Literature behind the 18 %: Smit / Engels / Govaert 2008 (Spine 33:14) and 2010 (J Mater Sci Mater Med 21:89):
PLLA under sustained load fails in ~1 day at 50 % of the short-term strength and the lifetime grows one decade per 14 MPa
drop; 18 % is the extrapolation to a 6-month support period (CAPABILITY_GAPS 2026-11-02 section 4.5, not the authors' number).
Short-term strength proxy: the hard-phase wet yield parameter sig_hard of the case (current_settings common, 15 MPa) until a
bench value exists -> limit_MPa = 0.18 * sig_hard (provisional, recorded in the output).
Measure of a state: 99th percentile (and max) of the von Mises Cauchy stress over the pure hard-phase cage elements (blocks
named cage_*_1.0; if a design has none, the blocks with the largest hard fraction). Sustained = the state at the end of the
follower-load ramp (t_follower[1], 3.5); window peak = max over the valid logged states up to the target bracket plus the
value interpolated to the target moment (e03.target_bracket, same convention as e05).
usage: python e06_hard_stress.py <case_dir> [out.json]     python e06_hard_stress.py --test
"""
import sys, os, json, numpy as np, xml.etree.ElementTree as ET
sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p) for p in ('common', 'methods')]
import e03_mu_req as e3
FRACTION, Q = 0.18, 99.0


def von_mises(s6):
    """FEBio symmetric stress rows (xx yy zz xy yz xz) -> von Mises."""
    s = np.asarray(s6, float)
    return np.sqrt(0.5 * ((s[:, 0] - s[:, 1]) ** 2 + (s[:, 1] - s[:, 2]) ** 2 + (s[:, 2] - s[:, 0]) ** 2) + 3 * (s[:, 3] ** 2 + s[:, 4] ** 2 + s[:, 5] ** 2))


def hard_blocks(root):
    names = [eb.get('name') for eb in root.find('Geometry').findall('Elements')]
    cage = [(i + 1, n) for i, n in enumerate(names) if n.startswith('cage') and 'biodisc' not in n]
    phi = {b: (float(n.rsplit('_', 1)[-1]) if n.rsplit('_', 1)[-1].replace('.', '', 1).isdigit() else 0.0) for b, n in cage}
    pmax = max(phi.values()) if phi else 0.0
    return [b for b in phi if phi[b] >= pmax - 1e-9], pmax


def main(cd, out=None):
    import xplt
    root = ET.parse(os.path.join(cd, 'case.feb')).getroot()
    blocks, pmax = hard_blocks(root)
    prm = json.load(open(os.path.join(cd, 'case.json'))) if os.path.exists(os.path.join(cd, 'case.json')) else {}
    prm = prm.get('params', prm); sig_hard = float(prm.get('sig_hard', 15.0)); limit = FRACTION * sig_hard
    states = xplt.read(os.path.join(cd, 'case.xplt'))['states']
    sch = json.load(open(os.path.join(cd, 'physio_schedule.json'))); br = e3.target_bracket(cd, sch)
    def meas(st):
        S = st['elem']['stress']; vm = np.concatenate([von_mises(S[b]) for b in blocks if b in S])
        return dict(p99=float(np.percentile(vm, Q)), max=float(vm.max()), n=int(len(vm))) if len(vm) else dict(p99=None, max=None, n=0)
    t_sus = sch['t_follower'][1]; sus = [s for s in states if abs(s['time'] - t_sus) < 1e-3]
    res = dict(hard_blocks=blocks, hard_phi=pmax, sig_hard_MPa=sig_hard, limit_MPa=limit, limit_rule='0.18 x sig_hard (PI 2026-11-03 item 7, secondary; short-term strength proxied by the wet yield parameter - provisional)',
               sustained=meas(sus[0]) if sus else None, t_sustained=t_sus, t_last=states[-1]['time'], windows={})
    for w in sch['windows']:
        k = br[w['name']]; ok_t = k['valid_times'] or [s['time'] for s in states]
        up = [s for s in states if w['t0'] + 1e-6 < s['time'] <= k['t_a'] + 1e-6 and any(abs(s['time'] - t) <= 1e-3 for t in ok_t)]
        vals = [meas(s)['p99'] for s in up]; mx = [meas(s)['max'] for s in up]
        if k['reached'] and k['frac'] > 0:
            sa, sb = e3.state_at(states, k['t_a']), e3.state_at(states, k['t_b'])
            if sb is not None:
                ma, mb = (meas(sa) if sa is not None else None), meas(sb)
                vals.append(ma['p99'] + k['frac'] * (mb['p99'] - ma['p99']) if ma else mb['p99']); mx.append(ma['max'] + k['frac'] * (mb['max'] - ma['max']) if ma else mb['max'])
        vals = [v for v in vals if v is not None]; mx = [v for v in mx if v is not None]
        res['windows'][w['name']] = dict(peak_p99=max(vals) if vals else None, peak_max=max(mx) if mx else None, reached=k['reached'], t_eval=k['t'], window_check=k['check'])
    pk = [v['peak_p99'] for v in res['windows'].values() if v['peak_p99'] is not None]
    res['peak_p99'] = max(pk) if pk else None
    res['within_sustained'] = None if not res['sustained'] or res['sustained']['p99'] is None else res['sustained']['p99'] <= limit
    res['within_peak'] = None if res['peak_p99'] is None else res['peak_p99'] <= limit
    res['provenance'] = e3.provenance(cd)
    if out: json.dump(res, open(out, 'w'), indent=1)
    return res


def selftest():
    """uniaxial sigma_xx = 2 -> von Mises 2; pure shear tau_xy = 1 -> sqrt(3); hydrostatic -> 0; p99 of 100 elements with one outlier."""
    vm = von_mises([[2, 0, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0], [-3, -3, -3, 0, 0, 0]]); ok = np.allclose(vm, [2, np.sqrt(3), 0])
    rows = np.zeros((100, 6)); rows[:, 0] = 1.0; rows[-1, 0] = 50.0; p = np.percentile(von_mises(rows), Q); ok &= 1.0 < p < 50.0
    print('von Mises', np.round(vm, 4), 'p99 with outlier', round(float(p), 3), 'SELFTEST', 'PASS' if ok else 'FAIL'); return bool(ok)


if __name__ == '__main__':
    if sys.argv[1] == '--test': sys.exit(0 if selftest() else 1)
    r = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps({k: v for k, v in r.items() if k != 'provenance'}, indent=1))
