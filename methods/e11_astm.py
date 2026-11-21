"""Read-out of the ASTM F2077-24 style rigid-block static tests (platform scripts/3_cage_case/h55_astm_f2077.py; PI 2026-11-19
item 2, decision 6). Per test: the load-displacement curve of the superior block, and
  stiffness   slope of the initial linear portion (F2077 3.2.16): least-squares line through the origin over the leading states whose
              secant stays within 5 % of the first secant, up to 25 % of the final displacement (>= 3 states; 2026-11-20 rule)
  offset yield 2 % offset (3.2.14: offset = 2 % of the intradiscal height; torsion 3.2.13: angular offset = 10 % of the intradiscal
              height / largest device dimension in the XZ plane, rad -> deg): first state where the curve falls below the offset
              line, interpolated; 'not reached' when the curve never crosses it (hyperelastic stiffening)
  ultimate    the maximum load if the curve has a peak before the end of the test, else 'not reached within D'
  PROXY loads (PI decision 6, named as proxies, NOT the standard's yield): the load at which the hard-phase von Mises stress
              (99th percentile over the pure hard-phase elements, e06 definition) first reaches the short-term strength proxy
              sig_hard and the sustained limit 0.18 x sig_hard (e06 limit_MPa), interpolated between states.
compression: displacement = -dz, load = -Fz of the block reaction sign-normalised; shear45: along the load axis (+X, -Z)/sqrt2;
torsion: twist step only (t >= 1), angle thz in deg, moment Mz in N mm.
usage: python e11_astm.py <astm_case_dir> <out.json>
"""
import sys, os, json, numpy as np, xml.etree.ElementTree as ET
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path[:0] = [os.path.join(E, 'common'), os.path.join(E, 'methods')]
import xplt, e06_hard_stress as e6
LIN_TOL = 0.05
PLAT = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026'


def rb_log(f):
    d, t = {}, None
    for line in open(f):
        if line.startswith('*Time'): t = float(line.split('=')[1])
        elif line[:1].isdigit() and t is not None: d[t] = np.array([float(v) for v in line.split(',')[1:]])
    return d


def interp_at(x, y, level):
    """first x where y reaches level (linear between samples), None if never."""
    for i in range(1, len(y)):
        if y[i - 1] < level <= y[i]: return float(x[i - 1] + (level - y[i - 1]) / (y[i] - y[i - 1]) * (x[i] - x[i - 1]))
    return None


