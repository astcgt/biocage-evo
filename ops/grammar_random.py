"""Control arm R (ROUND2_ARCHITECTURE.md section E; PI 2026-11-18): random draws from the Design Grammar, no language model.
A draw = a ring of random width + 0-2 random struts / bar sets, 0-3 random material rules, random fabrication. Draws that
the Geometry Compiler refuses are discarded and counted (the refusal rate is itself reported).
usage: python ops/grammar_random.py <out_dir> <n> <seed> [d_mm=1.0]
"""
import os, sys, json, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom_compile as G


def draw(rng, base):
    parts = [dict(op='ring', outer=0.0, inner=float(rng.choice([0.4, 0.8, 1.2, 1.6])))]
    for _ in range(int(rng.integers(0, 3))):
        k = rng.choice(['strut_x', 'strut_y', 'bars'])
        if k == 'bars': parts.append(dict(op='bars', axis=str(rng.choice(['x', 'y'])), pitch=float(rng.choice([1.6, 2.4, 3.2])), width=float(rng.choice([0.4, 0.8])), phase=float(rng.uniform(0, 1.6))))
        else:
            c = float(rng.uniform(-3, 3)); w = float(rng.choice([0.4, 0.8, 1.2])); parts.append(dict(op='band', axis='x' if k == 'strut_x' else 'y', lo=round(c - w / 2, 2), hi=round(c + w / 2, 2)))
    rules = []
    for _ in range(int(rng.integers(0, 4))):
        k = rng.choice(['skin', 'posterior', 'anterior', 'lines', 'core']); v = float(rng.choice([0.0, 0.25, 0.5, 0.75]))
        w = (dict(op='face', side=str(rng.choice(['top', 'bottom', 'both'])), lo=0.0, hi=float(rng.choice([0.2, 0.4, 0.6]))) if k == 'skin' else dict(op='band', axis='x', lo=-50, hi=float(rng.uniform(-3, 0))) if k == 'posterior'
             else dict(op='band', axis='x', lo=float(rng.uniform(0, 3)), hi=50) if k == 'anterior' else dict(op='lines', **{'from': int(rng.integers(0, 3)), 'to': int(rng.integers(3, 6))}) if k == 'lines'
             else dict(op='face', side='both', lo=float(rng.choice([0.6, 1.0])), hi=99))
        rules.append(dict(where=w, value=v, mode='set'))
    return dict(base_mesh=base, fabrication=str(rng.choice(['interleave', 'mix'])), solid=dict(op='union', of=parts), phi=rules, source='control arm R: random draw from the grammar', mechanism=None)


if __name__ == '__main__':
    out, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); d = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    base = sorted(glob.glob(os.path.join(G.PLAT, f'human_study/al/meshes/cage_A_*_d{d:.3f}.npz')))[0]; rng = np.random.default_rng(seed); os.makedirs(out, exist_ok=True); built, tried, fails = 0, 0, {}
    while built < n and tried < 50 * n:
        tried += 1; spec = draw(rng, os.path.relpath(base, G.PLAT)); spec['name'] = f'R-{built + 1:02d}'; rep, _ = G.compile_spec(spec, os.path.join(out, spec['name'] + '.npz'))
        if rep['built']:
            built += 1; json.dump(spec, open(os.path.join(out, spec['name'] + '.spec.json'), 'w'), indent=1); json.dump(rep, open(os.path.join(out, spec['name'] + '.report.json'), 'w'), indent=1)
        else:
            for k, c in rep['checks'].items():
                if not c['ok']: fails[k] = fails.get(k, 0) + 1
    json.dump(dict(seed=seed, d_mm=d, built=built, tried=tried, refused=tried - built, refusal_reasons=fails), open(os.path.join(out, 'summary.json'), 'w'), indent=1)
    print(json.dumps(dict(built=built, tried=tried, refusal_reasons=fails)))
