"""GPU implicit solver: (modified) Newton with the exact element tangent and a cuDSS sparse direct solve.

Why not pure dynamic relaxation: with bone (12 GPa) and nucleus (1 MPa, nu 0.49) in one model the explicit iteration
needs > 10^4 iterations per load increment (gate 2 diagnostic, 2026-10-26). Here each increment is a few Newton steps.
Friction keeps the explicit treatment of solver.py (stick trial from the increment-start anchor, Coulomb return to the
slip cone, exactly as FESlidingElasticInterface::ContactTraction); the tangent used for the solve is a fixed,
slightly stiffer approximation (contact penalty k I on touching nodes), so a stick / slip switch never makes the
linear system jump (initial-stiffness idea, Zienkiewicz) and the iteration stays a contraction; backtracking on the
residual norm guards the large steps.

Unknowns: free node dofs + free rigid-body dofs (translation of the COM, small rotation about it); a prolongation
matrix P maps them to all node dofs (rigid nodes: dx = dc + dtheta x (x - c)), K_red = P^T K P.
Element tangents come from forward-mode autodiff of the same stress functions verified in gate 1 (kern.P_*).
"""
import time as _time, numpy as np, torch, cupy as cp, cupyx.scipy.sparse as csp
from nvmath.sparse.advanced import DirectSolver
import kern, contact, solver as S
from solver import TRA, ROT, rotvec_to_R
from mech import DT


def _to_cp(t): return cp.from_dlpack(t.contiguous())


def _to_t(a): return torch.from_dlpack(a)


