# Ideas and architecture proposals (2026-10-31)

Ranked within each group by value for the main goal (a resorbable cage that holds a living disc without screws) against
effort. "PI" marks ideas that touch an agreed rule (DECISIONS.md) and need a decision before use. Each idea names the first
cheap experiment and what could go wrong.

## 1. Design concepts (seeds for the evolutionary designer, or testable by hand now)

| # | Idea | Why it could matter | First cheap test | Risk / what could go wrong |
|---|---|---|---|---|
| D1 | **Concavity interlock**: a hard core sized to the insertable envelope plus a compliant crown that refills the C3 inferior concavity (2.1-2.7 mm deep, apex posterior; Chen 2013) after insertion | The same concavity that blocks insertion blocks expulsion; posterior push-out on the contour-matched cage without rim was 93 N (< 135 N guard), so geometric interlock is the available lever once teeth and screws are excluded | h12 variant: core height = minimum gap along the insertion path, crown of soft PLCL; run split2 protocol + push_post on p062 geometry | the crown is the part that creeps / degrades first (A3 in RISKS.md); compression rule may fail; insertion strain of the crown |
| D2 | **Posterior lip in compliant PLCL** (inside the disc space, no canal intrusion) that bears only on posterior migration | Direct answer to the posterior guard; keeps the biodisc window | push_post on two lip heights (0.5, 1.0 mm) | nerve-safety check (canal clearance S1b, safety guard); soft lip may fold |
| D3 | **Radial stiffness grading made explicit** (hard rim, soft inner band): radial-gradient designs pass most often (45/65) | The screen already points there; the evolution should start from this basin | nothing to compute; include as a designer seed | may over-constrain novelty; keep other seeds |
| D4 | **Micro-textured contact faces within the 0.2 mm layer** (printed ridges across the expulsion direction) | Polished polymers have low, stress-independent friction (Damm 2015); ridges raise effective friction without teeth or bone penetration; PI rule allows shape + friction | friction coupon test first (ridged vs smooth PLCL on wet bone); model as a higher mu for ridged faces | needs the PLCL-bone friction measurement anyway; ridges wear or fill with tissue; printing resolution 0.4 mm |
| D5 | **Bistable or snap-fit expansion after insertion** (allowed by the PI 2026-10-27) | Overcomes the 35-41 % compression a contour-matched hard core would need to slide in | 1-D spring model of a bistable arch in PLCL 85:15 (strain <= 3 %) | hard PLCL yield ~5 %; mechanism may not survive 16 weeks; verifier/safety must check carefully |
| D6 | **Biodisc-space topology as a design variable** (connected void from endplate to endplate, 50 % floor) rather than a central window | S4 makes the void a first-class objective; MAP-Elites axis | define the void-fraction descriptor in constraints.py | void connectivity vs structural continuity (S3) conflict |
| D7 (PI) | **Lower the follower load for the compression rule to the TE-disc-sharing scenario** or raise it to 250 N for a sensitivity bound (Patwardhan 2000) | 100 N is a lower bound of in vivo loads; the rule's verdicts depend on it | re-run e05 on existing states at the 50 N state? not available; one design at 250 N | changes verdict counts; needs PI |

## 2. Methods

| # | Idea | Why | First test | Risk |
|---|---|---|---|---|
| M1 | **Exact-moment interpolation in e04/e05**: evaluate at the two states bracketing 1.5 N m and interpolate metrics | Removes the 4-13 % sampling overshoot seen on p062; makes split and sequential results identical by construction | implement as an option, compare on p062 (expect extension slip 0.134 vs 0.146 now) | both states must exist in the plot file (true for the window steps); metrics are not exactly linear in M |
| M2 | **Limit-surface slip mode on tied results** (Goyal, Ruina & Papadopoulos 1991): instantaneous centre of slip, spin vs translation, bounded outward displacement of the farthest cage point | Answers lateral bending / axial rotation dislocation without friction runs; already proposed 2026-10-28 | one design (p062) from existing face tractions | theory assumes rigid faces and uniform mu; must agree with the friction batch |
| M3 | **Degradation and maturation sweep**: scale E_soft 1.0 -> 0.1 and E_biodisc 0.03 -> 1 MPa in staged runs at 0/8/16/26 weeks | The support window is the device's purpose; fixation may shift from friction to tissue | 1 design x 4 stages (= 4 split2 runs, ~2 h) | lacks measured degradation curves; use literature brackets |
| M4 | **Sustained-stress criterion for hard PLCL** (Eyring / Smit 2008): peak hard-phase principal stress at t 3.5 vs 25 % of wet yield | Lactide cages failed by creep rupture at 3 months; nothing in the pipeline checks it | post-processing only (e06) on existing xplt states | yield of printed PLCL 85:15 unknown (15-40 MPa bracket) |
| M5 | **Uncertainty quantification over material ranges**: report pass probability per design over the E_hard x E_soft x strength ranges with the existing GP | Reviewers expect UQ (V&V 40); the AL surrogate already exists | fit GP on mu_req and compression; sample | surrogate error at the boundaries |
| M6 | **Surrogate-assisted illumination (SAIL)** for the evolution: GP trained on the L2 archive drives MAP-Elites | Each L2 evaluation costs 23-46 min; SAIL cut evaluations by orders of magnitude on airfoils | after 40 archive entries | voxel descriptors for the GP must be designed |
| M7 | **Reduced model without homogenising the cage interior** (PI rule): keep the cage mesh and material map, replace bone and ligaments by calibrated springs on the endplate nodes | 5-10x cheaper windows for screening; the material layout stays resolved for the evo agents | calibrate on p062: endplate stiffness map from the full model | contact with facets is lost; use only for L1 ranking, never for verdicts |
| M8 | **Automated "rotation applied" and completeness checks** after every run (joint moment rises, all six windows present, exit code vs termination line) | Both bugs of this week would have been caught within minutes | 30-line script in h31 / collect_split | none |
| M9 | **Rotation-controlled gate-2 references for gpufe** (PI protocol 2026-10-28) instead of moment control | Both codes stall at facet onset under moment control; the comparison itself is ill-posed | build 6 FEBio reference runs with the generic rigid joint | gpufe must implement the joint driver (8 h) |

