"""Push-out read-out of an h53 push window (PI 2026-11-19 test-gap plan item 3; S9: posterior push-out >= 135 N, PI 2026-10-26).

A restart cannot declare new log output, so the force on the pushed node set is recovered from the cage element stresses:
nodal internal force f_a = sum_e integral_e sigma grad(N_a) dv (hex8, 2x2x2 Gauss points in the CURRENT configuration, one
element-average Cauchy stress per element = what the plot file stores). The push force is the X component of sum_a f_a over
the pushed nodes (contact forces acting directly on those wall nodes are neglected). Check: the 5 posterior-wall nodes that the
physio decks log in push_reaction.txt are pushed nodes of w_push_ant - the per-node recovered force is compared with them.
Cage motion: mean displacement of the cage nodes that are NOT pushed, relative to the C4 endplate node mean (X = anterior +).
2026-11-19 check result (p062 w_push_ant): per logged node the stress recovery gives 0.58-0.67 x the FEBio reaction, and the set
total is 0.87 x the contact-equilibrium force below - so the PRIMARY push force is now the equilibrium of the whole cage: the
only other loads on the cage are the contact forces of cage_top / cage_bot (plot variable 'contact force' = net force per
surface), hence push force = -(F_top + F_bot) along the push direction (quasi-static, exact up to the solver residual).
The stress-recovered value is kept as 'force_push_dir_stress_N' (lower bound).
usage: python e09_pushout.py <w_push_dir> <out.json>
"""
import sys, os, json, numpy as np, xml.etree.ElementTree as ET
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(E, 'common'))
import xplt
G = np.array([[a, b, c] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]) / np.sqrt(3)
XI = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float)   # FEBio hex8 node order
DN = np.array([[XI[a] * np.array([(1 + XI[a][1] * g[1]) * (1 + XI[a][2] * g[2]), (1 + XI[a][0] * g[0]) * (1 + XI[a][2] * g[2]),
                                   (1 + XI[a][0] * g[0]) * (1 + XI[a][1] * g[1])]) / 8 for a in range(8)] for g in G])   # (gauss, node, dxi)


def grad_int(P):
    """integral of grad N_a over each hex in configuration P (n, 8, 3) -> (n, 8, 3)."""
    out = np.zeros_like(P)
    for q in range(8):
        J = np.einsum('ai,naj->nij', DN[q], P)                 # dx/dxi (n, 3, 3): J[i, j] = d x_j / d xi_i
        det = np.linalg.det(J); Ji = np.linalg.inv(J)
        out += np.einsum('nij,aj->nai', Ji, DN[q]) * det[:, None, None]   # grad N_a = J^-1 dN/dxi
    return out


