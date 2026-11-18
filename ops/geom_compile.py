"""Geometry Compiler v0 (ROUND2_ARCHITECTURE.md B12 / B13; PI 2026-11-18): Design Grammar specification -> cage model file.

How it works: the mesh files written by h12 already hold the FULL disc-space lattice (every 0.2 mm column of the endplate
footprint x K layers; 'region' says cage or void, 'phi' / 'hard' say which material). h14 drops the void elements, keeps
only face quads whose nodes all belong to cage elements and takes the material of every element from the file. So a new
shape needs no new mesh: the compiler RELABELS region / phi / hard on the lattice of the wanted distraction d and writes a
file in the same format. h12 and h14 (gate files) are not touched. The material map stays resolved per element.

Specification (JSON):
  {"name": "...", "base_mesh": "<any design-A h12 mesh at the wanted d>", "fabrication": "interleave" | "mix",
   "solid": <region>, "phi": [{"where": <region>, "value": 0..1, "mode": "set" | "min" | "max"}, ...],   # start 1.0, rules in order
   "line_clip": N (optional: clip the print-line index to N-1 as h12 does), "mechanism": "...", "source": "..."}
Regions (boolean over the lattice elements; lengths in mm; x = anterior (+) / posterior (-), y = lateral, frame coordinates):
  {"op": "all"}
  {"op": "ring", "outer": a, "inner": b}            between the footprint outline inset by a and inset by b (a < b)
  {"op": "band", "axis": "x" | "y", "lo": v, "hi": w}   slab, coordinates relative to the footprint centroid
  {"op": "lines", "from": a, "to": b, "clip": N}      0.4 mm print lines a..b-1 counted from the outline (0 = outermost)
  {"op": "disk", "cx": .., "cy": .., "r": ..}       cylinder through the height, centre relative to the centroid
  {"op": "face", "side": "top" | "bottom" | "both", "lo": s0, "hi": s1}   distance to that endplate face in [s0, s1)
  {"op": "bars", "axis": "x" | "y", "pitch": p, "width": w, "phase": f}  periodic bars
  {"op": "union" | "intersect", "of": [...]}, {"op": "subtract", "a": .., "b": ..}, {"op": "not", "of": ..},
  {"op": "mirror_y", "of": ..}                      union with its mirror image about the sagittal plane
  {"op": "custom", "file": "x.py", "func": "f"}     escape hatch: f(fields) -> boolean array; every use is logged
Interleave realisation (as h12): an element is hard when (print-line index + layer) mod 4 < round(4 phi); the print-line
index is the 0.4 mm contour line counted from the footprint outline.
L0 checks by code (safety rules of docs/PLAN.md; the numbers marked provisional are owned by the safety guard):
  S3 one connected solid part (islands are removed and logged; refused when > 2 % of the solid voxels would change -
     provisional limit);
  S4 the void that touches BOTH endplates (one connected region) is >= 50 % of the disc-space volume (PLAN.md S4: 'void
     connected to both endplates, >= 50 %'); and that region meets EACH endplate over >= 25 % of the footprint (provisional number: a void that
     reaches an endplate only through a small hole does not let the endplate feed the biodisc); the total void is reported
     next to it (audit D-20261118-38: the first version tested the total void and only required some through-going void);
  S5 in-plane feature >= 0.4 mm (2 columns; provisional tolerance 2 % for staircase cells) and every solid element
     supported from the layer below by the element underneath or one of its four side neighbours (45 degrees in the axis
     directions; a diagonal step would be 55 degrees and is not accepted; provisional tolerance 0.5 %);
  C1 the part touches both endplates; C2 no face quad over a void column that h14 would still take as contact;
  C3 solid columns that do not reach a face are counted (no contact surface is defined there - warning).
usage: python ops/geom_compile.py <spec.json> <out.npz> [report.json]       exit 0 = built, 2 = refused
"""
import os, sys, json, hashlib, importlib.util
import numpy as np
from scipy import ndimage

