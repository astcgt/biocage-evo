# mu_req (methods/e03_mu_req.py) on the complete tied physio runs, 2026-10-28

Inputs: the old study's tied physio runs (corrected load curves) that reached all 6 windows: physio_v3 (12 of 148 designs;
135 stalled, mostly in extension t 4.5-5.5, watchdog kill after 45 min without progress) and physio_fix p062 / p063
(same designs, identical results). e03 analytic self-test PASS (flat shear 0 %, disc twist 0.8 %, 15 deg incline 0 %).
Per window: the worst face (top / bottom) over the window's states. mu_drop = tension dropped (e02 rule, optimistic);
mu_scaled = compressive forces scaled to the real net normal force (F-0021 option 2).

| window | mu_drop | mu_scaled |
|---|---|---|
| flexion | 0.12-0.22 | 0.19-0.25 |
| extension | 0.07-0.09 | 0.08-0.14 |
| lateral bending (L = R) | 0.49-0.55 | 0.74-0.80 |
| axial rotation (L = R) | 1.88-2.32 | 2.19-2.78 |

Governing direction: axial rotation in all 14 runs (mu_scaled 2.2-2.8, 7-9x the 0.3 assumption). Max tension / net
compression on a glued face: 1.69-1.77 (the tied solution leans heavily on adhesion; F-0021 confirmed).
Reading: with the tied (glued) model the cage face would have to transmit the twist that the glue lets it carry; a real
cage would start to spin first and the annulus / facets would take more of the torque. A local spin is not dislocation
(PI 2026-10-27), so the tied mu_req is a pessimistic screen for axial rotation and lateral bending; whether the cage then
migrates outward needs a frictional (non-adhesive) run.
Per-case files: _pXXX*.json (states, provenance: git hash, script / case / xplt sha256).