## 3. Agent architecture

| # | Idea | Why | First step | Risk |
|---|---|---|---|---|
| A1 | **Designer as program synthesis with an archive** (FunSearch / AlphaEvolve pattern): proposals are short design programs that emit voxel fields; the engine mutates numeric constants; scored by archive cells filled that survive verifier + safety | Matches PLAN.md; the only part of the four-agent plan not started | designer.md + schema (docs/DESIGNER_KICKOFF.md) | needs the evaluator chain (voxel -> h12 -> h14 -> split2 -> e04/e05) end to end; evaluator bugs propagate silently |
| A2 | **HOLD gate and frozen tree in code** (evo_daemon refuses round N+1 on verifier HOLD or dirty tree) | Governance exists on paper; round 3 started under HOLD | 20 lines in evo_daemon.sh | may stall rounds when the verifier is conservative; PI override file |
| A3 | **Canaries**: the red team plants one synthetic bad result per round; the verifier's miss rate is tracked | GOVERNANCE.md promises it; never done | define a canary folder and a format | effort for the red team; false alarms |
| A4 | **Integrator reply file per finding** (status: fixed / rejected / escalated, with evidence) and a CR register | 29 findings unanswered; roles repeat themselves | generate CR-*.json from the 9 verdicts | time |
| A5 | **Literature agent with verification rule** (cite only what a fetched page confirms; keep UNVERIFIED flags) | Fabricated references are the main AI risk for the paper | the LITERATURE.md format already does this | search limits |
| A6 | **Provenance database** (SQLite): every number keyed by design, run dir, code hashes, settings class; verdict lists generated, never hand-merged | The aggregator rewrite of today is the first step | migrate collect_split outputs | schema churn |
| A7 | **Smaller, staged agent fan-out**: audits as 2-3 agents per phase with the main session doing synthesis; agent rounds scheduled off-peak | 25/29 agents failed today on the usage limit; inline work was more reliable | adopt as a working rule | slower wall clock |

## 4. Compute pipeline architecture

| # | Idea | Why | First step | Risk |
|---|---|---|---|---|
| P1 | **Scheduler reads a tuning file** (scheduler_tuning.json) instead of constants edited in code; atomic writes everywhere | The foreman truncated h19 on a full disk | 30 lines in h19 + foreman prompt change | none |
| P2 | **Disk guard**: pause launches below 30 GB free, delete .dmp of finished runs nightly, alert | 0 MB today | in h19 pass loop | deleting a checkpoint of a run that will be resumed (keep for unfinished) |
| P3 | **2 cores per GPU run** (16 concurrent under the 32-core quota) | GPU time is the binding resource only when CPU quota allows; cuDSS offloads the solve | benchmark one split2 design at 2 vs 4 cores | assembly-bound steps slow down; throughput may not improve |
| P4 | **Post-processing as part of the run** (h31 calls e04/e05 on each window when it ends, on the same cores) | No idle queue between batches; completeness by construction | 15 lines in h31 | adds ~5 min per window to the run slot |
| P5 | **Content-addressed results** (results keyed by sha256 of case.feb + code) with automatic invalidation when h14/h30/h31 change | h24 does this for inputs; outputs still rely on folder names | extend provenance in e03 | migration of existing files |
| P6 | **Dashboard**: one HTML status page regenerated hourly from the scheduler log, queue and merged verdicts (the visual report of today as a template) | The PI and the foreman read the same numbers | script + cron in evo_daemon | none |
| P7 (PI) | **Folder rename** of the OLD repo (scheduled) only after all daemons are stopped; update absolute paths in h-scripts, collect_split, config.json | Absolute paths are hard-coded in several places | grep for the path string | broken paths mid-batch |

## 5. Experiments that unlock the paper (outside the simulation)
1. PLCL-bone friction (wet endplate, 0.25-1 MPa, smooth vs ridged printed faces) - replaces the assumed 0.3.
2. Compression set and relaxation of PLCL 50:50 at 15 % / 25 % strain, 1 h to 28 d, 37 C wet - replaces the interim rule.
3. Creep rupture of printed PLCL 85:15 (Eyring fit) - adds the hard-phase lifetime criterion.
4. Hydrolysis of printed coupons and whole cages, 0-26 weeks - feeds the degradation sweep.
5. Push-out of printed prototypes in foam blocks (100 N preload, both directions) - comparability with Mobi-C 142 N / MOVE-C 202 N.
6. One cadaver C3-C4 FSU test with cage tracking (2 N m + 75-100 N follower, 3 cycles) - the validation a device claim needs.