EVO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAT = os.path.dirname(os.path.dirname(json.load(open(os.path.join(EVO, 'config.json')))['febio_src']))
sys.path.insert(0, os.path.join(PLAT, 'scripts', 'common'))
LINE, MAX_REPAIR, TOL_FEATURE, TOL_OVERHANG, MIN_VOID_FACE = 0.4, 0.02, 0.02, 0.005, 0.25
FSU, FRAME = os.path.join(PLAT, 'human_study/fsu/C34_fsu_refined.feb'), os.path.join(PLAT, 'human_study/frame_c3c4.json')
_fp_cache = {}


def footprint():
    if 'fp' not in _fp_cache:
        from cage_geom import Endplates
        _fp_cache['fp'] = Endplates(FSU, FRAME).footprint
    return _fp_cache['fp']


def fields(base):
    """per-element geometric fields of the lattice"""
    import shapely.geometry as sg
    Q, H, lay = base['Q'], base['hexes'], base['layer']; K = int(lay.max()) + 1; fp = footprint()
    z = Q[:, 2][H]; c = Q[H].mean(1); x, y = c[:, 0], c[:, 1]
    hcol = K * (z[:, 4:].mean(1) - z[:, :4].mean(1))
    xy, col = np.unique(np.round(c[:, :2], 4), axis=0, return_inverse=True); col = col.ravel()
    dout_c = np.array([fp.exterior.distance(sg.Point(a, b)) for a, b in xy])
    h = float(json.loads(str(base['info']))['H_mm'])
    gi = np.round((xy[:, 0] - xy[:, 0].min()) / h).astype(int); gj = np.round((xy[:, 1] - xy[:, 1].min()) / h).astype(int)
    return dict(n=len(H), K=K, x=x, y=y, cx=fp.centroid.x, cy=fp.centroid.y, layer=lay, col=col, xy=xy, dout=dout_c[col], hcol=hcol, h=h,
                s_bot=(lay + 0.5) * hcol / K, s_top=(K - lay - 0.5) * hcol / K, gi=gi[col], gj=gj[col], fp=fp)


