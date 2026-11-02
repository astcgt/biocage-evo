"""Safety guard r0003: 'watermelon-seed' push of the endplate wedge on a contour-matched cage.
Uniform clamp pressure p on both cage faces (top = C3 endplate surface, bottom = C4) inside the 1 mm inset footprint
(optionally only inside a sub-region). Net in-plane force from the inclined normals / net normal force = the friction
coefficient needed just to hold the cage against the clamp alone (no physiological load). Sign: Fx < 0 = posterior (toward the cord).
Frame: +X anterior, +Z superior (snapshot/model/frame_c3c4.json). Read-only.
Run from repo root: python work/agents/safety/s05_wedge_squeeze.py -> s05_wedge_squeeze.json
"""
import json, sys
import numpy as np
sys.path.insert(0, 'common')
from cage_geom import Endplates
import shapely.geometry as sg
ep = Endplates('snapshot/model/C34_fsu_refined.feb', 'snapshot/model/frame_c3c4.json')
h = 0.2
x0, y0, x1, y1 = ep.footprint.bounds
xs, ys = np.meshgrid(np.arange(x0, x1, h) + h / 2, np.arange(y0, y1, h) + h / 2)
X, Y = xs.ravel(), ys.ravel()
ins = np.array([ep.footprint.contains(sg.Point(a, b)) for a, b in zip(X, Y)])
X, Y = X[ins], Y[ins]
e = 0.05
def grad(f):
    return ((f(X + e, Y) - f(X - e, Y)) / (2 * e), (f(X, Y + e) - f(X, Y - e)) / (2 * e))
tx, ty = grad(ep.z_top); bx, by = grad(ep.z_bot)
# pressure on the cage top face from C3 acts downward along the C3 surface normal: n_top(outward of cage) = (-tx,-ty,1)/|.|,
# force on cage = -p n_top dA_true; dA_true = |(-tx,-ty,1)| dA_proj -> F = -p (-tx,-ty,1) dA_proj = p (tx, ty, -1) dA_proj
# bottom face: outward normal of cage = (bx,by,-1)/|.| -> F = -p (bx,by,-1) dA_proj = p (-bx,-by,1) dA_proj
A = h * h
gap = ep.z_top(X, Y) - ep.z_bot(X, Y)
def region(sel, name):
    Ft = np.array([tx[sel].sum(), ty[sel].sum(), -sel.sum()]) * A   # per unit p
    Fb = np.array([-bx[sel].sum(), -by[sel].sum(), sel.sum()]) * A
    Fn = sel.sum() * A
    net = Ft + Fb
    return dict(region=name, area_mm2=round(float(Fn), 2), net_Fx_over_N=round(float(net[0] / Fn), 4),
                net_Fy_over_N=round(float(net[1] / Fn), 4), top_face_Fx_over_N=round(float(Ft[0] / Fn), 4),
                bottom_face_Fx_over_N=round(float(Fb[0] / Fn), 4),
                mu_needed_clamp_only=round(float(np.hypot(net[0], net[1]) / (2 * Fn)), 4),
                note='mu = |net in-plane| / (2 faces x normal force); Fx<0 posterior')
res = [region(np.ones_like(X, bool), 'full footprint'),
       region(X < np.median(X), 'posterior half'),
       region(X >= np.median(X), 'anterior half'),
       region(gap >= 4.0, 'columns taller than 4.0 mm (beyond a hard core at T~1 mm)'),
       region(gap >= 4.95, 'columns taller than 4.95 mm (soft/void under S2 at T 2 mm)')]
# local slope statistics
slope = np.hypot(tx - bx, ty - by)  # opening angle between faces (small angle)
res.append(dict(local_opening_angle_deg=dict(median=round(float(np.degrees(np.median(slope))), 2),
                                            p90=round(float(np.degrees(np.percentile(slope, 90))), 2))))
json.dump(res, open('work/agents/safety/s05_wedge_squeeze.json', 'w'), indent=1)
for r in res: print(r)
