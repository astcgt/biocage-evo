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
    m = lambda s: float(h[s].mean()) if s.any() else float(h.mean())      # empty selection (possible for free-form maps): fall back to the overall value
    return dict(void_frac=float(info['window_frac']), mean_height_mm=float(info['height_mm_min_mean_max'][1]),
                contact_area_mm2=float(info['footprint_area_mm2'] - info['window_area_mm2']), hard_frac=float(h.mean()),
                face_hard_frac=m(face), core_hard_frac=m(core), post_hard_frac=m(cc[:, 0] < x0 + 0.25 * (x1 - x0)),
                ant_hard_frac=m(cc[:, 0] > x1 - 0.25 * (x1 - x0)), inner_hard_frac=m(inner), outer_hard_frac=m(outer),
                face_soft_thick_mm=float(skin.mean()), binary_material=float(binary))


PNAMES = ['log_k_axial', 'log_k_face', 'log_col_compliance', 'log_contrast', 'log_post_ant_stiffness', 'defl_100N_over_d', 'soft_volume_frac',
          'log_E_face', 'log_k_bend', 'stiff_centre_x_mm', 'face_strain_100N']
W_SIG = 0.02        # width of the logistic mixing law, as in h14_build_case.py line 35 (E_of_phi)


def physics_features(npz_path, E_hard, E_soft, theta, d):
    """Material x geometry composites (ROUND2 C6; declared 2026-11-18 before any scoring). Simple strength-of-materials
    estimates from the resolved material map - springs in series through the height of each column, columns in parallel:
      log_k_axial            axial stiffness of the whole cage (N/mm)
      log_k_face             the same for the 0.4 mm next to both faces only (contact compliance)
      log_col_compliance     mean through-height compliance of a column (also the shear compliance up to a constant)
      log_contrast           stiffest / softest element modulus
      log_post_ant_stiffness posterior-quarter / anterior-quarter axial stiffness (wedge tendency)
      defl_100N_over_d       height lost under the 100 N follower load / distraction d
      soft_volume_frac       volume fraction softer than the geometric mean of the two moduli
      log_E_face             mean modulus of the face layers
      log_k_bend             second moment of the column stiffness about the lateral axis (resistance to flexion / extension)
      stiff_centre_x_mm      antero-posterior position of the stiffness centre relative to the footprint centre
      face_strain_100N       nominal strain of the face layer under 100 N
    """
    z = np.load(npz_path, allow_pickle=True); info = json.loads(str(z['info'])); Q = z['Q']; H = z['hexes']; cage = z['region'] == 0; lay = z['layer']; K = int(lay.max()) + 1
    if info.get('fabrication') == 'interleave': E = np.where(z['hard'], E_hard, E_soft).astype(float)
    else:
        sg_ = lambda p: 1 / (1 + np.exp(-(p - theta) / W_SIG)); ph = np.nan_to_num(z['phi'], nan=0.0)
        E = E_soft * (E_hard / E_soft) ** ((sg_(ph) - sg_(0.0)) / (sg_(1.0) - sg_(0.0)))
    zc = Q[:, 2][H]; t = zc[:, 4:].mean(1) - zc[:, :4].mean(1); c = Q[H].mean(1); a = float(info['H_mm']) ** 2
    col = np.unique(np.round(c[:, :2], 3), axis=0, return_inverse=True)[1].ravel(); n = col.max() + 1
    comp = np.bincount(col[cage], (t / E)[cage], n); cnt = np.bincount(col[cage], None, n); full = cnt == K           # columns solid through the height
    kcol = np.where(full, a / np.maximum(comp, 1e-12), 0.0); x = np.bincount(col, c[:, 0], n) / np.bincount(col, None, n)
    near = cage & ((lay < 2) | (lay >= K - 2)); compf = np.bincount(col[near], (t / E)[near], n); kface = np.where(full, a / np.maximum(compf, 1e-12), 0.0)
    xs = x[full]; x0, x1 = xs.min(), xs.max(); post = full & (x < x0 + 0.25 * (x1 - x0)); ant = full & (x > x1 - 0.25 * (x1 - x0)); xm = (x * kcol).sum() / kcol.sum()
    face = cage & ((lay == 0) | (lay == K - 1)); area = full.sum() * a; Ef = float(np.exp(np.log(E[face]).mean())); ka = float(kcol.sum())
    return dict(log_k_axial=float(np.log(ka)), log_k_face=float(np.log(kface.sum())), log_col_compliance=float(np.log(comp[full].mean())), log_contrast=float(np.log(E[cage].max() / E[cage].min())),
                log_post_ant_stiffness=float(np.log(kcol[post].sum() / kcol[ant].sum())), defl_100N_over_d=float(100.0 / ka / d), soft_volume_frac=float((E[cage] < np.sqrt(E_hard * E_soft)).mean()),
                log_E_face=float(np.log(Ef)), log_k_bend=float(np.log((kcol * (x - xm) ** 2).sum())), stiff_centre_x_mm=float(xm - 0.5 * (x0 + x1)), face_strain_100N=float(100.0 / area / Ef))


if __name__ == '__main__':
    for f in sys.argv[1:]:
        print(json.dumps(dict(mesh=f.split('/')[-1], **{k: round(v, 4) for k, v in descriptors(f).items()})))
