# Risk analysis (2026-10-31)

L / M / H = likelihood and impact. Owner = who watches it (integrator = main Claude session; roles as in GOVERNANCE.md).

## A. Scientific validity of the main claim

| # | Risk | L | I | Early-warning signal | Mitigation | Owner |
|---|---|---|---|---|---|---|
| A1 | Tied interface + limit-surface mu_req misranks designs vs real friction (the deciding number is a surrogate) | M | H | friction pilots disagree with tied ranking; p062 friction run completed, no comparison yet | 7-design real-friction batch queued (physrotFr_); gate 4 comparison before any ranking is published | verifier |
| A2 | The compliant-phase compression rule (15 % / 25 %) is interim and unsupported by PLCL data; 62 "fail" verdicts rest on it | H | H | bench data moves the limits | compression-set / creep bench tests; report verdict sensitivity to the limits (10/20 %, 20/30 %) | PI + safety |
| A3 | Soft PLCL degrades within weeks (CL-rich half-life 18-32 d): fixation computed with fresh moduli is optimistic | H | H | none in the model today | degradation sweep (E_soft x 0.1-0.5) on passing designs; hydrolysis bench test | integrator |
| A4 | Hard PLCL creep rupture under sustained stress (lactide cages failed at 3 months at 25 % of short-term strength) is not checked | H | H | peak hard-phase stress not reported | add an Eyring / Smit-type sustained-stress criterion to e05 or a new e06; bench creep rupture | integrator |
| A5 | The "expand" insertion (shrink 0.8 prestrain) is a numerical convenience; real insertion may plastically deform the hard core or need 2-3 mm transient distraction | M | M | surgeon disagrees with the 2 mm transient limit | model a realistic insertion path for the finalists; surgeon confirmation | PI |
| A6 | Single idealised symmetric 26-year-old subject | H | M | - | 59/64-year-old models; endplate-geometry sweep | integrator |
| A7 | Quasi-static slow-dynamic protocol (density x1000, rho_inf 0) alters contact onset or hides stick-slip | L | M | static vs dynamic differ (validated within 0.002 on p062/p002) | keep the static check on a sample each batch | verifier |
| A8 | 12 designs (low E_soft) cannot be computed: result depends on how they are classified | M | M | - | PI decision (compression failure vs non-computable); report both counts | PI |
| A9 | Posterior push-out below the 135 N guard (93 N on p062) means the device class may not meet its own safety rule | M | H | more designs below 135 N | re-derive the 135 N requirement (Moroney full text); design features that raise posterior resistance (concavity interlock) | safety |

## B. Numerical and method risks

| # | Risk | L | I | Signal | Mitigation | Owner |
|---|---|---|---|---|---|---|
| B1 | Target-crossing sampling overshoot (4-13 % in M) biases slip bounds and mu_req | H | L | ratio of M_at_target to 1500 | interpolate to 1.5 N m between bracketing states in e04 (planned) | integrator |
| B2 | Element inversion in 0.2 mm soft layers stops runs (16 % of split2 designs) | H | M | negative-Jacobian lines | contact-skin equivalent law (h32 prototype), finer time steps, hourglass control; report as a limitation | integrator |
| B3 | Static retry for first-step failures changes the physics for those windows (6 of 7 succeeded) | L | L | mixed static/dynamic sources per design | flag in provenance (restart_static.feb present); compare on one design | verifier |
| B4 | Mesh convergence not repeated for the split2 protocol | M | M | - | one design at 0.1 mm layers | integrator |
| B5 | gpufe gate 2 fails in 5/6 directions; any L1b number is unverified | H | H (for evo) | gate2 logs | do not use gpufe for ranking until gates 2-4 pass; FEBio L2 for round 1 | verifier |

## C. Data and provenance

