PI decisions since round 1 (2026-10-26): mu 0.3 main (0.2 / 0.45 sensitivity); S4 floor 50 %; S5 kept; S9 = no slip-out in any direction (> 1 mm = fail), posterior migration absolutely unacceptable; physio load-curve bug found and fixed (DECISIONS.md 2026-10-26), physio reruns in human_study/al_v2/physio_fix/.
More PI decisions 2026-10-26: posterior migration <= 0.5 mm, posterior push-out >= 135 N; support period >= 16 weeks (Lintz 2021,
docs/PRIOR_FAILURES_Lintz2021.md - read it: the lab's previous PLA cages all fractured posteriorly); no imaging marker;
any feasible insertion method allowed, but the hard-core compression problem must be solved (docs/DECISIONS.md, insertion feasibility).
Commit 434c30b holds the load-curve fix.
Repository moved 2026-10-26: this round runs in biocage-evo (paths: work/, docs/, results/, gpufe/). Endplate: no bone shaping, soft tissue only; transient distraction limit being researched.

Updates 2026-10-27 (GPU solver, commit after 6000504; read results/gpufe_verify/ and gpufe/):
- Newton non-convergence explained: residual was already at round-off (1e-4 N total), the old relative test was mis-scaled.
  Now FEBio's own criteria (FESolidSolver2::Quasin: dtol / etol / rtol from the Control block) and the run stops when an
  increment does not converge (F-0004). Rigid-body rotation dofs now get their geometric stiffness and live lever arms.
- F-0003 fixed (sticking nodes keep their stick point, FEBio rule). New gate 1d (stick memory, 3 shear cycles, 10/20/40
  increments): FEBio rule passes; the old rule leaves a residual |Fx/Fz| ~ 0.02 (reproduces the red team's finding).
- Gate 2 (intact FSU vs FEBio): flexion PASS (5.766 vs 5.781 deg, 0.26 %). The other 5 directions currently FAIL with NaN at
  t 1.2-1.3, when the facet joints come into contact (frictionless sliding contact with Newton); being fixed now.
- PI: verifier, safety guard and red team may run now (round 2 moved forward); designer still not started.
