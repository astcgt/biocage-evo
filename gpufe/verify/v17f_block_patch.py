"""V17(f): the verifier's block hold deck (V07) on the BIOCAGE patch-6/7 binary (env BIOCAGE_STICK_MEMORY=1) vs the production binary.
Coulomb answer: zero creep during the hold, independent of the increment count. usage: python v17f_block_patch.py [patched_febio]"""
import os, sys, shutil, importlib.util, numpy as np
from prov import ROOT, OLD, provenance, save
os.environ.setdefault('V07_RATIO', '0.5')
sp = importlib.util.spec_from_file_location('v07', os.path.join(ROOT, 'work/agents/verifier/v07_stick_creep.py')); v = importlib.util.module_from_spec(sp); sp.loader.exec_module(v)
PATCHED = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OLD, 'third_party/FEBio/cbuild_fric/bin/febio4'); PROD = v.FEBIO
W = os.path.join(ROOT, 'results/gpufe_verify/v2/v17f_block_patch'); rep = dict(prov=provenance([PATCHED]), patched=PATCHED, production=PROD, rows=[])
AUTO = '<time_stepper><dtmin>0.0005</dtmin><dtmax>0.1</dtmax><max_retries>10</max_retries><opt_iter>10</opt_iter></time_stepper>'
for ratio in (0.5, 0.9):
    v.RATIO = ratio
    for E in (10, 400):
        for n in (10, 40):
            for binary, tag, mem in ((PROD, 'prod', 0), (PATCHED, 'patch', 1), (PATCHED, 'patch_auto', 2)):
                d = f'{W}/r{ratio}_E{E}_n{n}_{tag}'; shutil.rmtree(d, ignore_errors=True); os.makedirs(d); fp = d + '/case.feb'
                v.write(fp, E, n); s = open(fp).read()
                os.environ.pop('BIOCAGE_STICK_MEMORY', None)
                if mem: os.environ['BIOCAGE_STICK_MEMORY'] = '1'   # patch 7 (2026-11-08): the switch is an env variable, no longer a deck parameter
                if mem == 2: s = s.replace('</Control>', AUTO + '</Control>', 1)   # same deck with FEBio's auto stepper (the cage decks have one)
                s = s.replace('<Control>', '<Control><min_residual>1e-8</min_residual>', 1)   # both binaries: hold increments start in equilibrium, FEBio's relative norms stall (|R|^2 floor)
                open(fp, 'w').write(s); v.FEBIO = binary
                ok, R = v.febio(d); ts = np.array(sorted(R)); x = np.array([R[t][0] for t in ts]) if len(ts) else np.array([])
                at = lambda T: float(np.interp(T, ts, x)) if len(ts) and ts[-1] >= T - 1e-9 else None
                r = dict(ratio=ratio, E=E, n=n, binary=tag, normal=ok, t_last=float(ts[-1]) if len(ts) else None, x05=at(0.5), x10=at(1.0)); r['creep'] = (r['x10'] - r['x05']) if r['x05'] is not None and r['x10'] is not None else None
                rep['rows'].append(r); print(f"ratio {ratio} E {E:3d} n {n:2d} {tag:5s} ok {ok} t_last {r['t_last']} x(0.5) {r['x05']} hold creep {r['creep']}", flush=True)
print('saved', save('v17f_block_patch', rep))
