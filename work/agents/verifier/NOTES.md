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