def main(wd, out):
    push = json.load(open(os.path.join(wd, 'push.json')))
    g = ET.parse(os.path.join(wd, 'case.feb')).getroot().find('Geometry')
    X = {int(n.get('id')): np.array([float(v) for v in n.text.split(',')]) for n in g.find('Nodes')}
    nid = np.array(sorted(X)); X0 = np.zeros((nid.max() + 1, 3)); X0[nid] = np.array([X[i] for i in nid])
    blocks = [(eb.get('name'), np.array([[int(v) for v in e.text.split(',')] for e in eb])) for eb in g.findall('Elements')]
    ns = {s.get('name'): np.array([int(n.get('id')) for n in s]) for s in g.findall('NodeSet')}
    pushed = set(i for one in push['pushed_node_set'].split('+') for i in ns[one].tolist())   # 2026-11-21: 'a+b' = carried push (both walls prescribed, h53 add2)
    cage = [(i, El) for i, (n, El) in enumerate(blocks) if n.startswith('cage_') and El.shape[1] == 8]
    cage_nodes = np.unique(np.concatenate([El.ravel() for i, El in cage])); free = np.array([i for i in cage_nodes if i not in pushed])
    sel = [(i, El, np.isin(El, list(pushed))) for i, El in cage]; sel = [(i, El, m) for i, El, m in sel if m.any()]
    c4 = np.loadtxt(os.path.join(wd, 'C4_endplate_nodes.txt'), delimiter=',', comments='*', max_rows=1, usecols=0) if False else None
    ep_ids = None
    for nd in ET.parse(os.path.join(wd, 'case.feb')).getroot().iter('node_data'):
        if nd.get('file') == 'C4_endplate_nodes.txt': ep_ids = np.array([int(v) for v in nd.text.split(',')])
    logged = None
    for nd in ET.parse(os.path.join(wd, 'case.feb')).getroot().iter('node_data'):
        if nd.get('file') == 'push_reaction.txt': logged = [int(v) for v in nd.text.split(',')]
    pf = xplt.read(os.path.join(wd, 'case.xplt')); rows = []
    sid = {v.get('name') if isinstance(v, dict) else v: k for k, v in pf['surfaces'].items()}
    for st in pf['states']:
        if st['time'] < 3.5 - 1e-6: continue
        U = next(iter(st['node']['displacement'].values())); S6 = st['elem']['stress']; f = {}
        for i, El, m in sel:
            P = X0[El] + U[El - 1]; GI = grad_int(P); s = S6[i + 1]
            sig = np.array([[s[:, 0], s[:, 3], s[:, 5]], [s[:, 3], s[:, 1], s[:, 4]], [s[:, 5], s[:, 4], s[:, 2]]]).transpose(2, 0, 1)
            fa = np.einsum('nij,naj->nai', sig, GI)                 # f_a,i = sigma_ij * int dN_a/dx_j
            for e, a in zip(*np.where(m)): f[El[e, a]] = f.get(El[e, a], 0) + fa[e, a]
        F = np.sum(list(f.values()), axis=0); u4 = U[ep_ids - 1].mean(0) if ep_ids is not None else np.zeros(3)
        cf = st['face'].get('contact force', {}); Fc = -sum(np.asarray(cf[sid[n]]).ravel() for n in ('cage_top', 'cage_bot'))
        r = dict(t=float(st['time']), push_mm=float(U[np.array(sorted(pushed)) - 1, 0].mean() - u4[0]), force_N=Fc.tolist(), force_push_dir_N=float(Fc[0] * np.sign(push['mm'])),
                 force_stress_N=F.tolist(), force_push_dir_stress_N=float(F[0] * np.sign(push['mm'])),
                 contact_normal_z_N=[float(np.asarray(cf[sid[n]]).ravel()[2]) for n in ('cage_top', 'cage_bot')],
                 cage_free_mean_mm=(U[free - 1].mean(0) - u4).tolist())
        if logged: r['recovered_logged_nodes'] = {str(n): f[n].tolist() for n in logged if n in f}
        rows.append(r)
    # logged reactions of the same nodes (FEBio Rx;Ry;Rz) for the check
    chk = None
    if logged and any(str(n) in rows[-1].get('recovered_logged_nodes', {}) for n in logged):
        txt = open(os.path.join(wd, 'push_reaction.txt')).read().split('*Step'); last = {}
        for blk in txt:
            t = None
            for line in blk.splitlines():
                if line.startswith('*Time'): t = float(line.split('=')[1])
                elif line[:1].isdigit() and t is not None and t >= 3.5 - 1e-6: v = [float(x) for x in line.split(',')]; last.setdefault(t, {})[int(v[0])] = v[1:]
        chk = []
        for r in rows:
            tl = min(last, key=lambda t: abs(t - r['t'])) if last else None
            if tl is None or abs(tl - r['t']) > 1e-4: continue
            for n, fr in r['recovered_logged_nodes'].items(): chk.append(dict(t=r['t'], node=int(n), recovered=fr, logged=last[tl].get(int(n))))
    if rows:                                                    # displacements relative to the window start (t 3.5 = activation of the push)
        p0, c0 = rows[0]['push_mm'], np.array(rows[0]['cage_free_mean_mm'])
        for r in rows: r['push_mm'] -= p0; r['cage_free_mean_mm'] = (np.array(r['cage_free_mean_mm']) - c0).tolist()
    Fp = np.array([r['force_push_dir_N'] for r in rows]); k = int(np.argmax(Fp)) if len(Fp) else None
    res = dict(window=wd, push=push, n_pushed=len(pushed), states=rows, reaction_check=chk,
               peak_N=float(Fp[k]) if k is not None else None, peak_at_push_mm=rows[k]['push_mm'] if k is not None else None,
               completed_push_mm=rows[-1]['push_mm'] if rows else None, meets_135N=bool(k is not None and Fp[k] >= 135.0),
               note='peak over the computed states; if the run stopped before 3 mm the peak is a lower bound unless the force already dropped')
    json.dump(res, open(out, 'w'), indent=1)
    return res


if __name__ == '__main__':
    r = main(sys.argv[1], sys.argv[2])
    print(json.dumps({k: r[k] for k in ('n_pushed', 'peak_N', 'peak_at_push_mm', 'completed_push_mm', 'meets_135N')}))
