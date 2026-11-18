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
    print('L0 failures', out['l0_failures'][:6], 'void volume range', min(r['void_volume'] for r in rows), max(r['void_volume'] for r in rows),
          'thin max', max(r['thin_fraction'] for r in rows), 'overhang max', max(r['overhang_fraction'] for r in rows))
