"""Red team r0003 (c): how the PI 2026-10-27 dislocation measure (best-fit rigid motion of ALL cage nodes, its radial outward
translation; limits 1 mm any direction, 0.5 mm posterior; docs/DECISIONS.md:110-117) reacts to motions a designer could
produce. Synthetic cage: solid block on the evo voxel grid (0.2 mm), footprint 11 x 8.5 mm (p062 footprint ~92.8 mm^2),
height 4.6 mm (p062 mean height 4.605 mm), centred on the disc-space centre (origin). Posterior = -X (insertion from
anterior along -X, PLAN S2). Best-fit rigid motion = Kabsch / Horn least squares on equally weighted nodes.
Scenarios (displacements are imposed, not simulated): what the measure reports vs what any node actually does.
usage: python -I work/agents/redteam/r0003_dislocation.py -> r0003_dislocation_result.json
"""
import json, os, numpy as np

h = 0.2
xs, ys, zs = np.arange(-5.5, 5.5 + 1e-9, h), np.arange(-4.25, 4.25 + 1e-9, h), np.arange(-2.3, 2.3 + 1e-9, h)
X = np.stack(np.meshgrid(xs, ys, zs, indexing='ij'), -1).reshape(-1, 3)


def rigid_fit(X0, X1):
    c0, c1 = X0.mean(0), X1.mean(0)
    H = (X0 - c0).T @ (X1 - c1); U, S, Vt = np.linalg.svd(H); D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    return R, c1 - c0          # translation of the centroid (the 'rigid-body part'), rotation R


def report(name, u, note):
    X1 = X + u
    R, t = rigid_fit(X, X1)
    ang = float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
    radial = t  # cage centred on the disc-space centre: the radial outward direction is the direction of t itself
    post = max(0.0, -float(t[0]))
    nd = np.linalg.norm(u, axis=1)
    r = dict(scenario=name, note=note, rigid_translation_mm=[round(float(v), 4) for v in t], rigid_radial_mm=round(float(np.linalg.norm(radial)), 4),
             rigid_posterior_mm=round(post, 4), rigid_rotation_deg=round(ang, 3),
             max_node_disp_mm=round(float(nd.max()), 4), max_node_posterior_mm=round(float(max(0.0, -u[:, 0].min())), 4),
             verdict_1mm_any=bool(np.linalg.norm(radial) <= 1.0), verdict_0p5_post=bool(post <= 0.5))
    r['passes_dislocation_rule'] = r['verdict_1mm_any'] and r['verdict_0p5_post']
    return r


res = []
# 1 pure spin about the vertical axis through the centroid (F-0016 case): rigid part has zero translation
for deg in (5.0, 10.0):
    th = np.radians(deg); Rz = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])
    res.append(report(f'spin_{deg:.0f}deg', X @ Rz.T - X, 'whole cage rotates rigidly about Z; corners sweep into the lateral / posterior rim'))
# 2 anterior / lateral lobe: outer 15 % of the volume (largest +X) slides out by 4 mm, rest stays (soft hinge, elastic)
for frac, dist in ((0.15, 4.0), (0.25, 3.5)):
    m = X[:, 0] >= np.quantile(X[:, 0], 1 - frac); u = np.zeros_like(X); u[m, 0] = dist
    res.append(report(f'anterior_lobe_{int(frac*100)}pct_{dist}mm', u, 'outer anterior part extrudes out of the disc space (toward oesophagus); rest anchored'))
# 3 posterior lobe: 8 % of the volume (most -X) moves 4 mm posterior
for frac, dist in ((0.08, 4.0), (0.10, 4.5)):
    m = X[:, 0] <= np.quantile(X[:, 0], frac); u = np.zeros_like(X); u[m, 0] = -dist
    res.append(report(f'posterior_lobe_{int(frac*100)}pct_{dist}mm', u, 'posterior soft part migrates toward the cord; rest anchored'))
res.append(dict(scenario='weighting_note', note='the fit weights every node equally: the reported rigid translation is the node-average displacement '
                '(centroid shift), so the share of the volume that moves sets the reported value, not the size of the move'))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r0003_dislocation_result.json')
json.dump(dict(n_nodes=len(X), cases=res), open(out, 'w'), indent=1)
for r in res:
    print(json.dumps(r))
