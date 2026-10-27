# Red team r0002 - hand calculations and notes (third-party checkable)

## Session note
Early in the session I ran `cd <FEBio src> && grep`, which moved the session's working directory to the FEBio tree.
After that, the role's relative permission patterns (Write(work/agents/redteam/**), Bash(python -I work/agents/redteam/*))
no longer matched, and writes / python were refused until I cd'd back. No file outside work/agents/redteam and
work/findings was written. (Observation for F-0017: the permissions are relative-path patterns.)

## F-0011 (e02 drops out-of-plane tangential traction)
Source: work/agents/redteam/r0001_i001_p062_physio.json, state t = 3.5 (follower only; moments 0 in both curve versions).
- bottom shearF = (-1.466, -0.017, 10.922) N -> |xy| = 1.466; |3-D| = sqrt(1.466^2 + 0.017^2 + 10.922^2) = sqrt(2.149 + 0.0003 + 119.29) = 11.02 N
- top shearF = (5.189, 0.053, -5.519) N -> |xy| = 5.19; |3-D| = sqrt(26.93 + 0.003 + 30.46) = 7.575 N
- N bottom 105.151, top 104.582 -> M2 xy 0.0139 / 0.0496; M2 3-D 0.1048 / 0.0724; ratio bottom 7.5x
- cross-check: physio_fix/p062_gpu2/summary.json t 3.5: bot_shear_N 11.0197, top_shear_N 7.5753 (h15, independent code)
Window maxima from r0002_i001.py (r0002_i001_result.json): see F-0011 / F-0012.

## F-0015 (slip -> stick anchor reset; penalty depends on the cage material)
Rule (gpufe/contact.py:106-114 and FEBio FESlidingElasticInterface.cpp:136, :871-905 with laugon 0 -> Lt = 0):
a node that slipped in increment n is re-anchored at its current projection; in increment n+1 its stick trial
traction starts from 0 and must be rebuilt by a further relative displacement |t_t| / eps <= mu p / eps.
Auto penalty eps = penalty * E * A / V (contact.py:4, solver.py:89-110); voxel facet: A / V = 1 / h, h = 0.2 mm.
p062 case.json: penalty 10, E_hard 649.53 MPa, E_soft 8.194 MPa.
- eps_hard = 10 * 649.53 / 0.2 = 32,477 N/mm^3; eps_soft = 10 * 8.194 / 0.2 = 409.7 N/mm^3; ratio 79.3
- pressure: 105 N / footprint 92.83 mm^2 = 1.13 MPa; on the cage ring only (92.83 - 55.39 = 37.44 mm^2): 2.80 MPa
- per-increment loss delta = mu p / eps (mu 0.3):
  hard: 0.3 * 2.80 / 32477 = 2.6e-5 mm; soft: 0.3 * 2.80 / 409.7 = 2.05e-3 mm (1.13 MPa: 8.3e-4 mm)
- increments: 6 directions x 3 cycles x 2 half-windows x 20 increments = 720; if half are preceded by a slip: 360
- upper-bound order of magnitude: soft 360 * 2.05e-3 = 0.74 mm (0.30 mm at 1.13 MPa); hard 360 * 2.6e-5 = 0.009 mm
These are bounds for nodes that slip; whether the cage centre follows depends on how much of the face slips
(tied h15 runs show slip_area_frac 0.25-0.8 at mu 0.35, physio_fix/p062_gpu2/summary.json). NOT simulated: estimate only.

## F-0016 (S9 measured at the cage centre only)
Footprint 92.83 mm^2 (p062). Rough half-diagonal of an ~11 x 8.5 mm footprint = 0.5 * sqrt(11^2 + 8.5^2) = 6.95 mm.
Rotation about Z by theta moves a corner by r * theta: 5 deg = 0.0873 rad -> 0.61 mm; 4.1 deg -> 0.5 mm.
Tilt about Y by 2 deg with half-height 2.3 mm (mean height 4.605 mm): posterior edge moves 2.3 * 0.0349 = 0.08 mm (small).
