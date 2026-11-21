"""Subsidence-onset batch (PI 2026-11-19 test-gap plan item 1): methods/e08_subsidence.py on existing runs, no new simulation.
Designs: PASS + GREY classes of results/method/split/verdict_classes_merged.json.
Tied screening: the run that supplied each verdict value (comp_by_design_merged.json 'source'), read at its own evaluation time
(t 3.5 = sustained after insertion + 100 N follower; window t_eval = the state the compression verdict used).
Friction check: the route-E / fallback window of results/method/fric/verdicts.json (set / case_dir / w_<window>), read at the
verdict's evaluation state (intact ROM: obs01 t19rom t_eval; 1.5 N m: obs01 e04 target bracket) - not the window maximum.
Output: results/method/e08/<tag>.json per run + results/method/e08/summary.json.  usage: python ops/e08_batch.py [workers]
"""
import os, sys, json, glob
from concurrent.futures import ProcessPoolExecutor
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = '/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026/human_study/al_v2/'
OUT = os.path.join(E, 'results/method/e08'); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(E, 'methods')); import e08_subsidence as e8


OBS = os.path.join(E, 'results/method/obs01')
def fric_eval_time(p, w, evp):
    """the state the friction verdict used (advisor 11-19): intact ROM -> obs01 t19rom t_eval (fric_compare rule); 1.5 N m -> e04 target bracket t."""
    try:
        if evp in ('ROM', 'rom'): return json.load(open(os.path.join(OBS, f'FRIC__{p}__{w}.t19rom.json')))['t_eval']
        if evp: return json.load(open(os.path.join(OBS, f'FRIC__{p}__{w}.e04.json')))['windows'][w]['t']
    except (OSError, KeyError): return None
    return None


def job(a):
    tag, cd, times = a; o = os.path.join(OUT, tag + '.json')
    if os.path.exists(o): return tag, 'cached'
    try: e8.main(cd, o, times); return tag, 'ok'
    except Exception as ex: open(os.path.join(OUT, tag + '.err'), 'w').write(repr(ex)); return tag, 'error ' + repr(ex)[:200]


if __name__ == '__main__':
    cls = json.load(open(os.path.join(E, 'results/method/split/verdict_classes_merged.json')))['classes']
    comp = json.load(open(os.path.join(E, 'results/method/split/comp_by_design_merged.json')))
    fric = json.load(open(os.path.join(E, 'results/method/fric/verdicts.json')))
    ids = sorted(cls['PASS'] + cls['GREY/friction-posterior-0.45-0.55'])
    jobs, plan = {}, {}
    for p in ids:
        c = comp[p]; plan[p] = dict(cls='PASS' if p in cls['PASS'] else 'GREY', tied={}, fric={})
        req = {c['source']: {3.5}}
        for w, v in c['windows'].items(): req.setdefault(v['source'], set()).add(round(v['t_eval'], 4)); plan[p]['tied'][w] = (v['source'], v['t_eval'])
        plan[p]['tied']['sustained'] = (c['source'], 3.5)
        for src, ts in req.items():
            tag = 'tied__' + src.replace('/', '__'); jobs.setdefault(tag, [R + src, set()])[1].update(ts)
        for w, v in (fric.get(p, {}).get('windows') or {}).items():
            if not v.get('set') or not v.get('case_dir'): continue
            cd = R + f"{v['set']}/{v['case_dir']}/w_{w}"
            if os.path.exists(cd + '/case.xplt'):
                tag = f"fric__{v['set']}__{v['case_dir']}__{w}"; jobs[tag] = [cd, None]; plan[p]['fric'][w] = (tag, fric_eval_time(p, w, v.get('eval_point')))
    args = [(t, cd, sorted(ts) if ts else None) for t, (cd, ts) in jobs.items()]
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 6) as ex:
        for tag, st in ex.map(job, args): print(tag, st, flush=True)
    # ---- summary per design
    def val(tag, t):
        f = os.path.join(OUT, tag + '.json')
        if not os.path.exists(f) or t is None: return None
        rows = json.load(open(f))['states']; r = min(rows, key=lambda r: abs(r['t'] - t))
        return dict(t_eval=t, t=r['t'], **{k: r.get(k) for k in ('C3', 'C4', 'combined', 'C3_comp', 'C3_tens', 'C4_comp', 'C4_tens', 'C3_min_strain', 'C4_min_strain', 'C3_max_strain', 'C4_max_strain')})
    summ = {}
    for p, pl in plan.items():
        d = dict(cls=pl['cls'], tied={w: val('tied__' + s.replace('/', '__'), t) for w, (s, t) in pl['tied'].items()},
                 fric={w: val(tag, t) for w, (tag, t) in pl['fric'].items()})
        allv = [max(v['C3'] or 0, v['C4'] or 0) for v in list(d['tied'].values()) + list(d['fric'].values()) if v]
        d['worst_vertebra_max'] = max(allv) if allv else None; d['onset_10pct'] = bool(allv) and max(allv) > e8.ONSET
        summ[p] = d
    json.dump(dict(rule=e8.__doc__.split('\n')[2:6], designs=summ), open(os.path.join(OUT, 'summary.json'), 'w'), indent=1)
    print('onset', sum(d['onset_10pct'] for d in summ.values()), 'of', len(summ))
