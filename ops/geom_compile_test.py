"""Acceptance test of the Geometry Compiler (owner: verifier): the six parametric design-A families written in the Design
Grammar must reproduce the h12 mesh files element for element (region, phi and hard of every cage element), for every
design-A mesh in human_study/al/meshes. Writes results/grammar/acceptance_<date>.json.
usage: python ops/geom_compile_test.py [YYYY-MM-DD]"""
import os, sys, json, glob, re, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom_compile as G

AX = [dict(where=dict(op='face', side='both', lo=0.4, hi=0.6), value=0.75), dict(where=dict(op='face', side='both', lo=0.2, hi=0.4), value=0.5),
      dict(where=dict(op='face', side='both', lo=0.0, hi=0.2), value=0.25)]


def family_spec(mesh, grad, fab, n):
    rd = [dict(where=dict(op='lines', **{'from': n - 2, 'to': n - 1, 'clip': n}), value=0.5, mode='min'), dict(where=dict(op='lines', **{'from': n - 1, 'clip': n}), value=0.0, mode='min')]
    return dict(name=f'family_{grad}_{fab}', base_mesh=mesh, fabrication=fab, line_clip=n, solid=dict(op='ring', outer=0.0, inner=round(n * G.LINE, 3)),
                phi=(AX if grad in ('axial', 'both') else []) + (rd if grad in ('radial', 'both') else []), source='acceptance test')


if __name__ == '__main__':
    date = sys.argv[1] if len(sys.argv) > 1 else time.strftime('%Y-%m-%d'); rows = []
    for f in sorted(glob.glob(os.path.join(G.PLAT, 'human_study/al/meshes/cage_A_*.npz'))):
        z = np.load(f, allow_pickle=True); info = json.loads(str(z['info'])); grad, fab = info['gradient'], info['fabrication']
        rep, arr = G.compile_spec(family_spec(f, grad, fab, int(info['n_perimeters'])))
        cage = z['region'] == 0
        d = dict(mesh=os.path.basename(f), region_mismatch=int((arr['solid'] != cage).sum()), phi_mismatch=int((arr['phi'][cage] != z['phi'][cage]).sum()),
                 hard_mismatch=int((arr['hard'][cage] != z['hard'][cage]).sum()), n_cage=int(cage.sum()), checks_failed=[k for k, c in rep['checks'].items() if not c['ok']],
                 void_volume=rep['checks']['S4_void']['void_fraction_volume'], thin_fraction=rep['checks']['S5_min_feature']['fraction'], overhang_fraction=rep['checks']['S5_overhang']['fraction'])
        rows.append(d)
    bad = [r for r in rows if r['region_mismatch'] or r['phi_mismatch'] or r['hard_mismatch']]
    out = dict(date=date, meshes=len(rows), identical=len(rows) - len(bad), not_identical=bad[:20], l0_failures=[(r['mesh'], r['checks_failed']) for r in rows if r['checks_failed']], rows=rows)
    os.makedirs(os.path.join(G.EVO, 'results/grammar'), exist_ok=True); json.dump(out, open(os.path.join(G.EVO, f'results/grammar/acceptance_{date}.json'), 'w'), indent=1)
    print('meshes', len(rows), 'identical', len(rows) - len(bad), 'not identical', len(bad), [(r['mesh'], r['region_mismatch'], r['phi_mismatch'], r['hard_mismatch']) for r in bad[:6]])
    # probe of S4 (audit D-20261118-38): a big pocket with a 0.6 mm floor + a small separate through hole must be REFUSED
    base = sorted(glob.glob(os.path.join(G.PLAT, 'human_study/al/meshes/cage_A_*_d1.000.npz')))[0]
    floor = dict(op='face', side='bottom', lo=0.0, hi=0.6); hole = dict(op='disk', cx=0.0, cy=0.0, r=1.0); ringw = dict(op='ring', outer=0.0, inner=0.8)
    probes = dict(pocket_with_connected_small_hole=dict(op='union', of=[ringw, dict(op='subtract', a=floor, b=hole)]),
                  pocket_with_separate_small_hole=dict(op='union', of=[ringw, dict(op='subtract', a=floor, b=hole), dict(op='subtract', a=dict(op='disk', cx=0.0, cy=0.0, r=1.5), b=hole)]))
    out['s4_probes'] = {}
    for k, sol in probes.items():
        rp, _ = G.compile_spec(dict(name=k, base_mesh=base, fabrication='mix', solid=sol, phi=[])); out['s4_probes'][k] = dict(built=rp['built'], **rp['checks']['S4_void'])
        print('S4 probe', k, '(must be refused): built', rp['built'], {a: b for a, b in rp['checks']['S4_void'].items() if a.startswith('void')})
    # holes (PI 2026-11-18): side holes with a flat roof up to the bridge span must BUILD; a wide flat slot must be refused
    wall = dict(op='ring', outer=0.0, inner=1.2); band = dict(op='face', side='bottom', lo=1.0, hi=2.0)
    mid = dict(op='band', axis='y', lo=-2.5, hi=3.5)      # only where the front and back walls run across (tunnels along x through the wall)
    holes = dict(many_side_holes_1mm=(dict(op='subtract', a=wall, b=dict(op='intersect', of=[dict(op='bars', axis='y', pitch=2.4, width=1.0, phase=0.0), band, mid])), True),
                 one_side_slot_4mm=(dict(op='subtract', a=wall, b=dict(op='intersect', of=[dict(op='band', axis='y', lo=-2.0, hi=2.0), band])), False))
    out['hole_probes'] = {}
    for k, (sol, want) in holes.items():
        rp, _ = G.compile_spec(dict(name=k, base_mesh=base, fabrication='mix', solid=sol, phi=[])); out['hole_probes'][k] = dict(built=rp['built'], expected=want, failed=[c for c, v in rp['checks'].items() if not v['ok']], **rp['checks']['S5_overhang'])
        print('hole probe', k, 'built', rp['built'], '(expected', want, ')', {a: b for a, b in rp['checks']['S5_overhang'].items() if a in ('unsupported_elements', 'bridged_elements', 'fraction')}, out['hole_probes'][k]['failed'])
    json.dump(out, open(os.path.join(G.EVO, f'results/grammar/acceptance_{date}.json'), 'w'), indent=1)
    print('L0 failures', out['l0_failures'][:6], 'void volume range', min(r['void_volume'] for r in rows), max(r['void_volume'] for r in rows),
          'thin max', max(r['thin_fraction'] for r in rows), 'overhang max', max(r['overhang_fraction'] for r in rows))
