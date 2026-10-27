"""Credibility gate 1d (stick memory, finding F-0003): a sticking interface must not creep under cyclic shear.

The gate 1c block pair (mu 0.5) is pressed (t 0-0.25), then the top face is moved along x 0 -> a -> 0 three times
(t 0.25-1), with a small enough that the interface sticks throughout (|Fx| < mu |Fz|). With stick memory (a sticking node
keeps its stick point across increments: Coulomb's law) the tangential force returns to zero at the end of every cycle
whatever the increment size; with re-anchoring every increment (the old GPU rule, and also FEBio 4's own rule:
FESlidingElasticInterface::Update projects before InitSlidingSurface) a residual force builds up. Runs the GPU Newton solver with 10 / 20 / 40 increments per half cycle, current rule and
(for the record) the old rule.
Pass (current rule): stick throughout, and |Fx / Fz| at every cycle end < 1e-3 for all increment counts.
"""
import os, sys, json, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feb, model as mdl, newton, contact
from gate1c_friction import write
from paths import RESULTS

OUT = os.path.join(RESULTS, 'gpufe_verify/gate1d')
MU, AMP, PRESS = 0.5, 0.004, 0.02


def case(path, n):
    """gate 1c geometry; control and load curves replaced for press + 3 shear cycles, n increments per half cycle."""
    write(path, MU, drag=AMP, press=PRESS)
    s = open(path).read(); h = 0.125 / n
    a = s.index('<time_steps>'); b = s.index('</step_size>') + len('</step_size>')
    s = s[:a] + f'<time_steps>{int(round(1 / h))}</time_steps><step_size>{h}</step_size>' + s[b:]
    lc2 = '<point>0,0</point><point>0.25,0</point>' + ''.join(f'<point>{0.25 + 0.25 * c + 0.125},1</point><point>{0.5 + 0.25 * c},0</point>' for c in range(3))
    a = s.index('<loadcurve id="1"'); b = s.index('</LoadData>')
    s = s[:a] + '<loadcurve id="1" type="linear"><point>0,0</point><point>0.25,1</point><point>1,1</point></loadcurve>' \
        f'<loadcurve id="2" type="linear">{lc2}</loadcurve>' + s[b:]
    open(path, 'w').write(s)


def legacy_set_anchor(self, x):                                       # the rule before the F-0003 fix
    tri, L, q, nrm, d = self.project(x)
    self.anchor_tri, self.anchor_L, self.anchor_ok = tri, L, d < self.R


def run(n, legacy):
    d = os.path.join(OUT, f'n{n}'); os.makedirs(d, exist_ok=True); fp = os.path.join(d, 'case.feb'); case(fp, n)
    keep = contact.Pass.set_anchor
    if legacy: contact.Pass.set_anchor = legacy_set_anchor
    try:
        m = feb.read(fp); M = mdl.build(m)
        top = np.array(m['nodesets']['top'])
        s = newton.NewtonSolver(M, dict(verbose=False, dtol=1e-6, etol=1e-8))
        rows = []
        def cb(sol, row):
            r = sol.residual(sol.x).cpu().numpy()[top].sum(0)
            p = sol.passes[0]; inc = p.force_n > 0
            rows.append(dict(t=round(sol.t, 6), Fx=float(r[0]), Fz=float(r[2]), stick=float(p.stick[inc].float().mean()) if bool(inc.any()) else 0.0))
        s.run(on_increment=cb)
    finally:
        contact.Pass.set_anchor = keep
    ends = [r for r in rows if any(abs(r['t'] - te) < 1e-9 for te in (0.5, 0.75, 1.0))]
    shear = [r for r in rows if r['t'] > 0.25 + 1e-9]
    res = dict(n=n, legacy_rule=legacy, cycle_end_Fx_over_Fz=[abs(r['Fx'] / r['Fz']) for r in ends],
               max_Fx_over_Fz=max(abs(r['Fx'] / r['Fz']) for r in shear), min_stick_frac=min(r['stick'] for r in shear), rows=rows)
    res['passed'] = bool(max(res['cycle_end_Fx_over_Fz']) < 1e-3 and res['min_stick_frac'] > 0.999 and res['max_Fx_over_Fz'] < MU)
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    cases = [run(n, False) for n in (10, 20, 40)] + [run(n, True) for n in (10, 20, 40)]
    rep = dict(gate='1d stick memory: cyclic shear below the friction limit', all_passed=all(c['passed'] for c in cases if not c['legacy_rule']), cases=cases)
    json.dump(rep, open(os.path.join(OUT, 'gate1d_report.json'), 'w'), indent=1)
    for c in cases:
        print(f"{'re-anchor (old / FEBio) rule' if c['legacy_rule'] else 'stick-memory rule'} n {c['n']:3d}: cycle-end |Fx/Fz| {np.round(c['cycle_end_Fx_over_Fz'], 5).tolist()} "
              f"max |Fx/Fz| {c['max_Fx_over_Fz']:.3f} min stick {c['min_stick_frac']:.3f} {'PASS' if c['passed'] else 'FAIL'}")
    print('ALL PASSED' if rep['all_passed'] else 'SOME FAILED')


if __name__ == '__main__':
    main()
