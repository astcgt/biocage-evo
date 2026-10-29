# e04 dislocation screen, physio_rot (rotation control, non-symmetric stiffness), 2026-10-30

Source: old repo human_study/al_v2/physio_rot (pass 1, 139 designs), physio_rot_r2 (pass 2: windows below 1.5 N m re-run
with tangent-extrapolated amplitude), physio_rot_facet0 / facet3 (p062, p002). Per design the best window result over both
passes: best_by_design.json.

- 62 designs completed all 6 windows; 28 reached 1.5 N m in all 6 (flexion 62, extension 39, LB 45 / 49, AR 42 / 43).
- mu_squeeze (least friction for no rigid slip against both endplates), max over the reached windows: median 0.112,
  max 0.149 (p147). One-face slip bound: median 0.27 mm, max 0.48 mm (limit 1 mm). No dislocation mode found.
- Facet sensitivity (p062, p002): no facet contact changes mu_squeeze by <= +10 % (axial rotation 0.075 -> 0.082),
  facet cartilage E x3 by <= -5 %; slip bound <= 0.03 mm. The facets can be isolated for the slip-out question.
- 77 runs failed (failed_runs_lastJ.json: time, min J, max z-compression %, E_soft, design type, run of the cage at the
  last converged state). 48 already had > 30 % local soft compression (E_soft median 2.8 MPa; 22 of the 23 B failures;
  follower step or flexion): real large deformation, outside the 30 % soft-compression rule. 29 had <= 30 % (E_soft
  median 7 MPa, almost all A; later windows too): numerical failures, the design itself is not disqualified.
  Completed designs (sample of 12): max compression 2-21 %.
