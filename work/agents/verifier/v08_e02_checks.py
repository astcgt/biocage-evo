"""Verifier r0003, V08: checks of methods/e02_friction_limit.py (friction_limit LP) against closed-form limits, and the size of
the error from using reference-configuration face normals with current-configuration Cauchy stress (e02 lines 50-53, 66-67).
usage: python work/agents/verifier/v08_e02_checks.py   -> v08_e02_checks.json
(a) uniform pressure on a disc of radius R, total normal force N:
    pure shear F      -> mu = F / N
    pure twist T      -> mu = 3 T / (2 N R)            (uniform-pressure disc: T_max = 2/3 mu N R)
    16-gon inscribed  -> at most 1 / cos(pi/16) - 1 = 1.96 % above the exact value (conservative)
(b) face rotated by theta relative to the reference: the normal used is the reference one, traction t = -p n' (pure pressure,
    zero true shear). Spurious shear = p sin(theta); spurious mu_force = tan(theta) (shear / normal); compare with mu 0.3.
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); P = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(P, 'methods'))
from e02_friction_limit import friction_limit

R, N = 5.0, 100.0
g = np.linspace(-R, R, 81); X, Y = np.meshgrid(g, g); m = X**2 + Y**2 <= R**2
c = np.c_[X[m], Y[m]]; c = c - c.mean(0); A = (g[1] - g[0])**2
Pi = np.full(len(c), N / len(c)); Reff = np.sqrt(len(c) * A / np.pi)       # radius of the discretised disc (same area)
out = dict(n_points=int(len(c)), R_eff=Reff, cases=[])
for F, ang, T in ((10.0, 0.0, 0.0), (10.0, np.pi / 16, 0.0), (10.0, 0.3, 0.0), (0.0, 0.0, 100.0)):
    mu = friction_limit(c, Pi, np.array([F * np.cos(ang), F * np.sin(ang)]), T)
    exact = F / N if T == 0 else 3 * T / (2 * N * Reff)
    out['cases'].append(dict(F=F, angle=ang, T=T, mu_lp=mu, mu_exact=exact, rel=(mu - exact) / exact))
# combined shear + twist: LP must be >= each pure value and <= their sum (limit surface is convex)
mu_s = friction_limit(c, Pi, np.array([10.0, 0.0]), 0.0); mu_t = friction_limit(c, Pi, np.zeros(2), 100.0)
mu_c = friction_limit(c, Pi, np.array([10.0, 0.0]), 100.0)
out['combined'] = dict(mu_shear=mu_s, mu_twist=mu_t, mu_combined=mu_c, ok=bool(max(mu_s, mu_t) - 1e-9 <= mu_c <= mu_s + mu_t + 1e-9))
out['rotated_normal'] = [dict(theta_deg=t, spurious_mu=float(np.tan(np.radians(t))), fraction_of_mu_0p3=float(np.tan(np.radians(t)) / 0.3))
                         for t in (1, 2, 3, 5, 5.78)]
json.dump(out, open(os.path.join(HERE, 'v08_e02_checks.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
