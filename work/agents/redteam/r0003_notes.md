# Red team r0003 - notes (third-party checkable)

Scripts (all in this folder):
- r0002_i001.py rerun (16 s) -> identical r0002_i001_result.json (git: unmodified) -> F-0027.
- r0003_tension.py -> r0003_tension_result.json (+ printed table) -> F-0021. Needs the old repo's physio_fix xplt files.
  Ran once in background (nohup) and produced nothing (process gone, empty .out, cause not investigated); ran fine in the
  foreground (about 1 min).
- r0003_dislocation.py -> r0003_dislocation_result.json -> F-0022 (synthetic block, imposed motions, numpy only).
- r0003_snap/: uncommitted gpufe diff + sha256 at the time of reading (F-0025, F-0028).

## F-0021 arithmetic (p062_gpu2 extension, bottom face, t 5.00)
N_net 88.9 N, N+ 246.2 N, T 157.3 N (check: 246.2 - 157.3 = 88.9). |F_xy| = M2_e02 * N+ = 0.119 * 246.2 = 29.3 N
-> M2_net = 29.3 / 88.9 = 0.33 (script 0.328). 3-D: 0.468 * 88.9 = 41.6 N tangential (r0002 shear_3d_bot 41.57 N, same).
Caveat: M3_net scales the tied pressure pattern; only M2_net is exact for the given shear force.
Not checked: how much of the tension exists before the moment windows (insertion / 'expand' prestress); it does not
change the conclusion because e02 uses whatever tension is present.

## Observation on code under change
First `git diff gpufe/` (around 01:08-01:10) showed gap_normal with sign-only g = +-|q - ps|; the next read (after the
01:12:06 mtime of contact.py) showed the c0 / c1 smooth-fade version. Snapshot taken after the second read.

## Not done
- No canaries planted this round.
- F-0024 walking test specified, not run (no gated frictional path).
- p014 failure cause not investigated (old repo log only).