class NewtonSolver(S.Solver):
    def __init__(self, model, opts=None):
        o = dict(dtol=None, etol=None, rtol=None, stop_unconverged=True, max_newton=60, refactor_every=None, ls_conv_min=0.1, max_cuts=6, reg=1e-16, res_abs=0.05, line_search='energy', max_du=0.05, ls_min=0.01, ls_iter=5, contact_band=0.05, ls_max=6)
        o.update(opts or {}); super().__init__(model, o)
        self._pattern = None; self._ds = None; self._dsP = None
        if self.o['refactor_every'] is None:                              # contact changes the tangent from step to step: full Newton
            self.o['refactor_every'] = 1 if any(p.kind == 'sliding' for p in self.passes) else 8

    # -------------------------------------------------------------- dof map
    def _dofmap(self, x):
        N = self.m['N']; dev = self.dev
        freeN = ~(self.fixed | self.is_rigid[:, None])                      # (N, 3)
        nf = int(freeN.sum()); col = -torch.ones(N, 3, dtype=torch.long, device=dev)
        col[freeN] = torch.arange(nf, device=dev)
        rows, cols, vals = [torch.nonzero(freeN.reshape(-1))[:, 0]], [col[freeN]], [torch.ones(nf, dtype=DT, device=dev)]
        nd = nf; self.rcols = {}
        for k, rb in self.rb.items():
            mode = self.rmode[k]
            allowed = [mode[d] in ('free', 'force') for d in ('x', 'y', 'z')] + [mode[d] in ('free', 'force') for d in ('Rx', 'Ry', 'Rz')]
            idx = [i for i in range(6) if allowed[i]]
            if not idx: continue
            cmap = {i: nd + a for a, i in enumerate(idx)}; nd += len(idx); self.rcols[k] = cmap
            nodes = rb['nodes']; r = x[nodes] - rb['c']
            for d in range(3):
                if d in cmap:
                    rows.append(3 * nodes + d); cols.append(torch.full_like(nodes, cmap[d])); vals.append(torch.ones(len(nodes), dtype=DT, device=dev))
            # dx = dtheta x r  ->  dx_d = sum_e eps_{d e f}... written out
            M = {(0, 1): r[:, 2], (0, 2): -r[:, 1], (1, 0): -r[:, 2], (1, 2): r[:, 0], (2, 0): r[:, 1], (2, 1): -r[:, 0]}
            for (d, e), v in M.items():
                if 3 + e in cmap:
                    rows.append(3 * nodes + d); cols.append(torch.full_like(nodes, cmap[3 + e])); vals.append(v)
        R_, C_, V_ = torch.cat(rows), torch.cat(cols), torch.cat(vals)
        self.P = csp.coo_matrix((_to_cp(V_), (_to_cp(R_), _to_cp(C_))), shape=(3 * N, nd)).tocsr()
        self.PT = self.P.T.tocsr()
        self.freeN, self.colN, self.nd, self.nf = freeN, col, nd, nf

    # -------------------------------------------------------------- tangent
    def _entries(self, x):
        """COO entries (rows, cols, vals) of the full 3N x 3N tangent."""
        R, C, V = [], [], []
        def add_blocks(nodes, K):                          # nodes (E, n), K (E, n, 3, n, 3)
            E_, n = nodes.shape
            dof = (3 * nodes[:, :, None] + torch.arange(3, device=self.dev)).reshape(E_, 3 * n)
            R.append(dof[:, :, None].expand(E_, 3 * n, 3 * n).reshape(-1)); C.append(dof[:, None, :].expand(E_, 3 * n, 3 * n).reshape(-1))
            V.append(K.reshape(E_, 3 * n, 3 * n).reshape(-1))
        for g in self.groups:
            p = g.prm
            if g.kind == 'neo': prm = (p['mu'], p['lam'])
            elif g.kind == 'ortho': prm = (p['A'], g.mu_t, g.lam_t)
            elif g.kind == 'hmfib': prm = (p['mu'], p['lam'], p['beta'], p['a0'], p['ksi0'], p['alpha0'], p['fbeta0'], p['a1'], p['ksi1'], p['alpha1'], p['fbeta1'])
            elif g.kind == 'gentps': prm = (g.V0, p['G'], p['k'], p['Jm'], self._Fp(g))
            K = kern.elem_tangent(g.kind, x[g.conn], g.G, g.w, prm)
            add_blocks(g.conn, K)                          # internal force tangent
        if self.spr is not None:
            sp = self.spr; d = x[sp['j']] - x[sp['i']]; L = d.norm(dim=-1); n = d / L[:, None]
            ys = sp['ys']; S_ = ys.shape[1]; DL = L - sp['L0']
            u = ((DL - sp['x0'][sp['cid']]) / sp['dx'][sp['cid']]).clamp(0, S_ - 2); k0 = u.floor().long()
            flat = ys.reshape(-1); base = sp['cid'] * S_
            Fm = flat[base + k0] + (flat[base + k0 + 1] - flat[base + k0]) * (u - k0)
            kt = (flat[base + k0 + 1] - flat[base + k0]) / sp['dx'][sp['cid']]
            I = torch.eye(3, dtype=DT, device=self.dev)
            Kab = kt[:, None, None] * n[:, :, None] * n[:, None, :] + (Fm / L)[:, None, None] * (I - n[:, :, None] * n[:, None, :])
            Kp = torch.zeros(len(L), 2, 3, 2, 3, dtype=DT, device=self.dev)
            Kp[:, 0, :, 0], Kp[:, 1, :, 1], Kp[:, 0, :, 1], Kp[:, 1, :, 0] = Kab, Kab, -Kab, -Kab
            add_blocks(torch.stack([sp['i'], sp['j']], 1), Kp)
        for p in self.passes:
            psf = 1.0 if p.plc is None else self.lc(p.plc)
            if psf == 0 or (p.kind == 'tied' and (p.tie_off is None or self.t < p.init_time - 1e-12)): continue
            k = p.k * psf
            if p.kind == 'tied':
                tri, L = p.anchor_tri, p.anchor_L; M = torch.eye(3, dtype=DT, device=self.dev).expand(len(k), 3, 3)
                act = p.anchor_ok.to(DT)
            elif p.mu == 0:                                               # frictionless: exact tangent (normal, its rotation,
                tri, L, q, nrm, d = p.project(x)                          # projection point) by forward-mode autodiff
                nodes = torch.cat([p.s[:, None], tri], 1); xe = x[nodes]
                T = torch.eye(12, dtype=DT, device=self.dev).reshape(12, 1, 4, 3).expand(12, len(k), 4, 3)
                dK = torch.func.vmap(lambda t: torch.func.jvp(lambda y: contact.pair_forces(y, k, p.R, p.lam * psf), (xe,), (t,))[1])(T)
                add_blocks(nodes, -dK.permute(1, 2, 3, 0).reshape(len(k), 4, 3, 4, 3))
                continue
            else:
                tri, L, q, nrm, d = p.project(x)
                g = ((q - x[p.s]) * nrm).sum(-1)
                act = ((g > -self.o['contact_band']) & (d < p.R)).to(DT)
                M = torch.eye(3, dtype=DT, device=self.dev).expand(len(k), 3, 3) if p.mu > 0 else nrm[:, :, None] * nrm[:, None, :]
            wv = torch.cat([torch.ones(len(k), 1, dtype=DT, device=self.dev), -L], 1)            # slave, master a, b, c
            Kc = (k * act)[:, None, None, None, None] * wv[:, :, None, None, None] * wv[:, None, None, :, None] * M[:, None, :, None, :]
            add_blocks(torch.cat([p.s[:, None], tri], 1), Kc)
        for Pq in self.pressure:                                          # follower pressure: load stiffness (non-symmetric)
            pv = Pq['scale'] * self.lc(Pq['lc'])
            if pv == 0: continue
            xq = x[Pq['q']]; cols = []
            for b in range(4):
                for j in range(3):
                    t = torch.zeros_like(xq); t[:, b, j] = 1.0
                    cols.append(-torch.func.jvp(lambda y: S.Solver.pressure_q(y, pv), (xq,), (t,))[1])
            add_blocks(Pq['q'], torch.stack(cols, -1).reshape(xq.shape[0], 4, 3, 4, 3))
        return torch.cat(R), torch.cat(C), torch.cat(V)

    def _assemble(self, x):
        R_, C_, V_ = self._entries(x)
        N3 = 3 * self.m['N']
        if self._pattern is None or self._pattern[0] != len(R_):
            key = R_ * N3 + C_
            uk, inv = torch.unique(key, return_inverse=True)
            self._pattern = (len(R_), uk, inv)
        _, uk, inv = self._pattern
        data = torch.zeros(len(uk), dtype=DT, device=self.dev); data.index_add_(0, inv, V_)
        rows = uk // N3; cols = uk % N3
        indptr = torch.zeros(N3 + 1, dtype=torch.long, device=self.dev); indptr.index_add_(0, rows + 1, torch.ones_like(rows)); indptr = indptr.cumsum(0)
        K = csp.csr_matrix((_to_cp(data), _to_cp(cols), _to_cp(indptr)), shape=(N3, N3))
        Kr = (self.PT @ K @ self.P).tocsr()
        Kg = self._rigid_geo(x)
        if Kg is not None: Kr = (Kr + Kg).tocsr()
        Kr.sum_duplicates(); Kr.sort_indices()
        dg = Kr.diagonal(); reg = self.o['reg'] * float(cp.abs(dg).max())
        Kr = (Kr + csp.identity(Kr.shape[0], dtype=np.float64, format='csr') * reg).tocsr(); Kr.sort_indices()
        return Kr

    def _rigid_geo(self, x):
        """geometric stiffness of the rigid-body rotation dofs: the rigid nodes carry large individual forces (prestrain,
        reactions), and rotating the body turns them; with g = J(u)^T r(x(u)), K_red = J^T K J - H.r with
        (H.r)_ab = sum_i [ (f_b r_a + f_a r_b) / 2 - (r . f) delta_ab ], r_i = x_i - c, f_i = residual force on node i."""
        rr_all = None; R_, C_, V_ = [], [], []
        for k, cmap in self.rcols.items():
            rot = [i for i in (3, 4, 5) if i in cmap]
            if not rot: continue
            if rr_all is None: rr_all = self.residual(x)
            rb = self.rb[k]; r = x[rb['nodes']] - rb['c']; f = rr_all[rb['nodes']]
            A = r.T @ f                                                   # A[a, b] = sum r_a f_b
            H = 0.5 * (A + A.T) - torch.trace(A) * torch.eye(3, dtype=DT, device=self.dev)
            for a in rot:
                for b in rot:
                    R_.append(cmap[a]); C_.append(cmap[b]); V_.append(-H[a - 3, b - 3])
        if not R_: return None
        return csp.coo_matrix((_to_cp(torch.stack(V_)), (cp.asarray(R_), cp.asarray(C_))), shape=(self.nd, self.nd)).tocsr()

    def _factor(self, x):
        Kr = self._assemble(x)
        same = (self._ds is not None and self._Kr.shape == Kr.shape and self._Kr.nnz == Kr.nnz
                and bool(cp.all(self._Kr.indptr == Kr.indptr)) and bool(cp.all(self._Kr.indices == Kr.indices)))
        if same:
            self._Kr.data[...] = Kr.data                  # in-place value update: plan (reordering) reused
        else:
            if self._ds is not None: self._ds.free()
            self._Kr = Kr; self._b = cp.zeros(Kr.shape[0], dtype=np.float64)
            self._ds = DirectSolver(self._Kr, self._b); self._ds.plan(); self.n_plans = getattr(self, 'n_plans', 0) + 1
        self._ds.factorize()

    def _solve(self, g):
        self._b[...] = _to_cp(g)
        return _to_t(self._ds.solve()).clone()

    # -------------------------------------------------------------- residual in reduced dofs
    def _gres(self, x):
        if self.rcols: self._dofmap(x)                                        # rigid lever arms follow the rotation
        r = self.residual(x)
        for k, rb in self.rb.items():                                         # reactions / applied loads (bookkeeping)
            rr = x[rb['nodes']] - rb['c']; fn = r[rb['nodes']]
            Fr = fn.sum(0); Mr = torch.cross(rr, fn, dim=-1).sum(0)
            Fa, Ma = self._rigid_targets(k)
            rb['F'], rb['M'] = -Fr, -Mr; rb['Rf'], rb['Rm'] = Fr + Fa, Mr + Ma
        g = _to_t(self.PT @ _to_cp(r.reshape(-1))).clone()
        for k, cmap in self.rcols.items():
            Fa, Ma = self._rigid_targets(k); rb = self.rb[k]
            for i, c in cmap.items():
                g[c] += (Fa[i] if i < 3 else Ma[i - 3])
        return g, r

    def _update(self, x, du, a):
        x = x.clone(); fN = self.freeN
        x[fN] = x[fN] + a * du[self.colN[fN]]
        saved = {k: (rb['c'].clone(), rb['R'].clone()) for k, rb in self.rb.items()}
        for k, cmap in self.rcols.items():
            rb = self.rb[k]; t = torch.zeros(3, dtype=DT, device=self.dev); w = torch.zeros(3, dtype=DT, device=self.dev)
            for i, c in cmap.items():
                (t if i < 3 else w)[i % 3] = a * du[c]
            rb['c'] = rb['c'] + t; rb['R'] = rotvec_to_R(w) @ rb['R']
        self._prescribe_rigid()
        self._apply_rigid(x)
        return x, saved

    def _prescribe_rigid(self):
        for k, rb in self.rb.items():
            mode = self.rmode[k]
            for d, i in TRA.items():
                if mode[d] in ('fixed', 'presc'):
                    tgt = 0.0 if mode[d] == 'fixed' else self.rval[k][d]['scale'] * self.lc(self.rval[k][d]['lc'])
                    rb['c'][i] = rb['com0'][i] + tgt
            if any(mode[d] in ('fixed', 'presc') for d in ROT) and not all(mode[d] in ('fixed', 'presc') for d in ROT):
                pass                                                          # partial rotation fixes are not used in these models
            elif all(mode[d] in ('fixed', 'presc') for d in ROT):
                w = torch.tensor([0.0 if mode[d] == 'fixed' else self.rval[k][d]['scale'] * self.lc(self.rval[k][d]['lc']) for d in ROT],
                                 dtype=DT, device=self.dev)
                rb['R'] = rotvec_to_R(w)

    # -------------------------------------------------------------- one load increment
    def relax(self, label=''):
        o = self.o; t0 = _time.time()
        self._update_fixed_val()
        x = torch.where(self.fixed, self.fixed_val, self.x)
        self._prescribe_rigid(); self._apply_rigid(x)
        for p in self.passes:
            if p.kind != 'tied': p.search(x)
            if p.kind == 'sliding' and p.mu > 0: p.set_anchor(x)
        self._dofmap(x)
        g, r = self._gres(x)
        tol = self._tols()
        nfac = 0; tot = 0; naug = 0
        while True:                                                       # augmented Lagrangian passes (FEBio laugon)
            conv = False; it = 0; U = torch.zeros(self.nd, dtype=DT, device=self.dev); fresh = False; why = 'max_newton'
            while it < o['max_newton']:
                it += 1; tot += 1
                if (it - 1) % o['refactor_every'] == 0 and not fresh:
                    self._factor(x); nfac += 1; fresh = True
                du = self._solve(g)
                gn = float(g.norm())
                if o['max_du']:                                           # step-length limiter: no node moves more than max_du
                    dmax = float(_to_t(self.P @ _to_cp(du)).reshape(-1, 3).norm(dim=1).max())   # mm per iteration, so a
                    if dmax > o['max_du']: du = du * (o['max_du'] / dmax)                   # predictor in the soft neutral zone
                                                                                            # cannot jump through the facets
                if o['line_search'] == 'energy':
                    a, xn, gnew, r = self._line_search_energy(x, du, g)
                    if not (float(gnew.norm()) < 1e6 * max(gn, 1e-12)):        # blow-up (or NaN): this increment fails
                        self._update_back(xn); why = 'diverged'; break
                else:
                    a = 1.0; dec = False
                    for _ in range(o['ls_max']):
                        xn, saved = self._update(x, du, a)
                        gnew, r = self._gres(xn)
                        if float(gnew.norm()) < gn: dec = True; break
                        self._restore_rb(saved); a *= 0.5
                    if not dec:                                               # no descent along this direction
                        self._gres(x)
                        if gn <= o['res_abs']: conv = True; break             # already in equilibrium to the absolute floor
                        if not fresh:                                         # stale tangent: refactor here and try again
                            self._factor(x); nfac += 1; fresh = True; it -= 1; continue
                        why = 'line search'; break                            # fresh tangent and still no descent: the increment fails
                fresh = False
                if it == 1:                                                   # FEBio FESolidSolver2::Quasin initial norms
                    normRi = float(g @ g); normEi = abs(float(du @ g))
                ui = a * du; U = U + ui
                normR1 = float(gnew @ gnew); normu = float(ui @ ui); normU = float(U @ U); normE1 = abs(float(ui @ gnew))
                x, g = xn, gnew
                if any(p.kind != 'tied' for p in self.passes):
                    for p in self.passes:
                        if p.kind != 'tied': p.search(x)
                    g, r = self._gres(x)                                      # new candidates can change the projections
                if o['log_every']:
                    print(f'  {label} newton {it} R {normR1:.2e}/{normRi:.2e} E {normE1:.2e}/{normEi:.2e} u {normu:.2e}/{normU:.2e} a {a:.3f}', flush=True)
                if not (normR1 == normR1 and normu == normu): why = 'NaN'; break
                ok = ((tol['rtol'] <= 0 or normR1 <= tol['rtol'] * normRi) and (tol['dtol'] <= 0 or normu <= tol['dtol']**2 * normU)
                      and (tol['etol'] <= 0 or normE1 <= tol['etol'] * normEi))
                # a strongly cut line step makes the displacement / energy norms small without equilibrium (FEBio: s < LSmin)
                # absolute floor: total out-of-balance force <= res_abs (0.05) N over the whole model (loads: 1.5 N m moments, joint
                # forces of tens of N); FEBio's relative norms alone stall when an increment starts almost in equilibrium
                if (ok and a >= o['ls_conv_min']) or normR1 <= 1e-24 * max(normRi, 1e-300) or float(g.norm()) <= o['res_abs']:
                    conv = True; break
            if not conv or not self._augment(naug): break
            naug += 1; g, r = self._gres(x)
        self.x = x
        return dict(iters=tot, augmentations=naug, factorizations=nfac, converged=conv, seconds=_time.time() - t0, res=float(g.norm()),
                    why=None if conv else why)

    def _augment(self, naug):
        """FESlidingElasticInterface::Augment: per contact interface, lam_new = the converged contact pressure force
        (MBRACKET(lam + eps g)); done when |(|lam_new| - |lam|) / |lam_new|| < tolerance and naug >= minaug, or when
        naug >= maxaug. Returns True if multipliers were updated (another Newton pass needed)."""
        more = False; groups = {}
        for p in self.passes:
            if getattr(p, 'laugon', False): groups.setdefault(p.name, []).append(p)
        for name, ps in groups.items():
            psf = 1.0 if ps[0].plc is None else self.lc(ps[0].plc)
            if psf == 0: continue
            new = [p.force_n.clamp_min(0.0) / psf for p in ps]
            L0 = float(sum((p.lam ** 2).sum() for p in ps)) ** 0.5; L1 = float(sum((v ** 2).sum() for v in new)) ** 0.5
            pctn = abs((L1 - L0) / L1) if L1 > 0 else 0.0
            done = (pctn < ps[0].atol and naug >= ps[0].minaug) or naug >= ps[0].maxaug
            if self.o['log_every']: print(f'    augment {name} {naug}: |lam| {L0:.3e} -> {L1:.3e} pctn {pctn:.3e} {"done" if done else ""}', flush=True)
            if not done:
                for p, v in zip(ps, new): p.lam = v
                more = True
        return more

    def _restore_rb(self, saved):
        for k, (c_, R_) in saved.items(): self.rb[k]['c'], self.rb[k]['R'] = c_, R_

    def _update_back(self, xn):
        pass                                                              # the increment is restored by run() from its snapshot

    def _line_search_energy(self, x, du, g):
        """FEBio's line search (FECore/FELineSearch.cpp DoLineSearch), transcribed: energy r(s) = du . R(x + s du);
        accept when |r(s) / r(0)| <= lstol, else the quadratic step update of FEBio, at most ls_iter times, then the step
        with the smallest |r|; below ls_min the step 0.5 is used (FEBio / NIKE3D). Returns (s, x_new, g_new, r_new)."""
        o = self.o; lstol = self._tols()['lstol']
        r0 = float(du @ g); rmin = abs(r0); s = 1.0; smin = s; n = 0
        while True:
            xn, saved = self._update(x, du, s); g1, r = self._gres(xn)
            if s < o['ls_min']:
                self._restore_rb(saved); s = 0.5; xn, saved = self._update(x, du, s); g1, r = self._gres(xn); break
            r1 = float(du @ g1)
            if n == 0 or abs(r1) < rmin: smin, rmin = s, abs(r1)
            rr = 0.0 if abs(r1) < 1e-17 else abs(r1 / r0)
            if rr <= lstol: break
            a = r0 / r1; A = 1 + a * (s - 1); B = a * s * s; D = B * B - 4 * A * B
            if D >= 0:
                s_new = (B + D**0.5) / (2 * A)
                if s_new < 0: s_new = (B - D**0.5) / (2 * A)
                if s_new < 0: s_new = 0.0
            else:
                s_new = 0.5 * B / A
            if not (s_new == s_new) or s_new > 1.0: s_new = 0.5 if not (s_new == s_new) else 1.0   # A ~ 0 gives inf / NaN
            n += 1
            if n >= o['ls_iter']:
                self._restore_rb(saved); s = smin; xn, saved = self._update(x, du, s); g1, r = self._gres(xn); break
            self._restore_rb(saved); s = s_new
        return s, xn, g1, r

    # -------------------------------------------------------------- driver with automatic increment cutting
    def _snap(self):
        rb = {k: {n: v[n].clone() for n in ('c', 'R', 'F', 'M')} for k, v in self.rb.items()}
        ps = [{n: (getattr(p, n).clone() if torch.is_tensor(getattr(p, n)) else getattr(p, n))
               for n in ('anchor_tri', 'anchor_L', 'anchor_ok', 'stick', 'cand', 'tie_off', 'tied_done', 'force_n', 'force_t', 'gap', 'lam')} for p in self.passes]
        return self.x.clone(), self.t, rb, ps

    def _restore(self, S):
        x, t, rb, ps = S; self.x = x.clone(); self.t = t
        for k, v in rb.items(): self.rb[k].update({n: w.clone() for n, w in v.items()})
        for p, d in zip(self.passes, ps):
            for n, v in d.items(): setattr(p, n, v.clone() if torch.is_tensor(v) else v)

    def run(self, t_stop=None, on_increment=None, resume=None):
        """FEBio-like auto time stepping: the nominal increments (increments_per_step) are must-points; an increment that
        does not converge is retried from the last converged state with half the size (up to max_cuts halvings, else stop:
        F-0004); after an easy increment the size grows back (x1.5, never above nominal, never across a must-point).
        resume: a state from _snap() (e.g. a checkpoint); increments up to its time are skipped."""
        t = 0.0; hist = []; self.internal_scale = 1.0
        for si, st in enumerate(self.feb['steps']):
            ctl = st['control']; n = ctl['time_steps']; h = ctl['step_size']
            inc = self.o['increments_per_step'] or n
            t_end = t + n * h; dt0 = (t_end - t) / inc
            self._step_setup(st, t, t_end); self.ctl = ctl
            grid = [t + dt0 * k for k in range(1, inc + 1)]; gi = 0; dt = dt0; tc = t
            if resume is not None and resume[1] > t - 1e-12:
                if resume[1] >= t_end - 1e-12: t = t_end; continue
                self._restore(resume); tc = resume[1]; gi = sum(g_ <= tc + 1e-12 for g_ in grid)
            while gi < len(grid):
                S = self._snap(); cuts = 0
                while True:
                    tn = min(tc + dt, grid[gi])
                    self.t = tn
                    for p in self.passes:
                        if p.kind == 'tied' and not p.tied_done and self.t >= p.init_time - 1e-12:
                            p.tie(self.x); p.tied_done = True
                    self.internal_scale = max(self._force_scale(), 1e-6)
                    info = self.relax(label=f"{st['name']} t={self.t:.4f}")
                    if info['converged']: break
                    if self.o['verbose']: print(f"  [cut] t={tn:.5f} dt {tn - tc:.2e} failed ({info['why']}, {info['iters']} it): retry with half", flush=True)
                    self._restore(S); cuts += 1; dt = (tn - tc) / 2
                    if cuts > self.o['max_cuts']:
                        if self.o['stop_unconverged']:
                            raise RuntimeError(f'Newton not converged at t={tn:.5f} after {cuts - 1} cuts: {info}')
                        break
                info['dt'] = tn - tc; info['cuts'] = cuts
                tc = tn
                if abs(tc - grid[gi]) < 1e-12: gi += 1
                if info['iters'] <= 6 and cuts == 0: dt = min(dt * 1.5, dt0)
                row = self.record(); row.update(info, step=st['name']); hist.append(row)
                if self.o['verbose']:
                    print(f"[{st['name']}] t={self.t:.4f} dt {info['dt']:.3g} iters {info['iters']} {info['seconds']:.1f}s "
                          + ' '.join(f"{v['name']}: x {np.round(v['x'], 4).tolist()} th {np.round(v['th'], 5).tolist()} F {np.round(v['F'], 3).tolist()} M {np.round(v['M'], 2).tolist()}"
                                     for v in row['rigid'].values() if v['name'] != 'Fixed'), flush=True)
                if on_increment: on_increment(self, row)
                if t_stop is not None and self.t >= t_stop - 1e-12: return hist
            t = t_end
        return hist

    def _tols(self):
        """FEBio convergence tolerances: opts override, else the step's Control block, else FEBio defaults."""
        ctl = getattr(self, 'ctl', None) or {}
        d = dict(dtol=0.001, etol=0.01, rtol=0.0, lstol=0.9)
        return {k: self.o.get(k) if self.o.get(k) is not None else ctl.get(k, v) for k, v in d.items()}
