PI decisions 2026-10-27 after round 2 (full text: docs/DECISIONS.md, the two 2026-10-27 entries):
- Slip-out = dislocation: the rigid-body part of the whole cage motion, radially outward from the disc space (1 mm any
  direction, 0.5 mm posterior). Squash, local deformation and local micro-slip are acceptable. A posterior bulge is a
  separate nerve check (canal clearance).
- Slip judged by calculation first (mu_req from the tied cage, whole-face limit; e02 must handle curved faces);
  the frictional simulation only checks the shortcut; the law (no slip below the limit) is the reference, not FEBio.
- 135 N kept (Moroney 1988); expand-after-insertion / latch designs allowed, to be verified carefully by the safety guard.
- Safety guard insertion rules accepted (hard core no compression, soft <= 30 %, posterior mu 0.2, distraction 2 mm).
- All roles now have full tool permissions (you may run any code in your own folder; write only in your own folder,
  your verdict file, and work/findings for the red team).
- Focus: short-term safe no-dislocation. Fatigue, depth stop, debris, 16-week degradation deferred until a prototype exists.
GPU solver since round 2 (gpufe/, results/gpufe_verify/): diagonal regularisation was too large (1e-10 x max diag swamped
soft tissue) -> now 1e-16, Newton quadratic (3 iterations); follower-pressure load stiffness added; full Newton with
contact, strict line search (no descent with a fresh tangent = increment fails), automatic increment halving; FEBio claim
about stick points corrected (contact.py, gate1d). Gate 2 flexion: 5.781396 vs FEBio 5.781395 deg. Other 5 directions
still fail at facet contact onset (contact tangent has only k n n^T; being completed).
