"""NUM-16 (2026-11-18, no GPU): which interface-shear statistic is mesh-robust? Compare the production mesh (0.2 mm, physio_rot_split2/p062
w_flexion) and the fine mesh (cage HZ 0.1 mm, numconv_hz01/p062 w_flexion) at the 1.5 N m flexion state (e03 target bracket, interpolated):
per-face soft-side shear traction on the horizontal interfaces -> max, p99, p95, p90, median, area-weighted mean, and a patch average
(faces binned on a 0.5 mm in-plane grid, mean traction per patch, then p99 / max over patches). Tolerance of the label: 5 %.
usage: python num16_metric_check.py -> results/method/numconv/num16_metric_check.json"""
import os, sys, json, time, numpy as np
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(os.path.dirname(E), 'biocage_simulation_test_oct2026', 'human_study', 'al_v2') + '/'
sys.path[:0] = [os.path.join(E, 'methods'), os.path.join(E, 'common')]
import xplt, e03_mu_req as e3, e07_interface_shear as e7, xml.etree.ElementTree as ET
def tractions(cd, wn, patch=0.5):
    faces, loc = e7.interfaces(cd)
    A = np.array([loc[a] for a, b, n, h, ha in faces]); B = np.array([loc[b] for a, b, n, h, ha in faces]); N = np.array([n for a, b, n, h, ha in faces]); H = np.array([h for a, b, n, h, ha in faces]); HA = np.array([ha for a, b, n, h, ha in faces])
    root = ET.parse(os.path.join(cd, 'case.feb')).getroot(); X = {int(n.get('id')): np.array([float(v) for v in n.text.split(',')]) for n in root.find('Geometry').find('Nodes')}
    blocks = {i + 1: [[int(v) for v in e.text.split(',')] for e in eb] for i, eb in enumerate(root.find('Geometry').findall('Elements'))}
    cen = np.array([np.mean([X[k] for k in blocks[b][i]], axis=0) for b, i in A])        # face position ~ element-A centroid
    states = xplt.read(os.path.join(cd, 'case.xplt'))['states']; sch = json.load(open(os.path.join(cd, 'physio_schedule.json'))); k = e3.target_bracket(cd, sch)[wn]
    def ts_of(st):
        S = st['elem']['stress']; sa = e7.stress_tensor(np.stack([S[b][i] for b, i in A])); sb = e7.stress_tensor(np.stack([S[b][i] for b, i in B]))
        sig = np.where(HA[:, None, None], sb, sa); t = np.einsum('fij,fj->fi', sig, N); tn = np.einsum('fi,fi->f', t, N); return np.linalg.norm(t - tn[:, None] * N, axis=1)
    sa_, sb_ = e3.state_at(states, k['t_a']), e3.state_at(states, k['t_b'])
    ts = ts_of(sa_) + k['frac'] * (ts_of(sb_) - ts_of(sa_)) if (sb_ is not None and sa_ is not None and k['frac'] > 0) else ts_of(sa_ or sb_)
    ts, c = ts[H], cen[H]
    key = np.floor(c[:, :2] / patch).astype(int); patches = {}
    for i, kk in enumerate(map(tuple, key)): patches.setdefault(kk, []).append(ts[i])
    pm = np.array([np.mean(v) for v in patches.values()])
    return dict(n_faces=int(H.sum()), t_eval=k['t'], reached=k['reached'], max=float(ts.max()), p99=float(np.percentile(ts, 99)), p95=float(np.percentile(ts, 95)), p90=float(np.percentile(ts, 90)),
                median=float(np.median(ts)), mean=float(ts.mean()), n_patches=len(pm), patch_mean_p99=float(np.percentile(pm, 99)), patch_mean_max=float(pm.max()), patch_mean_p90=float(np.percentile(pm, 90)))
coarse = tractions(R + 'physio_rot_split2/p062/w_flexion', 'flexion'); fine = tractions(R + 'numconv_hz01/p062/w_flexion', 'flexion')
rel = {k: (fine[k] - coarse[k]) / coarse[k] for k in ('max', 'p99', 'p95', 'p90', 'median', 'mean', 'patch_mean_p99', 'patch_mean_max', 'patch_mean_p90')}
out = dict(generated=time.strftime('%Y-%m-%dT%H:%M'), window='p062 flexion at 1.5 N m (tied), horizontal interfaces, soft-side shear traction', coarse=coarse, fine=fine, fine_minus_coarse_rel=rel,
           within_5pct=[k for k, v in rel.items() if abs(v) <= 0.05], note='statistic candidates for a mesh-robust shear read-out (NUM-16); patch = 0.5 mm in-plane bins of face centroids')
os.makedirs(os.path.join(E, 'results/method/numconv'), exist_ok=True); json.dump(out, open(os.path.join(E, 'results/method/numconv/num16_metric_check.json'), 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ('note',)}, indent=1))