def region(e, F, log):
    import shapely.geometry as sg
    from shapely import vectorized
    op = e['op']
    if op == 'all': return np.ones(F['n'], bool)
    if op == 'ring':
        inside = lambda off: (vectorized.contains(F['fp'].buffer(-off, join_style=1), F['xy'][:, 0], F['xy'][:, 1]) if off > 0 else np.ones(len(F['xy']), bool))[F['col']]
        return inside(e.get('outer', 0.0)) & ~inside(e['inner'])
    if op == 'lines':      # 0.4 mm print lines counted from the footprint outline (0 = outermost), optionally clipped as h12 does
        li = (F['dout'] // LINE).astype(int); li = np.clip(li, 0, int(e['clip']) - 1) if e.get('clip') else li; return (li >= e['from']) & (li < e.get('to', 10 ** 6))
    if op == 'band':
        v = (F['x'] - F['cx']) if e['axis'] == 'x' else (F['y'] - F['cy']); return (v >= e['lo']) & (v < e['hi'])
    if op == 'disk': return (F['x'] - F['cx'] - e['cx']) ** 2 + (F['y'] - F['cy'] - e['cy']) ** 2 < e['r'] ** 2
    if op == 'face':
        s = dict(top=F['s_top'], bottom=F['s_bot'], both=np.minimum(F['s_top'], F['s_bot']))[e['side']]; return (s >= e['lo']) & (s < e['hi'])
    if op == 'bars':
        v = (F['x'] - F['cx']) if e['axis'] == 'x' else (F['y'] - F['cy']); return ((v - e.get('phase', 0.0)) % e['pitch']) < e['width']
    if op == 'union': return np.any([region(a, F, log) for a in e['of']], axis=0)
    if op == 'intersect': return np.all([region(a, F, log) for a in e['of']], axis=0)
    if op == 'subtract': return region(e['a'], F, log) & ~region(e['b'], F, log)
    if op == 'not': return ~region(e['of'], F, log)
    if op == 'mirror_y':
        m = region(e['of'], F, log); key = {(int(i), int(j), int(k)): n for n, (i, j, k) in enumerate(zip(F['gi'], np.round((F['y'] - F['cy']) / F['h'] * 2).astype(int), F['layer']))}
        mir = np.array([m[key.get((int(i), -int(j), int(k)), n)] for n, (i, j, k) in enumerate(zip(F['gi'], np.round((F['y'] - F['cy']) / F['h'] * 2).astype(int), F['layer']))])
        return m | mir
    if op == 'custom':
        spec = importlib.util.spec_from_file_location('custom_field', e['file']); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        log.append(f"custom field used: {e['file']}:{e['func']} (grammar-extension request)"); return np.asarray(getattr(mod, e['func'])(F), bool)
    raise ValueError(f'unknown region op {op}')


def grid(F, mask):
    g = np.zeros((F['gi'].max() + 1, F['gj'].max() + 1, F['K']), bool); g[F['gi'], F['gj'], F['layer']] = mask; return g


def compile_spec(spec, out=None):
    base = np.load(spec['base_mesh'] if os.path.isabs(spec['base_mesh']) else os.path.join(PLAT, spec['base_mesh']), allow_pickle=True)
    F = fields(base); log = []; K = F['K']; H = base['hexes']
    solid = region(spec['solid'], F, log)
    # S3 connectivity: keep the largest solid component
    lab, n = ndimage.label(grid(F, solid)); changed = 0
    if n > 1:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)); keep = 1 + int(np.argmax(sizes)); L = lab[F['gi'], F['gj'], F['layer']]
        changed = int((solid & (L != keep)).sum()); solid = solid & (L == keep); log.append(f'S3 repair: removed {n - 1} island(s), {changed} elements')
    phi = np.ones(F['n'])
    for r in spec.get('phi', []):
        w = region(r['where'], F, log); v = float(r['value']); mode = r.get('mode', 'set')
        phi[w] = v if mode == 'set' else np.minimum(phi[w], v) if mode == 'min' else np.maximum(phi[w], v)
    line = (F['dout'] // LINE).astype(int)
    if spec.get('line_clip'): line = np.clip(line, 0, int(spec['line_clip']) - 1)
    hard = ((line + F['layer']) % 4) < np.round(4 * phi)
    fab = spec.get('fabrication', 'interleave')
    # ---- L0 checks
    g = grid(F, solid); act = grid(F, np.ones(F['n'], bool)); vol = F['hcol'] / K; chk = {}
    chk['S3_one_part'] = dict(ok=bool(ndimage.label(g)[1] == 1), islands_removed=int(n - 1 if n > 1 else 0), changed_fraction=round(changed / max(1, int(solid.sum()) + changed), 4))
    vlab, vn = ndimage.label(act & ~g); through = [i for i in range(1, vn + 1) if (vlab[:, :, 0] == i).any() and (vlab[:, :, K - 1] == i).any()]
    vf = float(1 - vol[solid].sum() / vol.sum()); vL = vlab[F['gi'], F['gj'], F['layer']]
    main = max(through, key=lambda i: float(vol[vL == i].sum()), default=None); vthrough = float(vol[vL == main].sum() / vol.sum()) if main else 0.0
    ncol = int(act.any(2).sum()); face_top = float((vlab[:, :, K - 1] == main).sum() / ncol) if main else 0.0; face_bot = float((vlab[:, :, 0] == main).sum() / ncol) if main else 0.0
    chk['S4_void'] = dict(ok=bool(vthrough >= 0.5 and min(face_top, face_bot) >= MIN_VOID_FACE), void_fraction_through_both_endplates=round(vthrough, 4), void_face_fraction_top=round(face_top, 4), void_face_fraction_bottom=round(face_bot, 4), min_face_fraction_provisional=MIN_VOID_FACE, void_fraction_volume=round(vf, 4), void_fraction_projected=round(float(1 - g.any(2).sum() / act.any(2).sum()), 4), void_regions_touching_both_endplates=len(through))
    opened = np.stack([ndimage.binary_opening(g[:, :, k], structure=np.ones((2, 2), bool)) for k in range(K)], axis=2)
    thin = int((g & ~opened).sum()); chk['S5_min_feature'] = dict(ok=bool(thin <= TOL_FEATURE * g.sum()), thin_elements=thin, fraction=round(thin / max(1, int(g.sum())), 4), tolerance=TOL_FEATURE)
    sup = np.stack([g[:, :, 0]] + [ndimage.binary_dilation(g[:, :, k - 1], structure=ndimage.generate_binary_structure(2, 1)) for k in range(1, K)], axis=2)
    unsup = int((g & ~sup).sum()); chk['S5_overhang'] = dict(ok=bool(unsup <= TOL_OVERHANG * g.sum()), unsupported_elements=unsup, fraction=round(unsup / max(1, int(g.sum())), 4), tolerance=TOL_OVERHANG)
    nt, nb = int(g[:, :, K - 1].sum()), int(g[:, :, 0].sum()); chk['C1_touches_both_endplates'] = dict(ok=bool(nt > 0 and nb > 0), top_columns=nt, bottom_columns=nb)
    cage_nodes = np.zeros(len(base['Q']), bool); cage_nodes[np.unique(H[solid])] = True; lay = F['layer']
    spur = 0
    for k, sl in ((K - 1, slice(4, 8)), (0, slice(0, 4))):
        e = np.where((lay == k) & ~solid)[0]; spur += int(cage_nodes[H[e][:, sl]].all(1).sum())
    chk['C2_no_contact_over_void'] = dict(ok=spur == 0, quads=spur)
    col_any = g.any(2); recessed = int((col_any & ~(g[:, :, 0] & g[:, :, K - 1])).sum()); chk['C3_recessed_columns'] = dict(ok=True, warning=recessed > 0, columns=recessed)
    chk['repair_limit'] = dict(ok=bool(chk['S3_one_part']['changed_fraction'] <= MAX_REPAIR), limit=MAX_REPAIR)
    ok = all(c['ok'] for c in chk.values())
    sha = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    rep = dict(name=spec.get('name'), spec_sha256=sha, built=ok, checks=chk, log=log, n_solid=int(solid.sum()), mean_phi=round(float(phi[solid].mean()), 4) if solid.any() else None,
               hard_fraction=round(float(hard[solid].mean()), 4) if solid.any() else None, mechanism=spec.get('mechanism'), source=spec.get('source'))
    if ok and out:
        info = json.loads(str(base['info'])); cn = np.where(cage_nodes)[0]
        keep = lambda s: np.array([i for i in s if cage_nodes[i]], dtype=int)
        post, ant = keep(base['post']), keep(base['ant'])
        if len(post) < 5: post = cn[np.argsort(base['Q'][cn, 0])[:max(5, len(cn) // 50)]]; log.append('posterior node set rebuilt from the posterior-most cage nodes')
        if len(ant) < 5: ant = cn[np.argsort(-base['Q'][cn, 0])[:max(5, len(cn) // 50)]]; log.append('anterior node set rebuilt from the anterior-most cage nodes')
        ph = np.where(solid, phi, np.nan)
        info.update(gradient='grammar', fabrication=fab, n_cage=int(solid.sum()), n_biodisc=int((~solid).sum()), window_frac=chk['S4_void']['void_fraction_projected'],
                    window_area_mm2=round(info['footprint_area_mm2'] * chk['S4_void']['void_fraction_projected'], 2), void_fraction_volume=chk['S4_void']['void_fraction_volume'],
                    cage_volume_mm3=round(float(vol[solid].sum() * F['h'] ** 2), 1), phi_hist={str(v): int((ph[solid] == v).sum()) for v in (0.0, 0.25, 0.5, 0.75, 1.0)},
                    interleave_hard_frac=round(float(hard[solid].mean()), 3), grammar_spec_sha256=sha, grammar_name=spec.get('name'))
        np.savez_compressed(out, Q=base['Q'], G=base['G'], hexes=H, region=np.where(solid, 0, 1), phi=ph, hard=hard & solid if fab == 'interleave' else hard,
                            layer=base['layer'], top=base['top'], bot=base['bot'], post=post, ant=ant, info=json.dumps(info))
    return rep, dict(solid=solid, phi=phi, hard=hard)


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1])); rep, _ = compile_spec(spec, sys.argv[2])
    if len(sys.argv) > 3: json.dump(rep, open(sys.argv[3], 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(dict(built=rep['built'], failed=[k for k, c in rep['checks'].items() if not c['ok']], void_through=rep['checks']['S4_void']['void_fraction_through_both_endplates'], void_total=rep['checks']['S4_void']['void_fraction_volume'], log=rep['log']), ensure_ascii=False))
    sys.exit(0 if rep['built'] else 2)