| # | Risk | L | I | Signal | Mitigation | Owner |
|---|---|---|---|---|---|---|
| C1 | Invalid runs leak into verdicts (two bugs already: combined loading 10-26; restart load curves 10-31) | M | H | a window with constant moment; results from dirs listed in INVALID.md | aggregator now rebuilds from per-run files with an explicit invalid list; add a "rotation applied" check per window; validate every protocol change on all six directions, not one | integrator |
| C2 | Post-processing skipped CPU-run cases (18 found 10-31) or other glob gaps | M | M | designs with runs but no results | aggregator enumerates all case dirs; a completeness report per batch | integrator |
| C3 | Results not versioned (merged JSON, gate reports, board files uncommitted) | H | M | git status | commit results with the OLD-repo hash after each batch | integrator |
| C4 | Duplicate design points (150 -> 133 unique) inflate counts | H | L | - | report unique designs; fix the GP acquisition clamping | integrator |
| C5 | FEBio build (4.13 + 9 patches) not reproducible bit-for-bit | M | M | - | commit the patch files and a build script | integrator |

## D. Operations

| # | Risk | L | I | Signal | Mitigation | Owner |
|---|---|---|---|---|---|---|
| D1 | Shared disk fills (0 MB on 10-31: 4 runs lost, watchdog state truncated) | H | H | /raid free < 50 GB | disk guard in the scheduler (pause launches < 30 GB; alert), nightly deletion of .dmp of finished runs, atomic writes of state files | foreman |
| D2 | Other users' GPU jobs (0, 5, 6) and the 32-core cgroup quota limit throughput | H | M | throttling counters | GPU whitelist 1-4; 2-core GPU runs to be benchmarked | foreman |
| D3 | Server restart loses in-flight runs and daemons | M | M | tmux sessions missing | resume_all.sh covers daemons; checkpoints every 5 steps; keepalive | foreman |
| D4 | Autonomous agents edit production code (foreman truncated h19 on a full disk) | M | H | diff of scripts outside commits | foreman writes config only; code edits by the integrator with commits | PI |
| D5 | Usage limits interrupt agent work (25 of 29 agents failed on 10-31) | H | M | API limit errors | inline work by the main session; smaller agent fan-out; schedule agent rounds off-peak | integrator |

## E. Governance and AI

| # | Risk | L | I | Signal | Mitigation | Owner |
|---|---|---|---|---|---|---|
| E1 | Roles are not isolated (same Unix user, full tools); verdicts could be influenced | M | M | sha256 drift of code during rounds | red-team snapshot per round; frozen.json; later per-role users | red team |
| E2 | Designer games the evaluator (preload gaming, d gene, sponge voids) | H | M | archive cells filled by degenerate designs | fixed d set, score after follower load, S3-S5 L0 checks, canaries | safety + red team |
| E3 | Fabricated or unverified references enter the paper | M | H | "UNVERIFIED" flags in LITERATURE.md | cite only verified entries; check DOIs at submission | integrator |
| E4 | 29 red-team findings unanswered; rounds stopped since 10-28 | H | M | findings without status | answer each finding; round 4 digest with the new items | integrator |

## F. Publication and timeline

| # | Risk | L | I | Signal | Mitigation | Owner |
|---|---|---|---|---|---|---|
| F1 | Novelty challenged (Smit 2024 TO cages; Mojica-Santiago plate fixation) | M | M | - | position as the first fixation-free resorbable support judged on dislocation; cite both | integrator |
| F2 | Reviewers reject an in-silico-only device claim | H | H | - | bench friction / compression tests and a cadaver push-out before submission to a top venue; otherwise target JOR Spine / J Biomech first | PI |
| F3 | Single developer, PI bandwidth, surgeon input pending | H | M | open PI questions in DECISIONS.md | weekly decision digest; this progress report | PI |

## Top five, in words
1. The compression rule and the fresh-material assumption (A2-A4): the central result ("compression, not slip, discriminates") rests on an interim rule and on moduli that degrade within weeks; bench data and a degradation sweep are the first things to buy.
2. The tied-interface surrogate (A1): until the real-friction batch agrees, mu_req is a hypothesis.
3. Evaluator bugs (C1): two silent bugs in a week; every protocol change must be validated on all six directions, and the aggregator must stay source-complete.
4. Posterior safety (A9): the one measured push-out is below the project's own guard.
5. Operations (D1, D4, D5): disk, autonomous code edits and usage limits have each cost runs or hours this week.