def one(td, test, meta, sig_hard):
    lg = rb_log(os.path.join(td, 'block_sup.txt')); ts = sorted(lg); rows = []
    for t in ts:
        v = lg[t]                                                  # x y z thx thy thz Fx Fy Fz Mx My Mz
        if test == 'compression': d, F = None, -v[8]
        elif test == 'shear45': a = np.array([1, 0, -1]) / np.sqrt(2); F = -(v[6:9] @ a)
        else:
            if t < 1 - 1e-9: continue
            d, F = np.degrees(v[5]), -v[11]
        rows.append([t, v, F])
    # the superior block is rigid and its motion prescribed (linear in t): displacement = D x t (compression, shear45); torsion =
    # the logged block rotation thz of the twist step
    t_ = np.array([r[0] for r in rows]); V = np.array([r[1] for r in rows]); F = np.array([r[2] for r in rows])
    D = meta['D_mm'] * t_ if test != 'torsion' else np.degrees(V[:, 5])
    F = F * np.sign(F[-1]) if F[-1] != 0 else F
    D = np.concatenate([[0.0], D]); F = np.concatenate([[0.0], F])
    # 2026-11-20 (elastoplastic bench, PI decision 8): 'initial linear portion' = the leading states whose secant F/D stays within LIN_TOL of
    # the first state's secant, at most 25 % of the final displacement, at least the first 3 states (the old rule, D <= 25 % of D only, swept
    # yielded states into the fit once the hard phase yields at ~0.06 mm)
    sec = np.where(D > 0, F / np.where(D > 0, D, 1), np.nan); s1 = next((x for x in sec if np.isfinite(x) and x != 0), np.nan)
    m = np.zeros(len(D), bool); m[0] = True
    for i in range(1, len(D)):
        if D[i] <= 0: m[i] = True; continue
        if D[i] > 0.25 * D[-1] or abs(sec[i] / s1 - 1) > LIN_TOL: break
        m[i] = True
    if m.sum() < 4: m[:4] = True
    k = float(np.sum(D[m] * F[m]) / np.sum(D[m] ** 2)); k_old_rule = float(np.sum(D[D <= 0.25 * D[-1]] * F[D <= 0.25 * D[-1]]) / np.sum(D[D <= 0.25 * D[-1]] ** 2))
    h = meta['intradiscal_height_mm']
    if test == 'torsion':
        g0 = ET.parse(os.path.join(td, 'case.feb')).getroot().find('Geometry'); ids = {int(v) for eb in g0.findall('Elements') if eb.get('name').startswith('cage_') for e in eb for v in e.text.split(',')}
        XN = np.array([[float(v) for v in n.text.split(',')] for n in g0.find('Nodes') if int(n.get('id')) in ids])
        L = float(max(np.ptp(XN[:, 0]), np.ptp(XN[:, 2])))              # largest device dimension in the XZ plane (3.2.13)
        off = np.degrees(0.10 * h / L)
    else: off = 0.02 * h
    g = F - k * (D - off)                                             # >= 0 above the offset line
    y = None
    for i in range(1, len(D)):
        if D[i] > off and g[i] < 0:
            a = g[i - 1] / (g[i - 1] - g[i]); y = dict(disp=float(D[i - 1] + a * (D[i] - D[i - 1])), load=float(F[i - 1] + a * (F[i] - F[i - 1]))); break
    ip = int(np.argmax(F)); ult = dict(disp=float(D[ip]), load=float(F[ip])) if ip < len(F) - 1 else None
    # hard-phase stress per state (states of the twist step only for torsion)
    root = ET.parse(os.path.join(td, 'case.feb')).getroot(); hb, phi = e6.hard_blocks(root)
    pf = xplt.read(os.path.join(td, 'case.xplt')); st_t, p99, smax = [], [], []
    for st in pf['states']:
        if test == 'torsion' and st['time'] < 1 - 1e-9: continue
        vm = np.concatenate([e6.von_mises(st['elem']['stress'][b]) for b in hb if b in st['elem']['stress']])
        st_t.append(st['time']); p99.append(float(np.percentile(vm, 99))); smax.append(float(vm.max()))
    Dt = np.interp(st_t, np.concatenate([[0.0 if test != 'torsion' else 1.0], t_]), D)
    Ft = np.interp(st_t, np.concatenate([[0.0 if test != 'torsion' else 1.0], t_]), F)
    prox = {}
    for name, lev in (('short_term_sig_hard', sig_hard), ('sustained_0.18_sig_hard', 0.18 * sig_hard)):
        dl = interp_at(Dt, np.array(p99), lev); prox[name] = dict(level_MPa=lev, disp=dl, load=float(np.interp(dl, Dt, Ft)) if dl is not None else None)
        if dl is None and p99 and p99[0] >= lev: prox[name].update(disp=float(Dt[0]), load=float(Ft[0]), note='already reached at the start of the test segment (torsion: by the 100 N preload)')
    unit = ('deg', 'N mm') if test == 'torsion' else ('mm', 'N')
    return dict(test=test, units=dict(disp=unit[0], load=unit[1], stiffness=f'{unit[1]}/{unit[0]}'), stiffness=k, stiffness_fit=dict(rule=f'leading states with secant within {LIN_TOL:.0%} of the first, <= 25 % of D', n_states=int(m.sum()), d_max=float(D[m].max()), k_old_rule_25pct=k_old_rule), offset=float(off), offset_yield=y,
                ultimate=ult, final=dict(disp=float(D[-1]), load=float(F[-1])), hard_phase_proxy=prox, hard_phi=phi,
                curve=dict(disp=D.tolist(), load=F.tolist()), hard_vm=dict(t=st_t, p99=p99, max=smax),
                complete=bool(abs(t_[-1] - (2.0 if test == 'torsion' else 1.0)) < 1e-6))


def main(cd, out):
    meta = json.load(open(os.path.join(cd, 'astm.json')))
    prm = json.load(open(os.path.join(PLAT, meta['source'] + '_params.json'))); sig = float(prm.get('sig_hard', 15.0))
    res = dict(case=cd, source=meta['source'], intradiscal_height_mm=meta['intradiscal_height_mm'], sig_hard_MPa=sig, tests={})
    for t in ('compression', 'shear45', 'torsion'):
        td = os.path.join(cd, t)
        if not os.path.exists(os.path.join(td, 'block_sup.txt')): res['tests'][t] = None; continue
        try: res['tests'][t] = one(td, t, meta, sig)
        except Exception as ex: res['tests'][t] = dict(error=repr(ex)[:300])
    json.dump(res, open(out, 'w'), indent=1); return res


if __name__ == '__main__':
    r = main(sys.argv[1], sys.argv[2])
    for t, v in r['tests'].items():
        if not v or 'error' in v: print(t, v); continue
        print(t, 'k %.1f %s' % (v['stiffness'], v['units']['stiffness']), 'offset_yield', v['offset_yield'], 'ult', v['ultimate'], 'final', v['final'],
              'proxy', {k: (None if x['load'] is None else round(x['load'], 1)) for k, x in v['hard_phase_proxy'].items()}, 'complete', v['complete'])
