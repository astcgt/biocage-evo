# Verifier notes (private)

## r0001 (2026-10-26) -> HOLD
- Gate 1 re-run bit-identical (v01_compare_gate1.json).
- V02 stick creep (v02_stick_creep.py): GPU and FEBio both creep under constant sub-limit tangential load, linear in the
  increment count, ~1/E. Root cause both codes: stick anchor re-projected at every increment start. Critical for slip-out.
  Results: v02_results_E10.json, v02_stick_creep_newton.json (E 400).
- Newton line-search rigid-state bug (newton.py:202-208), unconverged increments accepted, untracked code, ignored laugon.
- Running scripts: `python -I` drops the user site and env-based library lookup; v02 header shows the workaround
  (user site first, CUDA_PATH, preload libnvrtc + libcudss, site.ENABLE_USER_SITE).

## r0002 (2026-10-27) -> HOLD (board/r0002/verifier.json)
- Gate 1 re-run at 77b7596: pass; inputs + FEBio outputs byte-identical; report differs ~1e-16 (atomics) -> use 1e-9 tolerance.
- KEY: FEBio does NOT keep stick points across increments (Update: ProjectSurface :680 before InitSlidingSurface :687);
  GPU new rule is better than FEBio; gate 4 must not use FEBio for holds / cycles (v05_febio_stick_order.md).
- Still open: line-search state bug (newton.py:223-233), 1b/1c not via Newton, tie_disc force 0 in gate 2 (driver uses run now),
  laugon ignored, Gent clamp mech.py:157 at ~99 % Jm for 40 % compression, provenance + patched FEBio, e02 batch broken.
- Permission: only `python gpufe/gate*.py` runs; my own scripts and multi-command shells are refused -> use md5sum/jq/Grep.
- No CR-*.json filed by the integrator for r0001.

## Next round to-do (r0003)
- Re-run V02 (force hold) on the new rule if permitted; expect creep ~0.
- Check CR-v8..v12 + repeats; gate 2 all 6 directions with tie / facet forces.

## Older to-do (r0001)
- Re-run V02 after CR-v1; must give creep < 1e-4 mm for n = 10 and 80.
- Write gate 1d (rotation 45 deg, nu 0.49, follower pressure, rigid force/moment, tied, two-pass) through NewtonSolver.
- Check gate 2 driver once committed (tie force 0 in flex_pos_y_gpu.json).

## r0003 (2026-10-28) -> HOLD (board/r0003/verifier.json, written by v10_write_verdict.py)
- Gate 1 re-run at 1f09ae2 (dirty gpufe/contact.py, newton.py; not used by gate 1): pass, files identical, max diff 1.5e-16.
- Permissions now open: own scripts run with plain `python` (no -I workaround needed).
- V07 (= V02 on new paths, v07_stick_creep.py, ratio via V07_RATIO): (a) hold crash: increment starting in equilibrium
  fails line search -> RuntimeError (newton.py:246/270); V07_PATCH=1 = verifier workaround. (b) creep under constant load at
  0.9 mu (E 10): 0.119 mm (n 10/20), 0.046 mm (n 40); FEBio 0.151/0.301/0.603 (linear in n). Cause: slipped nodes re-anchored
  (contact.py:114-117) = F-0015. Summary v07_summary.md.
- e02: LP exact (v08); reference-config normals with Cauchy stress -> spurious mu = tan(theta); curved faces (F-0011); no gate.
- FEBio reference = 4.13 + 9 patched files, 7 lib variants (v09_febio_build_state.txt).
- F-0013 fixed at HEAD; F-0014, F-0015 confirmed; F-0011 confirmed by code.

## Next round to-do (r0004)
- Re-run V07 without patch after CR-v13/v14; gate 1e criteria. Check gap consistency newton.py:109 vs contact.py:171.
- Gate M3 for e02: build the curved-face and 5-deg rotation benchmarks myself if engine does not.
- Gate 2 remaining 5 directions; tie-force report.
