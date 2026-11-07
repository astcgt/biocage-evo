"""V17(h): slip ONSET on the verifier's block deck (V07 geometry, mu 0.3, Fn 4 N), production vs patch-6/7 build (env
BIOCAGE_STICK_MEMORY=1). The stick-memory law must not only hold (v17f: zero creep) but also SLIP at the Coulomb limit: the
plate is driven in x by a prescribed displacement (0 -> XEND over t 0.4-1.0) instead of a force, and the tangential
reaction Fx is read from the rigid-body log. Coulomb answer: |Fx| rises elastically, then plateaus at mu |Fz| = 1.2 N,
independent of the increment count; the production law (anchor reset every increment) carries only one increment's
elastic stretch, so its |Fx| depends on the step size. Writes results/gpufe_verify/v2/v17h_block_slip_onset.json.
usage: python v17h_block_slip_onset.py [patched_febio]"""
import os, sys, shutil, importlib.util, numpy as np
from prov import ROOT, OLD, provenance, save
sp = importlib.util.spec_from_file_location('v07', os.path.join(ROOT, 'work/agents/verifier/v07_stick_creep.py')); v = importlib.util.module_from_spec(sp); sp.loader.exec_module(v)
PATCHED = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OLD, 'third_party/FEBio/cbuild_fric/bin/febio4'); PROD = v.FEBIO
W = os.path.join(ROOT, 'results/gpufe_verify/v2/v17h_block_slip_onset'); XEND = 0.5
rep = dict(prov=provenance([PATCHED]), patched=PATCHED, production=PROD, mu=v.MU, Fn=v.FN, x_end=XEND, rows=[],
           note='plateau = mean |Fx| / (mu |Fz|) over t 0.8-1.0 (plate x 0.33-0.5 mm, far past the elastic stick range)')
for E in (10, 400):
    for n in (10, 40):
        for binary, tag, mem in ((PROD, 'prod', 0), (PATCHED, 'patch', 1)):
            d = f'{W}/E{E}_n{n}_{tag}'; shutil.rmtree(d, ignore_errors=True); os.makedirs(d); fp = d + '/case.feb'
            v.write(fp, E, n); s = open(fp).read()
            os.environ.pop('BIOCAGE_STICK_MEMORY', None)
            if mem: os.environ['BIOCAGE_STICK_MEMORY'] = '1'
            s = s.replace(f'<force bc="x" lc="2">{v.RATIO * v.MU * v.FN}</force>', f'<prescribed bc="x" lc="2">{XEND}</prescribed>', 1)
            s = s.replace('<loadcurve id="2" type="linear"><point>0,0</point><point>0.4,0</point><point>0.5,1</point><point>1,1</point></loadcurve>',
                          '<loadcurve id="2" type="linear"><point>0,0</point><point>0.4,0</point><point>1,1</point></loadcurve>', 1)
            s = s.replace('<Control>', '<Control><min_residual>1e-8</min_residual>', 1)
            assert 'prescribed bc="x"' in s and '<point>0.5,1</point>' not in s
            open(fp, 'w').write(s); v.FEBIO = binary
            ok, R = v.febio(d); ts = np.array(sorted(R)); Fx = np.array([R[t][3] for t in ts]); Fz = np.array([R[t][4] for t in ts]); x = np.array([R[t][0] for t in ts])
            at = lambda T, a: float(np.interp(T, ts, a)) if len(ts) and ts[-1] >= T - 1e-9 else None
            pl = [abs(Fx[i]) / (v.MU * abs(Fz[i])) for i in range(len(ts)) if ts[i] >= 0.8 - 1e-9 and abs(Fz[i]) > 0]
            r = dict(E=E, n=n, binary=tag, normal=ok, t_last=float(ts[-1]) if len(ts) else None,
                     Fx={T: at(T, Fx) for T in (0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)}, x={T: at(T, x) for T in (0.5, 1.0)},
                     plateau_ratio=float(np.mean(pl)) if pl else None, plateau_spread=float(np.max(pl) - np.min(pl)) if pl else None)
            rep['rows'].append(r); print(f"E {E:3d} n {n:2d} {tag:5s} ok {ok} t_last {r['t_last']} |Fx|/(mu|Fz|) plateau {r['plateau_ratio']} spread {r['plateau_spread']} Fx(0.5) {r['Fx'][0.5]}", flush=True)
print('saved', save('v17h_block_slip_onset', rep))
