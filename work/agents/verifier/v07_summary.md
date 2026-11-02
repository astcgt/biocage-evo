# V07 force-hold creep (verifier r0003)

Script: v07_stick_creep.py; summary: v07_summarise.py. Coulomb answer: hold creep 0, independent of n.

| Ft/(mu Fn) | E MPa | n | GPU x(0.5) mm | GPU hold creep mm | hold incr | min stick | GPU last dx mm | FEBio x(0.5) mm | FEBio hold creep mm |
|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 10 | 10 | 0.05607 | 0.004166 | 5 | 0.875 | -7.958e-07 | 0.065 | 0.07547 |
| 0.5 | 10 | 40 | 0.05672 | 0.003198 | 20 | 0.875 | 0 | 0.08722 | 0.3018 |
| 0.9 | 10 | 10 | 0.1109 | 0.1187 | 20 | 0.5 | 0.005647 | 0.1193 | 0.1509 |
| 0.9 | 10 | 20 | 0.1109 | 0.1187 | 20 | 0.5 | 0.005647 | 0.1344 | 0.3014 |
| 0.9 | 10 | 40 | 0.1161 | 0.04604 | 25 | 0.5 | 0 | 0.162 | 0.6029 |

 | ratio 0.9 E 400 n 10 (patched): RuntimeError at t 0.6876 in the hold, max_newton 60 x 7 tries, residual 1.55e-7 N (4e-8 of Fn): probably stick / slip switching between iterations (not isolated), the displacement norm never meets dtol 1e-6 (v07_r0.9_patched.log); E 400 n 20 / 40 therefore not run. Unpatched runs: RuntimeError in the hold once all nodes stick (residual ~6e-13 N; v07_r0.5.log, v07_r0.9.log).
