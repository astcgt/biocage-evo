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
import kern, solver as S
from solver import TRA, ROT, rotvec_to_R
from mech import DT


def _to_cp(t): return cp.from_dlpack(t.contiguous())


def _to_t(a): return torch.from_dlpack(a)


class NewtonSolver(S.Solver):
    def __init__(self, model, opts=None):
        o = dict(dtol=None, etol=None, rtol=None, stop_unconverged=True, max_newton=60, refactor_every=8, contact_band=0.05, ls_max=6)
        o.update(opts or {}); super().__init__(model, o)
        self._pattern = None; self._ds = None; self._dsP = None

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
            else:
                tri, L, q, nrm, d = p.project(x)
                g = ((q - x[p.s]) * nrm).sum(-1)
                act = ((g > -self.o['contact_band']) & (d < p.R)).to(DT)
                M = torch.eye(3, dtype=DT, device=self.dev).expand(len(k), 3, 3) if p.mu > 0 else nrm[:, :, None] * nrm[:, None, :]
            wv = torch.cat([torch.ones(len(k), 1, dtype=DT, device=self.dev), -L], 1)            # slave, master a, b, c
            Kc = (k * act)[:, None, None, None, None] * wv[:, :, None, None, None] * wv[:, None, None, :, None] * M[:, None, :, None, :]
            add_blocks(torch.cat([p.s[:, None], tri], 1), Kc)
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
        dg = Kr.diagonal(); reg = 1e-10 * float(cp.abs(dg).max())
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
        conv = False; it = 0; nfac = 0; U = torch.zeros(self.nd, dtype=DT, device=self.dev)
        for it in range(1, o['max_newton'] + 1):
            if (it - 1) % o['refactor_every'] == 0:
                self._factor(x); nfac += 1
            du = self._solve(g)
            gn = float(g.norm()); a = 1.0
            for _ in range(o['ls_max']):
                xn, saved = self._update(x, du, a)
                gnew, r = self._gres(xn)
                if float(gnew.norm()) < gn or a < 0.02: break
                for k, (c_, R_) in saved.items(): self.rb[k]['c'], self.rb[k]['R'] = c_, R_
                a *= 0.5
            if it == 1:                                                   # FEBio FESolidSolver2::Quasin initial norms
                normRi = float(g @ g); normEi = abs(float(du @ g))
            ui = a * du; U = U + ui
            normR1 = float(gnew @ gnew); normu = float(ui @ ui); normU = float(U @ U); normE1 = abs(float(ui @ gnew))
            x, g = xn, gnew
            for p in self.passes:
                if p.kind != 'tied': p.search(x)
            if o['log_every']:
                print(f'  {label} newton {it} R {normR1:.2e}/{normRi:.2e} E {normE1:.2e}/{normEi:.2e} u {normu:.2e}/{normU:.2e} a {a:.3f}', flush=True)
            if not (normR1 == normR1 and normu == normu): break             # NaN
            ok = ((tol['rtol'] <= 0 or normR1 <= tol['rtol'] * normRi) and (tol['dtol'] <= 0 or normu <= tol['dtol']**2 * normU)
                  and (tol['etol'] <= 0 or normE1 <= tol['etol'] * normEi))
            if ok or normR1 <= 1e-24 * max(normRi, 1e-300):
                conv = True; break
        self.x = x
        info = dict(iters=it, factorizations=nfac, converged=conv, seconds=_time.time() - t0, res=float(g.norm()))
        if not conv and o['stop_unconverged']:                            # F-0004: never continue from an unconverged state
            raise RuntimeError(f'Newton not converged at t={self.t:.4f} ({label}): {info}')
        return info

    def _tols(self):
        """FEBio convergence tolerances: opts override, else the step's Control block, else FEBio defaults."""
        ctl = getattr(self, 'ctl', None) or {}
        d = dict(dtol=0.001, etol=0.01, rtol=0.0)
        return {k: self.o.get(k) if self.o.get(k) is not None else ctl.get(k, v) for k, v in d.items()}
