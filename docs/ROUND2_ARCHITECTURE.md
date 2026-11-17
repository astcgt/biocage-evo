# Round-2 evolution architecture: surrogate-guided active learning + naive/mentor ideation + principle extraction

PI 2026-11-18: 「下一輪方案：其他甲乙丙都不錯，深入構造細節」. This document is the construction detail of the three approved parts
(A surrogate + active learning, B naive / mentor ideation, C principle extraction) on top of the existing platform
(old repo: h14 build -> h24 preflight -> FEBio GPU runs -> e03 / e04 / e07 read-outs; evo repo: fric_compare -> e07_batch ->
collect_split -> mu_req_field -> capability labels -> h37 QA). Nothing here replaces a FEBio verdict: surrogates and LLM
agents only decide WHAT to simulate next. Plain-language summary for the PI: human_study/PI_REPORT_2026-11-18_direction.md (old repo).

## 0. Data we already have (the training set)
| source | rows | inputs | outputs |
|---|---|---|---|
| results/method/mu_req_field.csv | 149 tied-screening designs | hp_E_hard, hp_E_soft, hp_d (distraction), hp_theta, family (axial / radial interleave, posterior patterns), class | mu_req_max, governing window, tied class (compression-peak / -sustained / radial-mix ...), computable |
| results/method/fric/verdicts.json | 73 designs with frictional windows | same genes + insertion process (production / G) | posterior translation at the evaluation point (flexion, extension), verdict pass / grey / open, numerical_flags |
| results/method/fric/e07_verdicts.json | 72 designs | same | shear_req_p99_MPa, shear_req_max_MPa (PI 2026-11-18), 3 MPa check |
| human_study/al_v2/*/pNNN/cage_elems.npz | every built design | voxel / element material map | geometric descriptors (computed, see C) |

Gaps: only 4 continuous genes + a family label; the free-form encodings of docs/PLAN.md (CPPN, design programs, voxel edits)
have not been run through h14 yet (to verify: whether h12 / h14 accept an arbitrary in-plane material map - PLAN says the
encodings produce one voxel field; the build path for it is the first engineering item of part B).

## A. Surrogate model + active learning (the "quick estimator")
**A1 Features.** x = [E_hard, E_soft, d, theta, one-hot family] + geometric descriptors computed from cage_elems.npz by code
(soft fraction, posterior soft thickness, hard-rim continuity, contact area on each endplate, void fraction, posterior lip
height). Descriptor code: ops/descriptors.py (new; pure numpy; also used by C).
**A2 Targets (one model per target, shared inputs).**
- y1 posterior translation at the evaluation point, flexion and extension (regression; the quantity the 0.45 / 0.55 limits act on)
- y2 mu_req_max (regression; tied screening shortcut, cheap label available for all 149)
- y3 shear_req_p99_MPa (regression; PI 2026-11-18 required strength)
- y4 computability (classifier: not-computable-both-laws / unstable-window vs computed) - the platform [數值] risk
- y5 tied class = compression-peak / -sustained (classifier) - the cheap gate most designs fail
**A3 Model.** Gaussian process with an ARD Matern-5/2 kernel per target (scikit-learn GaussianProcessRegressor / Classifier; 73-149
points fit in seconds on CPU), targets log-transformed where positive (mu_req, shear). Alternative if GP calibration is poor:
small ensemble of gradient-boosted trees for the mean + GP for the uncertainty. Fitting script ops/surrogate_fit.py -> results/surrogate/model_<date>.pkl + results/surrogate/loo_<date>.json.
**A4 Validation before use (gate).** Leave-one-out on the 73: report R² and the 90 % interval coverage per target; the surrogate
may steer proposals only if posterior-translation LOO coverage is 0.8-0.95 and R² >= 0.5; otherwise it is used for
exploration only (pure uncertainty sampling). Recorded in DECISIONS and as a new h37 check R21 (every verdict row cites a FEBio case
dir; surrogate numbers never enter verdicts.json / labels).
**A5 Acquisition (batch of 20-30 per round).** Score = P(pass all gates) x U(biodisc void fraction, mu_req margin) + beta x
predictive std, with P(pass) = P(y1 < 0.45 both windows) x P(y3 <= threshold or flag) x P(y5 = pass) x P(y4 computable);
batch chosen greedily with local penalisation (kriging believer) so the 20 proposals spread out; 20 % of each batch reserved
for pure exploration (max std) and 2 replicate decks per round (R20 noise monitor). Candidate pool = 5 000 random genes in the
allowed ranges + part-B proposals + part-C-suggested directions. Script ops/propose_round.py -> work/board/rNNNN/proposals.json.
**A6 Loop.** propose -> designer role writes pNNN_params.json -> h14 build + h24 preflight (old repo) -> tied screening
(cheap) -> frictional windows under the production configuration (physio_fric5r route E; stick memory; fallback laws as
today) only for designs with P(pass) > 0.3 after the tied result -> read-outs -> fric_compare chain -> labels -> QA -> refit.
One round = ~2 days wall-clock on 3 GPUs (20 designs x 1-3 GPU-h; insertion 16-60 min, windows 7-50 min).
**A7 Cost.** Setup 1-2 days (descriptors, fit, LOO, R21). Per round: 20-60 GPU-h, ~1 h CPU, tokens only for the designer role.
**A8 What can go wrong.** 4 genes + descriptors may not explain the 0.01-mm-level posterior read-out (then A steers only the
cheap gates y2 / y5 and computability, still useful); descriptor leakage (descriptors computed from the built mesh are
available before simulation, so no leakage); replicate noise 0.012 mm sets the floor of y1 accuracy.

## B. Naive / mentor ideation (new shapes, not only new numbers)
Source: D'Ambrosio, Albalak, Lehman, Stanley 2026, arXiv 2611.11725 (naive model kept ignorant of the topic produces seed
ideas; a mentor model turns them into concrete proposals; novelty and usefulness both rose). Related: EvoSci (ACL 2026)
mentor agent; LLM self-judged novelty is unreliable (arXiv 2606.12071; AI2 novelty bench) -> our judge is the simulation.
**B1 Naive proposer.** A small model (Haiku-class) or the same model with a context stripped of PLAN / DECISIONS / results;
it gets only: the physical task in lay terms (a resorbable spacer that must not slide out of the C3-C4 disc space under bending,
must leave >= 50 % void for the living disc, printable in two PLCL stiffnesses in 0.2 mm layers, inserted from the front),
the constraint list S1-S10 as plain rules, and NO list of what we tried. Output: 10 seed ideas per round as text + a rough
layout sketch (ASCII grid or short pseudo-program). Prompt file roles/prompts/naive_proposer.md.
**B2 Mentor.** The strongest available model with full context (PLAN, principles from C, archive of tried designs): for each
seed - feasibility against S1-S10, distance to the archive (MAP-Elites descriptors of PLAN: void fraction, soft fraction,
posterior lip ...), then rewrite into a design program (PLAN encoding 2: short Python producing the voxel / material map) or,
where the parametric families suffice, a params JSON. Keeps <= 5 per round, writes work/board/rNNNN/ideation.json with the
seed text, the mentor's reasoning, the predicted weak point and the first cheap test. Prompt roles/prompts/mentor.md.
**B3 Judge.** Not an LLM: the h14 build must succeed, the safety role checks S1-S10, then the simulation verdicts decide;
novelty is scored by archive distance only.
**B4 Engineering prerequisite.** A build path from an arbitrary material map to h12 / h14 (to verify first; if missing: 2-3 days
to add a 'voxel_map' family that h14 reads from an .npz and h37 R7 recognises as a production option).
**B5 Cost.** Tokens: ~50-100 k per round (naive + mentor), i.e. a few USD; simulations only for the <= 5 accepted ideas (5-15 GPU-h).
**B6 Risk.** Most seeds unbuildable (expected; the mentor filters); the mentor may regress to known families (mitigation:
archive-distance floor for at least 2 of the 5); a new family means new numerical behaviour (soft-face inversions) - keep
the not-computable class and route-E fallback machinery as is.

## C. Principle extraction (what the 73 + 149 results already say)
Source: Abstraction Agent (arXiv 2609.04303: LLM proposes features, code scores them, correlation-based selection, clustering);
KeplerAgent (arXiv 2602.12259) for physics-guided form discovery.
**C1 Feature proposal.** The LLM proposes 20-40 candidate geometric / material features in words; each is implemented as a
numpy function over cage_elems.npz (ops/descriptors.py, shared with A). No feature value is ever estimated by the LLM.
**C2 Scoring.** Spearman correlation and partial dependence of each feature with y1 (posterior translation), y2 (mu_req), y3
(shear_req), class membership (radial-mix-excluded, compression-peak, not-computable); features with |rho| > 0.3 and
stable under bootstrap kept; redundant ones merged by clustering.
**C3 Rules.** Each kept feature becomes a plain-language rule with effect size, confidence and counter-examples, e.g.
「後方軟質層每加厚 0.2 mm，後伸後方位移約增加 x mm（n = 45，反例 p0xx）」; written to docs/DESIGN_PRINCIPLES.md (Traditional Chinese +
English) and fed to the mentor prompt (B2) and the designer role.
**C4 Cost.** 1 day; CPU only; ~200 k tokens one-off; refresh after every round (automatic table, manual prose check).
**C5 Risk.** 73 points support only coarse rules; correlation is not causation (rules are hypotheses for the active learner to test:
each rule becomes a candidate direction in A5's pool).

## Governance and QA
- Roles unchanged (designer, verifier, safety, redteam, foreman); new tools in ops/ are called by the designer role.
- PI decisions needed before round 1: acquisition weights (void fraction vs fixation margin), batch size, whether the mentor may
leave the parametric families (needs B4), and the 3 MPa gate-or-flag question (affects P(pass)).
- QA: R21 (verdicts cite case dirs, no surrogate numbers in labels), R22 (every proposal file lists its source: surrogate /
naive-mentor / principle direction / exploration) - provenance like window_drive today.
- Timeline: week 1 = C + A1-A4 (no GPU); week 2 = round 1 of A (20 designs) + first 5 B ideas; week 3 = refit, report.
