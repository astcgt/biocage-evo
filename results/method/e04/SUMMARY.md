# Dislocation screen (methods/e04_dislocation.py), 14 complete tied physio runs, 2026-10-28

Dislocation needs the cage to slide against BOTH endplates in the same sense (squeeze-out). mu_squeeze = least friction
coefficient at which the friction of both faces together (tied pressures scaled to the net normal force) carries the net
horizontal push and twist that the surrounding tissue puts on the cage. One-face slip bound = horizontal relative motion of
C3 vs C4 over the cage footprint (the most one face can slip while the cage moves with the other vertebra; reversible).

| window | max mu_squeeze (14 runs) | max one-face slip bound |
|---|---|---|
| flexion | 0.032 | 0.51 mm |
| extension | 0.016 | 0.75 mm |
| lateral bending | 0.139 | 0.43 mm |
| axial rotation | 0.082 | 0.42 mm |

All below mu 0.3 (main) and 0.2 (posterior check): the screen finds no squeeze-out (dislocation) mode in any direction for
any of the 14 designs, although whole-face mu_req (e03) exceeds 0.3 in lateral bending and axial rotation: those loads make
one face slip (the cage moves with one vertebra), not the cage leave the disc space.
Caveats: (1) pressures from the tied solution, scaled (F-0021 option 2); (2) the net push includes the stress-sampling
imbalance of F-0010 (~2 N; conservative); (3) one-face slip over 3 cycles may ratchet if the left / right or loading /
unloading paths are asymmetric: not assessed here; (4) only the 14 designs that completed (one AL family); (5) to be
checked on a few designs with frictional (non-adhesive) rotation-controlled runs.
