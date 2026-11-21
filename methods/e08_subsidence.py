"""Bone subsidence-onset check on an existing run (PI 2026-11-19, test-gap plan item 1; regulatory analogue ASTM F2267).

Rule = the capacity endpoint (b) agreed 2026-10-20 (old repo scripts/4_postprocess/h15_post_case.py, same code path):
  trabecular elements of C3 and C4 whose centroid lies inside the cage footprint and 0-3 mm (from -0.5 mm) beyond the endplate
  surface; an element is yielded when its min principal Lagrange strain < -0.75 % or its max principal > +0.70 %
  (Morgan & Keaveny 2001, J Biomech 34:569); subsidence onset = yielded volume > 10 % of that bone region.
Reported per state: the combined fraction (h15 definition), C3 / C4 separately (the stricter reading), and per vertebra the
compressive-only (_comp) and tensile-only (_tens) yielded fractions (a bonded tied face can pull the bone on the lift-off side).
The strain is the total Lagrange strain from the reference configuration (insertion + release + follower + window).
usage: python e08_subsidence.py <case_dir> <out.json> [t1 t2 ...]   (no times: every state at t >= 3.0)
"""
import sys, os, json, numpy as np, xml.etree.ElementTree as ET
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAT = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026'
sys.path[:0] = [os.path.join(E, 'common'), os.path.join(PLAT, 'scripts', 'common')]
import xplt
from cage_geom import Endplates
from shapely import vectorized
YC, YT, ONSET, DEPTH = -0.0075, 0.0070, 0.10, 3.0


def tet_vol(P): return abs(np.einsum('ij,ij->i', P[:, 1] - P[:, 0], np.cross(P[:, 2] - P[:, 0], P[:, 3] - P[:, 0]))) / 6


def main(cd, out, times=None):
    case = json.load(open(os.path.join(cd, 'case.json'))); prm = case['params']
    g = ET.parse(os.path.join(cd, 'case.feb')).getroot().find('Geometry')
    X = {int(n.get('id')): np.array([float(v) for v in n.text.split(',')]) for n in g.find('Nodes')}
    blocks = [(eb.get('name'), np.array([[int(v) for v in e.text.split(',')] for e in eb])) for eb in g.findall('Elements')]
    ep = Endplates(os.path.join(PLAT, prm['fsu']), os.path.join(PLAT, prm['frame'])); fp = ep.footprint
    bone = {}
    for i, (n, El) in enumerate(blocks):
        if n not in ('C3_trabecular', 'C4_trabecular'): continue
        assert El.shape[1] == 4, f'{n}: expected tet4'
        P = np.array([[X[j] for j in e] for e in El]); C = P.mean(1)
        ref = ep.z_top(C[:, 0], C[:, 1]) if n.startswith('C3') else ep.z_bot(C[:, 0], C[:, 1])
        dz = (C[:, 2] - ref) if n.startswith('C3') else (ref - C[:, 2])
        sel = vectorized.contains(fp, C[:, 0], C[:, 1]) & (dz >= -0.5) & (dz <= DEPTH)
        bone[i] = (n[:2], sel, tet_vol(P)[sel])
    pf = xplt.read(os.path.join(cd, 'case.xplt')); st = pf['states']; st_t = np.array([s['time'] for s in st])
    ks = sorted({int(np.argmin(abs(st_t - t))) for t in times}) if times else [k for k in range(len(st)) if st_t[k] >= 3.0 - 1e-6]
    rows = []
    for k in ks:
        Ls = st[k]['elem'].get('Lagrange strain', {}); r = dict(t=float(st_t[k])); yv = tv = 0.0
        for i, (v, sel, vol) in bone.items():
            Eg = Ls.get(i + 1)
            if Eg is None: r[v] = None; continue
            Eg = Eg[sel]; M = np.array([[Eg[:, 0], Eg[:, 3], Eg[:, 5]], [Eg[:, 3], Eg[:, 1], Eg[:, 4]], [Eg[:, 5], Eg[:, 4], Eg[:, 2]]]).transpose(2, 0, 1)
            ev = np.linalg.eigvalsh(M); y = (ev[:, 0] < YC) | (ev[:, -1] > YT)
            r[v] = float(vol[y].sum() / vol.sum()); r[v + '_min_strain'] = float(ev[:, 0].min()); yv += vol[y].sum(); tv += vol.sum()
            r[v + '_comp'] = float(vol[ev[:, 0] < YC].sum() / vol.sum()); r[v + '_tens'] = float(vol[ev[:, -1] > YT].sum() / vol.sum())   # advisor 11-19: tensile part may be a tied-interface artefact
            r[v + '_max_strain'] = float(ev[:, -1].max())
        r['combined'] = float(yv / tv) if tv else None
        rows.append(r)
    res = dict(case=cd, rule='Morgan & Keaveny 2001 trabecular yield strain (-0.75 % / +0.70 %), 0-3 mm below the footprint, onset > 10 % yielded volume (h15 endpoint b)',
               region_volume_mm3={v: float(vol.sum()) for (v, sel, vol) in bone.values()},
               region_elements={v: int(sel.sum()) for (v, sel, vol) in bone.values()}, states=rows,
               max=dict(combined=max((r['combined'] or 0) for r in rows) if rows else None,
                        worst_vertebra=max(max(r.get('C3') or 0, r.get('C4') or 0) for r in rows) if rows else None))
    res['onset'] = bool(rows) and res['max']['worst_vertebra'] > ONSET
    json.dump(res, open(out, 'w'), indent=1)
    return res


if __name__ == '__main__':
    r = main(sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3:]] or None)
    print(json.dumps(dict(max=r['max'], onset=r['onset'], n_states=len(r['states']), region=r['region_elements'])))
