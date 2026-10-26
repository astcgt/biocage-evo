"""Credibility gate 2 (intact C3-C4 segment): GPU Newton solver vs the FEBio 4 reference runs of the refined FSU.

The same .feb as the reference (snapshot/reference/fsu_intact/<direction>/fsu.feb: prestrain t 0-1, 1.5 N m pure moment
on the C3 potting t 1-2) is read and solved by gpufe.newton with FEBio's own convergence tolerances; the C3 rigid-body
rotation history is compared with FEBio's C3pot_rigid.txt at the same times, plus the facet contact force at the end.
Pass: main-axis rotation at t = 2 within 5 % of FEBio (and every output time within 5 % of the end value); facet force
reported (FEBio uses augmented Lagrangian facets, this solver plain penalty, so a small difference is expected).
usage: python gate2_fsu.py <direction> [increments]   (direction: flex_pos_y flex_neg_y lb_pos_x lb_neg_x ar_pos_z ar_neg_z)
"""
import os, sys, json, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feb, model as mdl, newton
from paths import SNAP, RESULTS

OUT = os.path.join(RESULTS, 'gpufe_verify/gate2')
AXIS = dict(x=0, y=1, z=2)


def read_rigid(path):
    """FEBio rigid-body log: list of (t, [x y z thx thy thz Mx My Mz])."""
    out, t = [], None
    for line in open(path):
        if line.startswith('*Time'): t = float(line.split('=')[1])
        elif line[:1].isdigit() and t is not None: out.append((t, [float(v) for v in line.split(',')[1:]]))
    return out


def main():
    d = sys.argv[1]; inc = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    ax = AXIS[d[-1]]; ref_dir = os.path.join(SNAP, 'reference/fsu_intact', d)
    ref = read_rigid(os.path.join(ref_dir, 'C3pot_rigid.txt'))
    t0 = time.time(); m = feb.read(os.path.join(ref_dir, 'fsu.feb')); M = mdl.build(m)
    s = newton.NewtonSolver(M, dict(verbose=True, increments_per_step=inc))
    print('setup', round(time.time() - t0, 1), 's', flush=True)
    hist = s.run()
    tg = np.array([h['t'] for h in hist]); thg = np.array([h['rigid'][2]['th'][ax] for h in hist])
    rt = np.array([r[0] for r in ref]); rth = np.array([r[1][3 + ax] for r in ref])
    end_ref, end_gpu = float(rth[-1]), float(thg[-1])
    mom = rt >= 1.0                                                   # moment phase: compare at FEBio's output times
    dev = np.abs(np.interp(rt[mom], tg, thg) - rth[mom]) / abs(end_ref)
    fac = {}
    for p in s.passes:
        if p.kind == 'sliding' and p.name not in fac: fac[p.name] = float(p.force_t.norm(dim=-1).sum())   # first (primary) pass
    rep = dict(direction=d, increments=inc, gpu_end_rot_deg=np.degrees(end_gpu), febio_end_rot_deg=np.degrees(end_ref),
               end_rel_err=abs(end_gpu - end_ref) / abs(end_ref), max_curve_dev_of_end=float(dev.max()),
               facet_force_gpu_N=fac, newton_iters=[h['iters'] for h in hist], seconds=time.time() - t0,
               PASS=bool(abs(end_gpu - end_ref) / abs(end_ref) < 0.05 and dev.max() < 0.05), history=hist)
    os.makedirs(OUT, exist_ok=True); json.dump(rep, open(os.path.join(OUT, d + '.json'), 'w'), indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != 'history'}), flush=True)


if __name__ == '__main__':
    main()
