# Safety guard r0003 - working notes (2026-10-28)

Python runs for this role now (PI 2026-10-27 (6)). All scripts run from the repo root, read-only on the model.

## N1 Geometry re-run (s03_geometry.py = r0001 s01 with post-split paths -> s03_geometry.json)
Footprint (1 mm inset) AP 9.55 x LR 11.45 mm, 92.83 mm2; gap in footprint min 2.95 / median 4.06 / max 5.30 mm;
disc-space volume 380.3 mm3 (S4 50 % floor = 190 mm3 void); anterior 120 deg chord 11.83 mm vs max footprint Y width 11.45 mm
(-> S2 'Y width <= opening' is met by any footprint-filling part, margin 0.38 mm);
posterior footprint edge to outline 1.00 mm; uncinate bone points start at |Y| 6.24 mm vs footprint half-width 5.73 mm (0.51 mm gap).

## N2 Midline gap profile (s04_midline_profile.py -> .json). Frame +X = anterior (frame_c3c4.json X_anterior).
Y=0: anterior outline 3.51, minimum 2.96 at X +3.8 (anterior lip), then rising monotonically to 5.30 at the posterior
footprint edge and 5.48 at the posterior outline edge. Y=+/-3: 3.32 -> 4.81 (footprint), 5.02 (outline).
=> Inside the modelled disc space there is NO posterior closure (posterior_closure_in_footprint = 0.0 on all three lines).
The anterior lip (2.96 vs 3.45 at the anterior edge) blocks ANTERIOR expulsion only.
CORRECTION of my r0002 note N4: '~0.35 mm midline overlap with the posterior lip' used the baseline STL value
'posterior 4.1 mm' (DECISIONS_baseline_human_c34.md:15), which is not the gap inside the FE disc mesh. In the FE model
posterior migration meets no geometric stop at all; it moves into a taller gap (clamp is lost as the cage moves back).
Open: why the STL measure (posterior 4.1) differs from the FE disc mesh (5.48 at the posterior outline). Integrator to check.

## N3 Wedge squeeze ('watermelon seed') of a contour-matched cage (s05_wedge_squeeze.py -> .json)
Uniform clamp pressure on both faces, net in-plane force / normal force:
full footprint Fx/N = -0.165 (posterior), mu needed for clamp alone = 0.083; anterior half 0.105; posterior half 0.060;
region taller than 4.95 mm 0.044. Lateral (Fy) ~0 (symmetric).
=> The clamp ALONE pushes a contour-matched cage toward the cord and uses ~0.08-0.10 of the friction budget before any
neck motion (41-52 % of mu 0.2). Independent support: F-0011 measured, follower load only (t 3.5, p062 corrected rerun),
bottom face full tangential / normal = 11.02 / 105.15 = 0.105 (direction not stated there).
Assumption: uniform pressure; real pressure follows stiffness -> number to be replaced by e02 (curved faces) on FE runs.

## N4 Measurement artefact of 'translation relative to C3' (s06_frame_artifact.py -> .json)
Cage centroid at (-1.02, 0, 6.07) mm from the ICR (frame origin), r = 6.15 mm. A cage that does not move at all on C4
appears to move relative to C3 by 2 r sin(theta/2): 0.32 / 0.62 / 0.86 mm at 3 / 5.78 / 8 deg (AP component almost all of it).
5.78 deg = gate-2 intact flexion (VERIFICATION / pi_updates). -> exceeds the 0.5 mm posterior limit with zero slip.
Fix: judge net dislocation at the zero-load points between cycles; in-cycle peaks in the mid-frame (mean of C3 and C4 motion,
halves the artefact) or as interface slip.

## N5 Best-fit rigid motion loophole (s07_bestfit_loophole.py -> .json)
Toy node cloud in the footprint box; posterior hard slab (fraction f of nodes) moved -u in X, soft rest still.
Best fit of ALL nodes = f x u: f 0.2, u 1.5 mm -> reads 0.30 mm (passes 0.5 mm); f 0.35, u 1.0 -> 0.35 mm; f 0.5, u 1.0 -> 0.50 mm.
=> A stiff part can move >1 mm toward the cord while the PI's whole-cage measure reads <0.5 mm. Also node-count weighting
depends on mesh density. Fix: report max(best fit all nodes [volume-weighted], best fit hard voxels E > 20 MPa) and the
canal-clearance check on every node.

## N6 Literature this round
- Damm NB, Morlock MM, Bishop NE 2015 J Biomech 48:3517-3521, doi:10.1016/j.jbiomech.2015.07.012 (abstract read via
  Europe PMC 2026-10-28): polished surface on trabecular bone: mu independent of contact stress, 'much lower' than porous; no number in abstract.
- Zhang X, Ma X, Lin Q, ... Song 2023 Macromol Biosci 23(5), doi:10.1002/mabi.202200548 (Crossref abstract 2026-10-28):
  PEEK against CORTICAL bone, reciprocating tribology in SBF / calf serum / hyaluronic acid / mucin; abstract has no mu
  value; full text not read -> numbers unverified. Only direct polymer-on-bone friction paper found.
- FE cage studies assume mu 0.2-0.4 (web search 2026-10-28, e.g. BMC Musculoskelet Disord 2020 autologous bone-cage FE
  doi:10.1186/s12891-020-03411-1 uses 0.2) - assumptions, not measurements.
- Europe PMC was unavailable (HTTP 503) for part of the session; searches incomplete.
