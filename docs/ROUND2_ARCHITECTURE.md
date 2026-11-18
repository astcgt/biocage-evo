# Round-2 evolution architecture: surrogate-guided active learning + naive/mentor ideation + principle extraction

PI 2026-11-18: 「下一輪方案：其他甲乙丙都不錯，深入構造細節」. This document is the construction detail of the three approved parts
(A surrogate + active learning, B naive / mentor ideation, C principle extraction) on top of the existing platform
(old repo: h14 build -> h24 preflight -> FEBio GPU runs -> e03 / e04 / e07 read-outs; evo repo: fric_compare -> e07_batch ->
collect_split -> mu_req_field -> capability labels -> h37 QA). Nothing here replaces a FEBio verdict: surrogates and LLM
agents only decide WHAT to simulate next.
**Rev 2 (PI 2026-11-18 second message, sections marked [rev 2]; D-H are new):** nominal coverage 90 % with a grouped validation report; design grammar + geometry compiler; senior role with falsifiable experiment cards; mentor may repair but must keep the mechanism; program-only judging; C also discovers new design parameters for A; creativity must be proven against controls; literature first when blocked; Hugging Face repository registered.
Plain-language summary for the PI: human_study/PI_REPORT_2026-11-18_direction.md (old repo).

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
[rev 3 correction: descriptors are computed from the h12 mesh npz named by each params file (human_study/al/meshes/*.npz: phi, hard, region, coordinates), not from cage_elems.npz, which holds only block / index / layer / area. For today's families the mesh is fixed by family + d. First validation result: docs/DECISIONS.md 2026-11-18.]
**A1 Features.** x = [E_hard, E_soft, d, theta, one-hot family] + geometric descriptors computed from cage_elems.npz by code
(soft fraction, posterior soft thickness, hard-rim continuity, contact area on each endplate, void fraction, posterior lip
height). Descriptor code: ops/descriptors.py (new; pure numpy; also used by C).
**A2 Targets (one model per target, shared inputs).**
- y1 [rev 3, audit D-20261118-31] two judged quantities, as in fric_compare: post_ext = SIGNED posterior translation in extension at the
  intact ROM (limits 0.45 / 0.55 mm) and uh_flex = any-direction translation in flexion at 1.5 N m (limit 1 mm; in flexion the cage
  moves anteriorly, so the posterior limit never acts there)
- y2 mu_req_max (regression; tied screening shortcut, cheap label available for all 149)
- y3 shear_req_p99_MPa (regression; PI 2026-11-18 required strength)
- y4 computability (classifier: not-computable-both-laws / unstable-window vs computed) - the platform [數值] risk
- y5 tied class = compression-peak / -sustained (classifier) - the cheap gate most designs fail
**A3 Model.** Gaussian process with an ARD Matern-5/2 kernel per target (scikit-learn GaussianProcessRegressor / Classifier; 73-149
points fit in seconds on CPU), targets log-transformed where positive (mu_req, shear). Alternative if GP calibration is poor:
small ensemble of gradient-boosted trees for the mean + GP for the uncertainty. Fitting script ops/surrogate_fit.py -> results/surrogate/validation_<date>.json + loo_predictions_<date>.csv [rev 3: no model file is stored; the model is refitted from
the tables by ops/propose_round.py, so R23 compares the validation file with the input tables (mu_req_field.csv, verdicts.json), not with a pickle].
**A4 Validation before use (gate) [rev 2].** Nominal coverage is fixed at **90 %** (PI). Validation is **leave-one-group-out**:
a group = all rows that share the gene tuple + family (later: the grammar specification hash), merged with any rows that share
a launched deck hash (launched_feb.sha256) - so replicate decks (p050 / p068 / p084 / p127 are one deck) and the same design
under another insertion process or friction law (different deck hash, same genes) stay in ONE fold - a replicate
may never sit on both sides (data leakage). Report per target, in results/surrogate/validation_<date>.json:
- empirical coverage of the 90 % interval (with its sampling error: about +-0.07 at ~70 groups),
- prediction interval width (median, p90; mm for y1) next to the scales that matter: grey band 0.10 mm, replicate noise 0.012 mm,
- MAE and RMSE, and the same for a family-mean baseline (skill = 1 - RMSE / RMSE_baseline),
- all of the above per design family (with n; reported, not gated) and **leave-one-family-out** (the proxy for a new geometry region).
Steering rule (授權自行決定 for the numbers other than 90 %): the surrogate may steer proposals for a target only if empirical
coverage is 0.80-0.95 (= nominal 90 % within sampling noise) AND skill >= 0.2 (this replaces rev 1's R2 >= 0.5: R2 against the
global mean is inflated by between-family differences; skill is measured against the family mean) AND the median interval is narrower than the
5-95 % spread of the training outputs; otherwise that target is exploration-only (pure uncertainty sampling). If coverage is
off but skill is fine: recalibrate with cross-conformal intervals weighted by the GP standard deviation ("Conformal approach to Gaussian process surrogate evaluation with coverage guarantees", arXiv
2401.07733; conformal Bayesian optimisation, Stanton et al., AISTATS 2023) before giving up. Out-of-distribution rule: a
candidate whose descriptor distance to the training set (k-nearest-neighbour distance, normalised) exceeds the largest
leave-one-group-out distance is labelled OOD - the surrogate may neither promote nor reject it; it enters only through the
exploration quota or part B, and its residual after simulation is sent to C6. QA: h37 R21 (every verdict row cites a FEBio
case dir; surrogate numbers never enter verdicts.json / labels) and R23 (validation file exists, grouped, newer than its input tables mu_req_field.csv and verdicts.json).
**A5 Acquisition (batch of 20-30 per round).** Score = P(pass all gates) x U(biodisc void fraction, mu_req margin) + beta x
predictive std, with P(pass) = P(post_ext < 0.45) x P(uh_flex < 1.0) x P(y5 = pass) x P(y4 computable) [rev 3; y4 has 6 positives and cannot be
validated - until it can, P(y4) = family base rate] (y3 shear is a flag + ranking key since PI 2026-11-18, not in P(pass));
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
[rev 2 precedence: where B1-B6 differ from section B' (B7-B13), B' wins - in particular 10 separate naive processes instead of
one (B8), and archive distance, feasibility checks and build success are computed by code, not by the mentor (B11, B13).]
Source: D'Ambrosio, Albalak, Lehman, Stanley 2026, arXiv 2611.11725 (naive model kept ignorant of the topic produces seed
ideas; a mentor model turns them into concrete proposals; novelty and usefulness both rose). Related: EvoSci (ACL 2026; not re-verified 2026-11-18, the other four citations of B and C were checked against arXiv)
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
- [rev 2] Roles: see section D (naive, senior, mentor added; verifier / safety / red team extended; one process per role).
- [rev 3: all decided 2026-11-18 except the exact weight, see 'PI decisions' below] Originally open before round 1: acquisition weights (void fraction vs fixation margin), batch size, whether the mentor may
leave the parametric families (needs B4), the control-arm budget (section E) and the Hugging Face content / visibility (section G). [rev 2: the 3 MPa question was settled 2026-11-18 as flag + ranking.]
- QA: R21 (verdicts cite case dirs, no surrogate numbers in labels), R22 (every proposal file lists its source: surrogate /
naive-mentor / principle direction / exploration) - provenance like window_drive today.
- Timeline: week 1 = C + A1-A4 (no GPU); week 2 = round 1 of A (20 designs) + first 5 B ideas; week 3 = refit, report.

## B' . Part B amendments [rev 2, PI 2026-11-18]
**B7 Chain.** naive (free ideas) -> senior (falsifiable experiment card) -> mentor (executable design specification in the
Design Grammar) -> Geometry Compiler (program) -> program judges. No LLM decides build success, distance or physics.
**B8 Naive proposer.** 10 SEPARATE processes, one idea each (one process writing 10 ideas fixates on its first: Deng, Brucks,
Toubia, arXiv 2602.20408), each started in an empty directory outside both repositories (full tools, nothing to read), each
with a different everyday-analogy cue (door wedge, wall plug, climbing cam, suction cup, zip tie ...; persona cues raised idea
diversity in the same paper; simple "think differently" prompts beat elaborate creativity methods, IDEAFix arXiv 2606.00875).
Output per idea: one sentence "what stops it sliding out" (the physical mechanism), a sketch, expected weak point.
**B9 Distinct physical mechanisms.** A blind tagger process (small model, sees only the idea text) assigns one tag from an open
taxonomy (wedge self-locking, posterior lip / hook on the uncinate, preload by elastic expansion, conforming seat, curvature
interlock, auxetic expansion, directional compliance, ... + "new: <name>"). Code keeps at most 2 ideas per tag per round and
asks for replacements; the same tagger tags the mentor's final specification, and code compares tag before / after
(mechanism-preservation check). Honest limit: tagging is the weakest judge here - geometric distance in descriptor space is
the hard criterion, and descriptors can miss a new topology (that gap is C6's job).
**B10 Senior (new role).** For every surviving idea writes a pre-registered experiment card: hypothesis ("if mechanism M
works, read-out Y is below Z"), the ablation twin (the same design with M removed), the read-out (only existing platform read-outs). Budget rule: the card's
primary read-out is mu_req from tied screening, run for the design AND its twin (the twin gets tied screening only: +5 cheap
runs per round, no frictional windows); posterior translation / shear_req / compression gate are secondary read-outs of the
design alone, the refutation threshold (outside
replicate noise 0.012 mm / the mu_req shortcut tolerance) and what is learnt either way. The card is hashed and time-stamped
before the simulation starts; code scores it confirmed / refuted / inconclusive (Popper-style sequential falsification: Huang
et al. 2025, arXiv 2502.09858, "Popper"). A refuted card is a useful result; an inconclusive one is waste and is counted.
**B11 Mentor.** Knows the whole platform (PLAN, principles, archive, grammar, compiler limits). May repair infeasible detail
(thickness, printability, insertion) but must keep the mechanism: (i) every rejection cites an S1-S10 rule or a compiler error -
"not promising" is not a reason; (ii) the mechanism tag must survive the rewrite; (iii) audit lane: each round code draws 1
mentor-rejected idea at random and compiles it anyway (minimal repair) - if it builds and screens well it is a red-team
finding against the mentor; (iv) at least 2 of the <= 5 kept ideas lie beyond the archive-distance floor.
**B12 Design Grammar (v0, grows by change request).** A JSON specification on the 0.2 mm grid inside the inset footprint:
primitives (footprint-offset rings in whole 0.4 mm perimeters, slabs, struts, endplate-conforming shells, ramps / wedges with
height as a function of position, lips / ridges at named sites, periodic cells), operations (union, subtract, intersect,
mirror, linear / polar pattern), a material field phi(x, y, z) (piecewise or a function of distance to endplate / window /
anterior-posterior position; 'mix' or 'interleave' realisation, material map kept resolved - no homogenisation), globals
(d in {0.5, 1.0, 1.5} mm, E_hard, E_soft, theta). Escape hatch: `custom_field` = a pure Python function returning occupancy
and phi (PLAN encoding 2); each use is logged and becomes a grammar-extension request, so the grammar never caps the ideas.
**B13 Geometry Compiler (ops/geom_compile.py, new).** specification -> voxel field -> L0 checks S1 / S3 / S4 / S5 by code ->
hex mesh npz in the h12 format -> h14 -> h24 preflight. Verified 2026-11-18: h14 already reads the per-element map (region,
phi, hard) from the cage npz, so the consuming side exists; h12 only generates "footprint minus one window" columns, so the
generating side (arbitrary occupancy, face quads, wall node sets) is the 2-3 day item. Repairs allowed: drop islands, dilate
below-minimum features, enforce declared symmetry - all logged; the compiler REFUSES when repairs would change > 2 % of the
solid voxels. Acceptance test owned by the verifier: the existing parametric families written in the grammar must reproduce
the h12 npz (same element count and phi histogram) and, for 2 designs, the same verdict within replicate noise. Related
language work: solver-aided hierarchical CAD language for LLMs (Jones et al., arXiv 2502.09819).

## C' . Part C amendment [rev 2]
**C6 Finding new design parameters (for A's out-of-distribution problem).** The 4 genes + family label mean nothing for a new
topology, so the surrogate's inputs move to quantities defined for ANY material map: (a) geometric descriptors (C1), (b)
cheap-physics descriptors - the tied-screening outputs (mu_req, governing window) used as INPUTS of the friction targets
(two stages: ranking the candidate pool uses geometry only, because (b) exists only after a design's tied screening; (b) then
feeds the second-stage decision of A6 - which designs get frictional windows; the shortcut already ranks the gold standard with Spearman 0.90, results/method/mu_req_vs_fric5.json).
Loop after every round: residuals outside the 90 % interval and all OOD-labelled designs -> the LLM proposes features that
could explain them -> code implements and scores each by the change in leave-one-group-out error and coverage (not by
correlation alone) -> kept features become surrogate inputs, a plain-language rule, and - when the feature is something a
designer can set - a new knob in the Design Grammar (B12) and a new axis of A's candidate pool. Sources (from the 2026-11-18
search, summaries only): Large Discovery Models, arXiv 2608.15669 (search without feature discovery converges early to a
worse plateau); Human-LLM Collaborative Feature Engineering for Tabular Data (ICLR 2026; LLM proposes feature operations, a Bayesian surrogate selects); ReElicit, arXiv 2605.19093
(LLM-elicited feature space + Gaussian process). No paper found that combines LLM features, OOD surrogates and new topology.

## D. Agents and teams [rev 2]
One process per role, full tools, own folder; hand-over only by schema-checked JSON on the board (GOVERNANCE.md; the
restricted-tools sentence there is superseded by PI 2026-10-27).
| team | role | model / context | sees | produces | cannot |
|---|---|---|---|---|---|
| ideation | naive x10 | small model, empty directory | lay task + S1-S10 in plain words | 1 idea each | see archive, results |
| ideation | tagger | small model | idea text only (later: specification only) | mechanism tag | see who wrote it |
| ideation | senior | mid context: read-outs and tests, not results of this round | ideas | experiment cards (pre-registered) | change ideas |
| ideation | mentor | strongest model, full context | ideas + cards + archive + principles | <= 5 grammar specifications, rejections with rule ids | judge outcomes |
| search | designer (existing) | full context | surrogate proposals (A5), principles | params / specifications for part A | change the surrogate gate |
| program judge | compiler, L0, distance, verdict chain, card scorer | code | files | build ok, S1-S5, distance, verdicts, card outcome | - |
| validation | verifier (extended) | blinded to rationale | results, code | PASS / HOLD: grouped validation report rerun, replicate decks, compiler acceptance test, leakage check | judge design merit |
| validation | safety guard (existing) | blinded | compiled designs | VETO on S1-S10 | add rules without the PI |
| validation | QA auditor + h37 | independent | everything | R21-R25 status | - |
| red team | red team (extended) | full | everything | findings with evidence | fix things |
| operations | foreman (existing) | - | queues | resource use | science |
Red-team targets this round: (1) surrogate over-confidence - designs it rates safest in thin-data regions; (2) compiler
loopholes - specifications that compile yet break S3 / S5 or differ from the mesh; (3) evaluator gaming - passing through
grey, flagged or not-computable paths; (4) mentor bias - kept vs rejected distributions, tag drift, audit-lane results;
(5) pseudo-novelty - 10 ideas that are one design; (6) card gaming - hypotheses too vague to refute; (7) canaries for the verifier.
Judging has three layers: program (facts: build, rules, distance, simulation - decisive), validation team (is the process
sound: PASS / HOLD / VETO, never "is the design good"), PI (rule changes, disputes open after two rounds). No LLM scores
novelty or quality. New h37 checks: R21, R22 (as before), R23 (grouped validation file), R24 (card hash and time precede
started_at), R25 (the naive and tagger session logs show no read outside their own directory and no web search - an empty directory alone
does not isolate an agent with full tools; proposal source recorded). Naive and tagger have their own prompts (not common.md)
and are exempt from section F: a naive agent that reads the literature is no longer naive.

## E. Proving that the AI ideas add effective exploration [rev 2]
Same compiler and judges; B vs R at equal design count (5 vs 5), B vs A compared per GPU-hour (A runs 20); metrics fixed before round 1 (results/round2/prereg.json):
arm A = surrogate search inside the existing families; arm B = naive -> senior -> mentor; arm R (control) = random draws from
the Design Grammar without any LLM; optional arm M = mentor alone. Metrics: build success rate; valid-novel yield per GPU-hour
(passes L0, computable, beyond the archive-distance floor); archive cells gained (quality-diversity score); hypervolume gain on
(fixation margin, void fraction); new mechanism tags with >= 1 passing design; surrogate learning gain (drop in grouped
validation error after adding the arm's data); card outcomes. Statistics: bootstrap intervals / permutation test on B - R and
B - A; the prereg states the detectable gap, not a round count (one-sided exact test, 5 %): with 5 per arm only 4 of 5 vs 0 of 5
is distinguishable; with 15 per arm (3 rounds) 8 of 15 vs 2 of 15, or 6 vs 1; with 25 per arm 8 vs 2. So round 1 is
descriptive, and after 3 rounds only a large advantage of the AI arm can be claimed. Known risk from the
literature: LLM ideas are individually creative but homogeneous as a population (arXiv 2602.20408, 2606.00875), which is
exactly what arm R and the per-tag cap test. Cost of arm R: 5 designs = 5-15 GPU-h per round (PI decision).

## F. Literature first [rev 2, standing rule]
When a role or the integrator is blocked (method does not converge, validation fails, no obvious design), the first step is
a literature search; the search and what it returned (or "none found") is cited in the finding / decision.

## G. Hugging Face [rev 2]
Repository named by the PI: ast-atp/biocage_evo (registered in config.json). State 2026-11-18: public MODEL repository, empty;
no client, token or registered SSH key on this server, so nothing was uploaded. Proposed use (PI to confirm): surrogate
models + validation reports + the training table and design archive snapshot per round, so each round is reproducible from
one tagged revision. [rev 3] PI 2026-11-18: any project content may go there and the repository stays public; first push 80212f0 (tables,
surrogate validation code and report). Every upload is scanned for server paths, e-mail addresses and AI attribution first.

## PI decisions 2026-11-18 04:58 [rev 3]
Candidate pool of arm A [rev 3, audit D-20261118-28]: design-A families only (the 24 design-B meshes have void 0.645 / contact
22.55 mm2 against 0.597 / 37.44 mm2 for the 77 design-A meshes, and 23 of the 24 design-B designs are compression-sustained), so the
space weight cannot tilt the pool today. PI 2026-11-18 06:02: weight = fixation margin 80 : biodisc space 20 (replaces the integrator's 70 : 30 reading).
Utility U in A5 = 0.8 x fixation-margin score + 0.2 x biodisc-space score (PI 2026-11-18 06:02 「採樣權重 80：20」; earlier: PI 2026-11-18 05:31: 「更正：空間還是保留」, withdrawing 「先不管」; S4 >= 50 % stays a
constraint in the grammar checks and the naive task text); batch = A 20 + B 5
(+ 5 twins) + R 5 + 1 audit; mentor may leave the families (>= 2 of 5 beyond the distance floor); control arm R approved;
Hugging Face uploads under the PI's identity only, no AI / Claude trace in contributors, commit messages or the card.

## State 2026-11-18 11:55 [rev 4]
Built and tested without the platform: Geometry Compiler + grammar reference (B12 / B13; relabels the existing lattice), proposal program (A5, dry run), principle extraction (C; composites not adopted by the declared rule), pre-registration and control-arm sampler (E), role prompts (B8-B11), h37 R21 / R23. Waiting for the platform: any simulation of a new design (release shock, new-design runner). Results and findings: docs/DECISIONS.md 2026-11-18 11:55.

## PI decisions 2026-11-18 12:21 on the cage height [rev 5]
The gene d is the cage's height above the natural disc space (撐高量), not the insertion step. Designs are compared at the same height: every design of every arm runs at the reference height 0.8 mm (verdict; first set to 1.0 mm, changed the same day after the PI delegated the choice - evidence results/round2/settings_optimisation_2026-11-18.json) and the loosened height 0.5 mm (fixation without relying on the tissue squeeze force). d is no longer proposed by any arm (this replaces 'd' in the feature list of A1 for proposals; it stays a model input). A5 as implemented: ops/propose_round.py docstring; pre-registration: results/round2/prereg.json + prereg_amendment_2026-11-18a.json. Rules of part C are listed only when they survive at the same height.

## Batch per round as of 2026-11-18 12:47 [rev 6]
A 10 runs (4 new designs x 2 heights + 2 replicates), B <= 7 designs x 2 heights + 7 ablation twins (tied, loosened height), R 7 designs x 2 heights, audit lane 1 design x 2 heights; 14 naive ideas per round. This replaces every earlier batch figure in this document (20 / 5 / 5 and '10 seed ideas'). Pre-registration: results/round2/prereg.json + amendments a, b, c.

## H. Timeline [rev 2]
Week 1: C (incl. C6 descriptors) + A1-A4 grouped validation + Design Grammar v0 and Geometry Compiler with its acceptance test
(no GPU except the 2 acceptance designs). Week 2: round 1 = A 20 (4 exploration + 2 replicates inside) + B 5 (+ 5 ablation
twins, tied screening only) + R 5 (approved 2026-11-18) + 1 audit-lane design. Week 3: refit, C6, arm comparison (descriptive), report.
