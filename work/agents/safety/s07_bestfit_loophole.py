"""Safety guard r0003: loophole check of the PI 2026-10-27 dislocation measure (best-fit rigid motion of ALL cage nodes).
Toy cage = uniform node cloud in the 1 mm inset footprint box (9.5 x 11.5 x 4 mm). A stiff part (hard core, fraction f of the
nodes) is moved rigidly by u toward posterior (-X); the soft rest stays (it is held by friction / squashed). Best fit (Kabsch)
of all nodes vs the hard part alone. Also: node-count weighting vs volume weighting when the mesh is finer in thin features.
Run: python work/agents/safety/s07_bestfit_loophole.py
"""
import json
import numpy as np
rng = np.random.default_rng(0)
def kabsch(P, Q, w=None):
    w = np.ones(len(P)) if w is None else w
    w = w / w.sum(); pc, qc = w @ P, w @ Q
    H = ((P - pc) * w[:, None]).T @ (Q - qc); U, S, Vt = np.linalg.svd(H)
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]); R = Vt.T @ D @ U.T
    return R, qc - R @ pc
N = 20000
P = rng.uniform([-5.5, -5.7, 0], [4.0, 5.7, 4.0], (N, 3))
rows = []
for f in (0.2, 0.35, 0.5):
    hard = P[:, 0] < np.quantile(P[:, 0], f)          # posterior slab = hard core
    for u in (0.6, 1.0, 1.5):
        Q = P.copy(); Q[hard, 0] -= u
        R, t = kabsch(P, Q)
        cen_shift = (Q.mean(0) - P.mean(0))[0]
        rows.append(dict(hard_fraction=f, hard_core_posterior_move_mm=u,
                         bestfit_all_nodes_translation_x_mm=round(float(t[0] + (R @ P.mean(0) - P.mean(0))[0]), 3),
                         centroid_shift_x_mm=round(float(cen_shift), 3),
                         bestfit_rotation_deg=round(float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))), 3),
                         passes_0p5mm_posterior_limit=bool(abs(cen_shift) <= 0.5)))
json.dump(rows, open('work/agents/safety/s07_bestfit_loophole.json', 'w'), indent=1)
for r in rows: print(r)
