"""V1 reader audit (plan docs/GPUFE_VERIFICATION_PLAN.md). Every element and attribute of a FEBio input is either USED by gpufe,
IGNORED with a stated reason, or a DEFECT (silently dropped by feb.py / solver.py though it changes the equations being solved).
Reasons were taken from reading gpufe/feb.py, solver.py, newton.py at the commit in the provenance block; run it again after any reader change.
usage: python v01_reader_audit.py [case.feb ...]"""
import os, sys, collections, xml.etree.ElementTree as ET
from prov import AL, provenance, save
USED = {'Contact': {'init_time', 'laugon', 'tolerance', 'penalty', 'auto_penalty', 'two_pass', 'search_radius', 'minaug', 'maxaug', 'fric_coeff'},
        'Control': {'time_steps', 'step_size', 'dtol', 'etol', 'rtol', 'lstol', 'time_stepper', 'dtmax'},
        'Boundary': {'fix', 'prescribe', 'rigid_body', 'fixed', 'prescribed', 'force'}, 'Step': {'Control', 'Boundary', 'Loads'}}
IGNORED = {'Contact': {'gaptol': 'FEBio default off (0)', 'search_tol': 'gpufe searches by nearest centroids, compared in V8 / V2', 'seg_up': 'segment update policy, numerical',
                       'tension': '0 everywhere in production', 'knmult': 'tangent only; residual term scales with the gap', 'symmetric_stiffness': 'solver matrix storage'},
           'Control': {'max_refs': 'iteration limit', 'max_ups': 'iteration limit', 'ls_check_jacobians': 'numerical', 'plot_level': 'output', 'dtmin': 'stepper', 'max_retries': 'stepper',
                       'opt_iter': 'stepper', 'symmetric_stiffness': 'solver matrix storage'}}
DEFECT_ALWAYS = {('Step', 'Constraints'): 'prescribed rotation drive (generic rigid joint) dropped: the window applies no rotation',
                 ('Control', 'analysis'): "analysis type dropped: FEBio window steps are type='dynamic' (density term), gpufe solves static",
                 ('Control', 'rhoi'): 'time-integration parameter of the dynamic step dropped', ('Contact', 'fric_coeff@lc'): 'friction load curve dropped: gpufe has mu from t 0, FEBio ramps it',
                 ('Control', 'dtmax@lc'): 'must-point curve dropped (increment sequence differs from FEBio)'}


def audit(path):
    r = ET.parse(path).getroot(); res = collections.defaultdict(collections.Counter); seen = collections.Counter()
    def tag(sec, name, ctx=''):
        k = (sec, name)
        if k in DEFECT_ALWAYS: res['DEFECT'][f'{sec}/{name}: {DEFECT_ALWAYS[k]}'] += 1
        elif name in USED.get(sec, ()): res['USED'][f'{sec}/{name}'] += 1
        elif name in IGNORED.get(sec, {}): res['IGNORED'][f'{sec}/{name}: {IGNORED[sec][name]}'] += 1
        else: res['UNKNOWN'][f'{sec}/{name}'] += 1
    for c in (r.find('Contact') if r.find('Contact') is not None else []):
        for k in c:
            tag('Contact', k.tag)
            for a in k.attrib:
                if not (k.tag == 'penalty' and a == 'lc'): tag('Contact', f'{k.tag}@{a}')
    def boundary(b):
        for e in b:
            tag('Boundary', e.tag)
            if e.tag == 'rigid_body':
                for x in e: tag('Boundary', x.tag)
    if r.find('Boundary') is not None: boundary(r.find('Boundary'))
    for st in r.findall('Step'):
        for x in st:
            tag('Step', x.tag)
            if x.tag == 'Control':
                for k in x:
                    if k.tag == 'analysis': res['DEFECT' if k.get('type') != 'static' else 'IGNORED'][f"Control/analysis type={k.get('type')}" + (f": {DEFECT_ALWAYS[('Control', 'analysis')]}" if k.get('type') != 'static' else ': static is what gpufe solves')] += 1; continue
                    tag('Control', k.tag)
                    if k.tag == 'time_stepper':
                        for q in k:
                            tag('Control', q.tag)
                            for a in q.attrib: tag('Control', f'{q.tag}@{a}')
            elif x.tag == 'Boundary': boundary(x)
    return {k: dict(v) for k, v in res.items()}


if __name__ == '__main__':
    decks = sys.argv[1:] or [os.path.join(AL, f) for f in ('physio_fric3/p062/w_extension/case.feb', 'physio_fix/p062_gpu2/case.feb')]
    rep = dict(prov=provenance(decks), decks={})
    for d in decks:
        a = audit(d); rep['decks'][os.path.relpath(d, AL)] = a
        print('==', os.path.relpath(d, AL), {k: sum(v.values()) for k, v in a.items()})
        for k in ('DEFECT', 'UNKNOWN'):
            for m, n in a.get(k, {}).items(): print(f'  {k} x{n}: {m}')
    rep['PASS'] = not any(a.get('DEFECT') or a.get('UNKNOWN') for a in rep['decks'].values())
    print('saved', save('v01_reader_audit', rep), 'PASS', rep['PASS'])
