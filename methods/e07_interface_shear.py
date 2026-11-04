"""e07 interface shear (PI 2026-11-04: shear at the printed hard / soft interface large enough to delaminate is a safety failure).

For every state of case.xplt: the traction on each cage element face shared by two elements of different material (FEBio block), taken
one-sided from each element's Cauchy stress times the face normal; the reported 'soft side' is the traction in the element with the
lower phi (in mixing-nozzle designs this is the lower-phi side of EACH phi step, not phi 0 vs 1), 'hard side' the other, split into
shear |t - (t.n) n| and normal (t.n, tension positive = peel).
Faces are classed horizontal (|n_z| > 0.7: between printed layers, the axial-gradient interface) or vertical (in-plane band
boundary, the radial-gradient interface). Reports max and 99th percentile (MPa) per class and state, plus the cage-wide
maximum over the states. Face normals are taken in the reference configuration (small-rotation approximation; the soft
bands reach 10-25 % compression, so treat the numbers as +-10 %). No threshold is applied here: the bond strength of the
co-printed PLCL hard / soft interface is not measured; the PI sets the limit.
usage: python e07_interface_shear.py <case_dir> [out.json]
"""
import sys, os, json, numpy as np, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'common'))
P = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026/'
FACES = ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
Q = 99


def interfaces(cd):
    """(hex a, hex b, unit normal, horizontal?, a is the stiffer side?) for every face shared by two cage elements of DIFFERENT
    material, plus the xplt (block id, index) of every cage hex. 2026-11-04 fix: the material is the FEBio element block
    (cage_elems.npz 'block': cage_mix_<phi>, or cage_soft_0.0 / cage_hard_1.0). The mesh flag 'hard' is the interleave pattern
    only: in mixing-nozzle designs it alternates inside one material, so the first version evaluated faces that are no
    material interface at all (every mix result before 2026-11-04 11:30 is invalid)."""
    cj = json.load(open(os.path.join(cd, 'case.json'))); m = np.load(P + cj['params']['cage_npz'])
    ce = np.load(os.path.join(cd, 'cage_elems.npz'), allow_pickle=True)
    hexes, X = m['hexes'], m['Q']
    idx, blocks = ce['npz_index'], ce['block']
    names = [eb.get('name') for eb in ET.parse(os.path.join(cd, 'case.feb')).getroot().find('Geometry').findall('Elements')]
    bid = {n: i + 1 for i, n in enumerate(names)}
    pos = np.zeros(len(idx), int)
    for b in set(blocks):
        w = np.where(blocks == b)[0]; pos[w] = np.arange(len(w))
    loc = {int(h): (bid[blocks[k]], int(pos[k])) for k, h in enumerate(idx)}
    mat = {int(h): str(blocks[k]) for k, h in enumerate(idx)}
    phi_of = lambda name: float(name.rsplit('_', 1)[1])
    fmap = {}
    for h in idx:
        for f in FACES:
            nodes = hexes[h][list(f)]; fmap.setdefault(tuple(sorted(nodes)), []).append((int(h), nodes))
    out = []
    for key, v in fmap.items():
        if len(v) != 2 or mat[v[0][0]] == mat[v[1][0]]: continue
        (a, na), (b, nb) = v
        p = X[na]; n = np.cross(p[2] - p[0], p[3] - p[1]); n /= np.linalg.norm(n)
        out.append((a, b, n, abs(n[2]) > 0.7, phi_of(mat[a]) > phi_of(mat[b])))
    return out, loc


def stress_tensor(s6):
    s = np.empty(s6.shape[:-1] + (3, 3))
    s[..., 0, 0], s[..., 1, 1], s[..., 2, 2] = s6[..., 0], s6[..., 1], s6[..., 2]
    s[..., 0, 1] = s[..., 1, 0] = s6[..., 3]; s[..., 1, 2] = s[..., 2, 1] = s6[..., 4]; s[..., 0, 2] = s[..., 2, 0] = s6[..., 5]
    return s


def main(cd, out=None):
    import xplt
    faces, loc = interfaces(cd)
    if not faces: return dict(n_faces=0, states=[])
    A = np.array([loc[a] for a, b, n, h, ha in faces]); B = np.array([loc[b] for a, b, n, h, ha in faces])
    N = np.array([n for a, b, n, h, ha in faces]); H = np.array([h for a, b, n, h, ha in faces]); HARD_A = np.array([ha for a, b, n, h, ha in faces])
    states = xplt.read(os.path.join(cd, 'case.xplt'))['states']
    res = dict(n_faces=len(faces), n_horizontal=int(H.sum()), n_vertical=int((~H).sum()), states=[])
    for st in states:
        S = st['elem']['stress']
        # traction from each side separately: the stiff (hard) element carries stress concentrations that the soft element
        # cannot (its stress is bounded by the soft material), so the two one-sided tractions differ where the 0.2 mm mesh
        # does not resolve the boundary layer; 'soft' is the traction the soft phase actually transmits, 'mismatch' the
        # relative difference (a resolution indicator).
        sa = stress_tensor(np.stack([S[b][i] for b, i in A])); sb = stress_tensor(np.stack([S[b][i] for b, i in B]))
        sig_soft = np.where(HARD_A[:, None, None], sb, sa); sig_hard = np.where(HARD_A[:, None, None], sa, sb)
        r = dict(time=st['time'])
        side = {}
        for nm, sig in (('soft', sig_soft), ('hard', sig_hard)):
            t = np.einsum('fij,fj->fi', sig, N); tn = np.einsum('fi,fi->f', t, N); ts = np.linalg.norm(t - tn[:, None] * N, axis=1)
            side[nm] = (ts, tn)
        for cls, mask in (('horizontal', H), ('vertical', ~H)):
            if mask.any():
                ts, tn = side['soft']; th, _ = side['hard']
                r[cls] = dict(shear_max=float(ts[mask].max()), shear_p99=float(np.percentile(ts[mask], Q)),
                              peel_max=float(tn[mask].max()), peel_p99=float(np.percentile(tn[mask], Q)),
                              hard_side_shear_max=float(th[mask].max()), hard_side_shear_p99=float(np.percentile(th[mask], Q)))
        res['states'].append(r)
    for cls in ('horizontal', 'vertical'):
        v = [s[cls] for s in res['states'] if cls in s]
        if v: res[cls + '_max_over_states'] = dict(shear_max=max(x['shear_max'] for x in v), shear_p99=max(x['shear_p99'] for x in v),
                                                   peel_max=max(x['peel_max'] for x in v), t_shear_max=res['states'][int(np.argmax([x['shear_max'] for x in v]))]['time'])
    if out: json.dump(res, open(out, 'w'), indent=1)
    return res


if __name__ == '__main__':
    r = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"faces {r['n_faces']} (horizontal {r.get('n_horizontal')}, vertical {r.get('n_vertical')})")
    for s in r['states']:
        print(f"t {s['time']:.3f}  " + '  '.join(f"{c}: soft-side shear max {s[c]['shear_max']:.3f} p99 {s[c]['shear_p99']:.3f} peel max {s[c]['peel_max']:.3f} | hard-side shear max {s[c]['hard_side_shear_max']:.3f} MPa" for c in ('horizontal', 'vertical') if c in s))
