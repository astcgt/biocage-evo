"""Geometric descriptors of a cage material map (ROUND2_ARCHITECTURE.md A1 / C1; PI 2026-11-18).

Computed by code from the cage mesh npz written by h12 (old repo human_study/al/meshes/*.npz: Q frame coordinates, hexes,
region 0 cage / 1 biodisc, phi, hard, layer, info) - the per-element material map stays resolved, nothing is homogenised.
Every descriptor is defined for ANY material map on the grid (no family label needed), so the same code serves new
topologies from the Geometry Compiler. Posterior = -X in the frame (the 'post' node set sits at the smallest X).
Note: for today's parametric families the mesh is fixed by family + distraction d, so inside a family these descriptors are
functions of d only; their use is transfer across families and to new shapes.

usage: python ops/descriptors.py <cage.npz> [more.npz ...]     # prints one JSON line per mesh
"""
import sys, json, numpy as np
from scipy.spatial import cKDTree

NAMES = ['void_frac', 'mean_height_mm', 'contact_area_mm2', 'hard_frac', 'face_hard_frac', 'core_hard_frac',
         'post_hard_frac', 'ant_hard_frac', 'inner_hard_frac', 'outer_hard_frac', 'face_soft_thick_mm', 'binary_material']


def descriptors(npz_path):
    z = np.load(npz_path, allow_pickle=True)
    info = json.loads(str(z['info'])); Q = z['Q']; H = z['hexes']; reg = z['region']; lay = z['layer']
    cage = reg == 0
    binary = info.get('fabrication') == 'interleave'
    h = (z['hard'].astype(float) if binary else np.nan_to_num(z['phi'], nan=0.0))[cage]      # effective hard fraction per cage element
    c = Q[H].mean(1); cc = c[cage]; lc = lay[cage]; K = int(lay.max()) + 1; hz = float(info.get('HZ_mm', 0.2))
    x0, x1 = cc[:, 0].min(), cc[:, 0].max()
    face = (lc == 0) | (lc == K - 1); core = (lc >= K // 3) & (lc < K - K // 3)
    # distance of each cage column to the biodisc window (in-plane)
    win = np.unique(np.round(c[~cage][:, :2], 3), axis=0)
    dwin = cKDTree(win).query(cc[:, :2])[0] if len(win) else np.full(len(cc), np.inf)
    inner = dwin < 0.45; outer = dwin > 0.85
    # soft skin thickness: consecutive soft elements from each face, per column
    col = np.unique(np.round(cc[:, :2], 3), axis=0, return_inverse=True)[1].ravel()
    hm = np.full((col.max() + 1, K), np.nan); hm[col, lc] = h
    def run(a):   # count of leading soft (< 0.5) elements along each row
        soft = np.where(np.isnan(a), False, a < 0.5); return np.cumprod(soft, axis=1).sum(1)
    skin = (run(hm) + run(hm[:, ::-1])) * hz / 2.0
    m = lambda s: float(h[s].mean()) if s.any() else float('nan')
    return dict(void_frac=float(info['window_frac']), mean_height_mm=float(info['height_mm_min_mean_max'][1]),
                contact_area_mm2=float(info['footprint_area_mm2'] - info['window_area_mm2']), hard_frac=float(h.mean()),
                face_hard_frac=m(face), core_hard_frac=m(core), post_hard_frac=m(cc[:, 0] < x0 + 0.25 * (x1 - x0)),
                ant_hard_frac=m(cc[:, 0] > x1 - 0.25 * (x1 - x0)), inner_hard_frac=m(inner), outer_hard_frac=m(outer),
                face_soft_thick_mm=float(skin.mean()), binary_material=float(binary))


if __name__ == '__main__':
    for f in sys.argv[1:]:
        print(json.dumps(dict(mesh=f.split('/')[-1], **{k: round(v, 4) for k, v in descriptors(f).items()})))
