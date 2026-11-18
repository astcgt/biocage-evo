# Decisions - BIOCAGE free-form evolution (biocage-evo)

Model decisions inherited from the human C3-C4 study: docs/DECISIONS_baseline_human_c34.md (read-only copy). Entries below are
copied from that log's evo section (2026-10-25/26) and continue here; the old log is no longer updated for evo.

## Free-form evolutionary design (evo), PI 2026-10-25
Goal (PI): PLCL-only BIOCAGE, shape and material grown freely (evolution-like) to go beyond human-imagined designs; minimum
constraints = surgery-compatible + no nerve / bone harm; maximum freedom otherwise. Plan: `human_study/evo/PLAN.md`.
- Roles: four adversarial AI roles (Claude, headless) + a computational engine (evolution + simulation):
  designer (free ideation / mutation), verifier (reliability + reproducibility of the evaluation pipeline),
  safety guard (minimum purpose + nerve / bone safety), red team (finds and amplifies holes in all others, reports options).
- Space: STRICTLY inside the disc space (inset footprint, between the endplates); no bone penetration (no teeth / keels / screws),
  nothing protruding out of the disc space. Fixation must come from shape + friction.
- Material: every voxel = void or any PLCL 85:15 / 50:50 blend fraction phi in [0, 1] (Duan 2021 sigmoid as in the AL),
  print resolution 0.4 mm line / 0.2 mm layer.
- Biodisc space: the 60 % central-window rule is dropped for evo; replaced by (a) a low floor on the biodisc (void) volume and
  (b) the void must connect both endplates; volume is an objective -> trade-off chart (biodisc space vs fixation) for the PI.
- Insertion: one piece, from anterior, may be compressed during insertion and spring back (as the 'expand' insertion, shrink 0.8).
- Fixation score: minimise the friction coefficient needed to hold, worst of the 6 physiological directions (mu_req = max over
  flexion / extension / left-right LB / left-right AR); no hard pass mark.
- Compute: about half of CPU / GPU for evo, half for the physio AL.
- 2026-10-25 PI: avoid CPU-bound simulation where a credible GPU method close to reality exists; main goal = no slip-out,
  checked smartly; compare methods first (human_study/evo/METHODS_COMPARISON.md). New e02 (scripts/7_evo/e02_friction_limit.py):
  friction limit with twist (linear program) on tied runs. p062: force ratio 0.35-0.52 vs friction limit 0.75-2.15 (twist up to
  ~1 N m on the glued face in lateral bending, coupled axial rotation) -> the current force ratio is optimistic, the limit
  pessimistic; real friction simulation needed to decide. Proposal: own GPU explicit solver (TLED) on the same FEBio mesh,
  verified against FEBio in 5 gates. Batch on all 76 physio runs: tmux biocage_evo_e02 -> human_study/evo/method/.
- 2026-10-25 PI: evo slip-out failure = cage centre translation relative to the bone > 1 mm (as the earlier 1 mm relative-slip limit); also record ratcheting over cycles.
- 2026-10-26 PI asked how the four roles are managed (independent, cooperating, supervising, no data mixing): proposal human_study/evo/GOVERNANCE.md (IV&V, separation of duties, blackboard, structured JSON hand-overs, blinding, provenance, enforced per-role tool permissions). Pending PI comments.
- 2026-10-26 PI answers (evo):
  (1) solver core accepted: GPU Newton (cuDSS) + explicit friction return mapping (pure explicit DR too slow for bone vs nucleus);
  (2) three-tier evaluation accepted (fast screen < 1 min, full GPU 10-30 min for the front runners, FEBio for finalists);
  (3) friction coefficient PLCL-bone for the real-friction check: from literature (analyst to search and propose);
  (4) 6 directions x 3 cycles for ratcheting: enough;
  (5) S1-S9 values: PI asked for a plainer explanation (pending);
  (6) twist in flexion / extension (I-001): define precisely, search literature, analyse, propose fixes before using the numbers;
  (7) AL objective: wait for the real-friction GPU results before changing it;
  (8) start verifier, safety guard, red team now (designer later);
  (9) all roles on claude-opus-5-5, observe for one day.
- 2026-10-26 BUG FOUND (I-001, while analysing the 'twist in flexion'): h14 physio moment curves lacked the window-start
  point (ts, 0), so each moment ramped from t 3.5 instead of starting at its own window: at the flexion peak C3 also carried
  Rx 299 / Rz 166 N mm, at the right-LB peak Rz 833 N mm (p062 C3pot.txt). Every physio run so far (76 AL pre-runs,
  physio_test, facet_test, lb_test) had COMBINED loading instead of the agreed one-direction pure moments (Wilke 1998 /
  Panjabi testing convention). Fixed in h14 (pts += (ts, 0)); other tests unchanged. Consequences: physio ROM, stalls
  (extension / left LB), slip safety factors and the e02 twist numbers are invalid and must be re-run; the physio AL had not
  started (queue empty), no compute lost. Cage-mesh / model symmetry checked: surfaces mirror within 0.01 mm, bone tet meshes
  not mirrored (node offsets 0.04-0.6 mm) - only a small numerical asymmetry expected.
- 2026-10-26 physio reruns with the fixed curves queued: human_study/al_v2/physio_fix/{p062,p063,p014} (settings class = physio_test, preflight OK) to quantify the bug's effect before the physio AL.
- 2026-10-26 PI (evo constraints):
  friction coefficient for the real-friction check: mu = 0.3 main (smooth polymer, wet), sensitivity 0.2 / 0.45; every
  design also reports the mu needed to hold (no PLCL-bone measurement in the literature; coupon test recommended);
  S4 biodisc space floor = 50 % of the disc-space volume (was proposed 30 %); S5 printability: keep 0.4 mm / 45 deg overhang;
  S9 replaced: the test goal is NO slip-out in ANY direction (cage-centre translation > 1 mm relative to C3 or C4 = fail,
  6 directions x 3 cycles, ratcheting recorded); posterior migration (toward the cord) is absolutely unacceptable
  (reported separately; any posterior net translation is flagged even below 1 mm).
- 2026-10-26 red-team F-0002: pre-fix physio results marked INVALID (al_v2/PHYSIO_INVALID_2026-10-26.md, copies in physio_analysis/ and evo/method/; METHODS_COMPARISON.md section A and ISSUES.md I-002 flagged).
- 2026-10-26 PI (evo): (a) posterior limit 0.5 mm net migration toward the cord and minimum posterior push-out 135 N (safety guard
  proposal, Moroney 1988 max cervical AP shear) accepted; (b) biodisc maturation / support period: from the lab's previous work
  (Lintz 2021 dissertation, human_study/evo/PRIOR_FAILURES_Lintz2021.md): >= 16 weeks main, 26 weeks sensitivity; (c) no
  radiographic marker for now, imaging follow-up assumed possible (out of scope); (d) insertion: any feasible insertion method
  may be considered (oblique, staged, ...); the 53-60 % compression needed for a front slide-in and the permanent-set risk of
  hard PLCL must be faced: analyst to research surgical distraction / endplate preparation practice; (e) commit the work
  (author austonliuyi only, no Claude attribution).
- 2026-10-26 insertion feasibility (analyst, for PI): native C3-C4 gap in the footprint 2.95-5.30 mm (concave endplates, tallest
  in the middle). A contour-matched cage (design A, all AL designs) slid in from anterior WITHOUT compression needs an extra
  transient parallel distraction of 2.35 mm beyond the final distraction d (total 2.85-3.85 mm over native for d 0.5-1.5);
  without it the tallest column must be compressed 35-41 %. Hard PLCL 85:15 yield strain ~5 % (25 MPa / ~400 MPa, no direct
  data) -> the 'expand' insertion (natural height 0.8 x) is not physically possible for the hard core; it is a numerical
  convenience. Literature: surgeons distract with Caspar pins / trial spacers until a snug fit; final disc-height gain >= 2 mm
  (over-distraction) raises adjacent-segment ossification and subsidence (Sci Rep 2023, s41598-023-44998-4; Frontiers 2023 FE);
  ACDR practice removes osteophytes and checks parallel endplates (PMC5435629). Open PI / surgeon questions: maximum TRANSIENT
  intraoperative distraction for insertion; whether endplate preparation (anterior lip / osteophyte removal, flattening the
  concavity with curettes) is part of the procedure. Insertion options for evo (PI: any feasible method): (1) transient extra
  distraction, (2) endplate preparation, (3) hard core inside the insertable envelope + compliant PLCL 50:50 parts that compress
  elastically and refill the concavity, (4) rotate-in / oblique paths. Note: the concavity that blocks insertion also blocks
  expulsion (geometric interlock) - a fixation mechanism worth keeping.
- 2026-10-26 Repository split (PI): evo work moved to this repo (history of the moved files kept, data snapshot with hashes,
  private GitHub repo). Paths: human_study/evo -> work/ + docs/ + results/, scripts/7_evo -> gpufe/, methods/, roles/.
- 2026-10-26 PI (insertion): maximum TRANSIENT intraoperative distraction: follow current surgical guidelines / surgeon
  teaching (analyst to research); endplate preparation: NO bone removal or shaping, soft-tissue clearing only -> the endplate
  concavity stays; insertion must work with the concavity (hard core inside the insertable envelope, compliant parts allowed).
- 2026-10-26 transient distraction (analyst, literature; no explicit mm limit exists): Mobi-C technique - trial heights start at
  the smallest and must not exceed the height of the healthy adjacent discs (4.5 mm size added to avoid facet over-distraction);
  Bryan technique - minimise pin distraction, prefer intradiscal distraction (PMC6132602); over-distraction >= 2 mm of final
  disc-height gain is harmful (Sci Rep 2023); a distraction-force study suggests <= 6 kgf cm. DEFAULT until the PI / surgeon
  confirms: total intraoperative disc-height gain (transient, for insertion) <= 2 mm over native, final d 0.5-1.5 mm;
  hard PLCL strain during insertion <= 3 %, compliant PLCL 50:50 <= 40 %. With no bone shaping, a contour-matched dome needs
  +2.35 mm beyond d -> it must be compliant, or the hard core must stay inside the insertable envelope. Open: surgeon
  confirmation (Haertl team) of the transient limit.
- 2026-10-26 PI: the model snapshot (snapshot/model, snapshot/reference, ~52 MB) is committed to the repository.
- 2026-10-26 PI: unattended operation. ~/.jupyter/jupyter_server_config.py runs ops/resume_all.sh at every server start (PI-authorised); ops/activity_keepalive.py reports real background work (FEBio running, queued jobs, GPU solver or agent round) as Jupyter activity every 10 min so the idle culler does not stop a computing server, and stops reporting when no work is left (PI-authorised, permission rule added by the PI; log work/agents/keepalive.log). Recommended: inform the server admin.
- 2026-10-27 PI (after round 2):
  (1) Slip-out is judged by calculation first: from the fixed (tied) cage, the force the interface must carry vs what friction
      can give, i.e. the minimum friction coefficient needed (mu_req, limit-surface method e02); the full frictional
      simulation is only the check of that shortcut on selected designs. Where a frictional reference is needed, the law
      (no slip below the friction limit) is the reference, not FEBio (FEBio re-anchors stick points every increment:
      FESlidingElasticInterface::Update projects before InitSlidingSurface; verifier round 2, confirmed in the source).
      e02 must handle curved contact faces (red team round 2: flat assumption under-estimates mu_req up to 7.5x).
  (2) Posterior push-out 135 N kept (origin: safety guard round 1, Moroney 1988 maximum cervical AP shear). Expand-after-
      insertion / latch structures are allowed, but the safety guard must verify them carefully.
  (3) Safety guard insertion rules accepted: hard core passes the narrowest anterior gap without compression (stress based,
      no permanent set), soft material compression <= 30 %, posterior checks at mu 0.2, transient distraction 2 mm
      (1.5-2.5 sensitivity) pending surgeon confirmation.
  (4) Slip-out also judged by the displacement of the most posterior cage point (toward the cord), not only the centre.
  (5) Friction experiments come later; simulate as realistically as possible meanwhile (mu 0.3 main, 0.2 / 0.45).
  (6) All role tool permissions opened (roles/run_roles.sh): roles are independent processes that each push one goal to the
      limit and supervise each other; no single agent plays several roles.
  (7) Focus: short-term safe non-slip-out first. Fatigue, insertion depth stop, soft debris / delamination and 16-week
      degradation are recorded as later checks, applied once a suitable prototype exists.
- 2026-10-27 PI (definition of slip-out): slip-out means dislocation, i.e. the cage as a whole moving radially out of the disc
  space. Being squashed a little, local deformation or local micro-slip at part of the contact face are acceptable as long
  as the cage as a whole does not dislocate. Implementation: (a) dislocation = the rigid-body part of the cage motion (best-fit
  rigid motion of all cage nodes, relative to C3 and C4), its radial outward component (from the disc-space centre); limits
  1 mm any direction, 0.5 mm posterior; (b) elastic shape change is excluded from (a); a posterior bulge of soft material
  is a nerve-safety check of its own (no cage material inside the canal clearance zone), not slip-out; (c) the friction
  shortcut uses the whole-face limit (mu_req: the least mu at which the whole cage face can hold the load as one body), so
  local partial slip does not count as failure. Supersedes (4) of the entry above ("most posterior point displacement").
- 2026-10-28 PI: a FOREMAN agent for resources, speed, scheduling and restart resilience. Implementation: ops/task_runner.py
  (deterministic, every 5 min from ops/evo_daemon.sh: task queue work/ops/tasks/, starts tasks in tmux on a GPU with free
  memory and within the cgroup memory headroom, re-queues tasks lost in a restart) + roles/run_foreman.sh (independent
  headless Claude, every 60 min (PI 2026-10-28: changed from 30), prompt roles/prompts/foreman.md: inventory, health, utilisation tuning of scheduling
  only, restart coverage, report work/agents/foreman/status.json with summary_zh). It may not change science, invent
  scientific tasks, touch other users' processes, bypass the FEBio preflight, or commit / push.
- 2026-10-28 integrator: GPU Newton absolute convergence floor res_abs = 0.05 N (total out-of-balance force) added, with FEBio's energy line search (FELineSearch.cpp) transcribed, a C1
  rounding of the contact penalty (0.005 mm) and FEBio's augmented Lagrangian for laugon contacts; near facet contact the
  model has a very soft mode where FEBio's displacement norm stalls at residuals of 1e-3 - 3e-2 N; adequacy of 0.05 N is
  judged by the gate 2 rotations vs FEBio; increments
  that start almost in equilibrium stalled FEBio's relative norms (gate 2, facet contact onset).
- 2026-10-28 PI: physio / ROM loading for the frictional and gate runs: rotation control of the C3 rigid body about the main
  axis (other dofs free) until the reaction moment reaches the target (1.5 N m), instead of applying the moment directly;
  same equilibrium end state, a path that does not jump in the soft neutral zone (both FEBio and the GPU solver stall at
  facet contact onset under moment control: 135 / 148 physio_v3 runs stalled in extension).
- 2026-10-28 integrator proposal to the PI (pending): answer slip-out for lateral bending / axial rotation first with the
  limit-surface slip mode (Goyal, Ruina & Papadopoulos 1991) on the existing tied results: instantaneous centre of the slip
  motion, spin- vs translation-dominated, bounded slip angle from the segment torsional stiffness, resulting outward
  displacement of the farthest cage point vs 1 mm / 0.5 mm; frictional runs only to check a few designs.
- 2026-10-31 review day (integrator, inline after the agent workflow hit the usage limit). Evo-infrastructure audit (agent,
  14 findings): gate 2 fails 5/6 directions and has not run since 10-28 (VERIFICATION.md stale); no designer / constraints /
  design space / archive / engine exist; l2_febio h14 copy stale; HOLD not enforced in evo_daemon; 29 findings unanswered,
  no CR register; task_runner and roles may use other users' GPUs (config gpu 5); foreman edit truncated OLD h19 on the full
  disk. Proposals written for the PI: docs/DESIGNER_KICKOFF.md (readiness, designer prompt draft roles/prompts/designer.md,
  schema, engine MVP on the FEBio-L2 path, round-0 seeds, ~100-140 h before round 1), docs/RISKS.md, docs/IDEAS_ARCHITECTURE.md,
  paper/LITERATURE.md (5 topics, verification flags), paper/ABSTRACT_OUTLINE.md, paper/figures/F1-F7. ops/collect_split.py
  rewritten to aggregate from all per-run files (see OLD DECISIONS 2026-10-31 10:40). Merged verdicts 62/62/24.
  Pending PI: fitness definition (e04 vs e03), verdict rule for follower-load inversions, S8, designer start.
- 2026-11-04 PI (design gates after the tied screening, applied in ops/collect_split.py): (1) gate 4 dislocation under real
  friction judged at the intact-ROM state (1 mm any / 0.5 mm posterior), no pass by absence - both flexion and extension must
  reach an evaluation point (ops/fric_compare.py); (2) S10 interface shear <= 3 MPa, soft-side p99 at the ROM state,
  PROVISIONAL pending a bond-strength test (ops/e07_batch.py -> results/method/fric/e07_verdicts.json); (3) radial-gradient
  mixing-nozzle designs (A and B) excluded at design level; old-repo sampler h22 no longer proposes them.
  Result: of the 71 tied passes, 0 pass all gates - 26 dislocation-friction, 15 interface-shear (every axial design: flexion
  10-14 MPa), 13 radial-mix-excluded, 14 radial-interleave friction-computability (pending the c3_release_ramp pilot), 3
  friction-window (flexion did not reach ROM). Trade-off seen: whole-layer soft pads (axial) hold (0.50-0.64 mm) but load the
  layer interface; hard-rich interleave faces keep the interface at 1.7-2.7 MPa but slide ~1 mm.
  Lesson for the free-form designer (not a constraint, the PI excluded a design class, not a voxel pattern): soft voxels in
  bands on the endplate contact face, interleaved with hard voxels, are the pattern that failed both gates; any free-form
  design with mixed phi on the contact face must be checked against S9 and S10 under real friction.
- 2026-11-04 11:30 correction: e07 first version used the mesh flag 'hard' (interleave pattern only) as the interface for every
  design, so all mix-design interface values in the entry above were on faces that are no material boundary. Fixed (FEBio block
  = material), rerun. Corrected classes of the 71 tied passes: dislocation-friction 26, interface-shear 17, radial-mix 13,
  friction-computability 15. Corrected metric does NOT pass the mesh tolerance (HZ 0.1: layer -15.9 %, band +16.7 %). Flexion
  at the intact ROM needs 1.9-6.1 N m (target 1.5), see old-repo DECISIONS 2026-11-04 11:30; evaluation point goes back to the PI.
- 2026-11-04 13:50 merged classes after duplicate pooling (supersedes the counts above): tied passes 72 (p059 = p074 added,
  inherits pooled evidence). dislocation-friction 28, interface-shear-provisional 16, radial-mix-excluded 14,
  friction-computability 14 (radial interleave). 0 pass all gates. Evaluation point and 3 MPa threshold unchanged, PI pending.

## 2026-11-05 04:10 — PI decisions applied (see biocage_simulation_test_oct2026/human_study/DECISIONS.md 04:10)
- Evaluation point (PI item 1 = 04:30 wording): 1.5 N m state when transmitted, else intact ROM (fric_compare, eval_point per window).
  Gate 4: 14 fail / 24 pass / 33 open (was 26 / 14 / 31; open = 27 insertion stops + 6 window-level). Radial-mix exclusion first (collect_split, PI item 2).
- Merged classes: radial-mix-excluded 28, dislocation-friction 17, interface-shear-provisional 14, friction-computability 14; PASS 0; tied passes 72.
- All friction verdicts provisional (R03 superseded; NUM-16 / NUM-17; density reference -> physio_fric4 at 1e-9, item 8).

## 2026-11-07 — PI decision 1: slip-out verdict = mu_req (tied screening); the real-friction run is a check, not a gate
Implemented 2026-11-08 in ops/collect_split.py (see ../biocage_simulation_test_oct2026/human_study/DECISIONS.md 2026-11-07 13:00 and 2026-11-08 01:40). Recomputed classes: PASS 13, friction-check-exceeded 13 (recorded, provisional), interface-shear-provisional 18, radial-mix-excluded 28, friction-computability 14. The former DESIGN/dislocation-friction class (17) no longer exists.

## 2026-11-09 18:10 physio_fric5 set complete - precedence applied
- 43 designs / 86 windows of physio_fric5 (stick-memory reference law) finished; fric_compare / e07_batch / collect_split / mu_req_field rerun with fric5 superseding fric3 per window. fric verdicts pass 35 / fail 6 / open 30 (was 24/14/33); e07 fail 28 / pass 10 / open 5; collect_split PASS 13, friction-check-exceeded 7 (p051 p060 p072 p075 p093 p114 p145). 5 fric5 windows unusable (solver error before the read-out state: p036 p132 p142 p148 flexion, p100 extension) -> those designs open until rerun. Details: old repo human_study/DECISIONS.md 2026-11-09 18:10.
- 18:50: results/method/mu_req_vs_fric5.{json,csv} (shortcut vs gold standard, Spearman 0.90, rms 0.032 mm, 0.5 mm boundary at mu_req 0.140) and results/method/fric/e07_fric3_vs_fric5_shear.json (law raises p99 interface shear at ROM by a median 6 %). Details in the old repo DECISIONS 2026-11-09 18:50.

## 2026-11-10 14:4x PI decisions applied (grey zone, fallback, soft-face locking, provenance, tolerance; set physio_relG)
- verdicts pass 27 / grey 16 / fail 0 / open 28; collect_split PASS 0, GREY/friction-posterior-0.45-0.55 13, friction-check-exceeded 0. Details: old repo DECISIONS 2026-11-10 14:3x-14:4x.

## 2026-11-11 00:21 process-G batch final; fric_compare rules changed (no first-increment veto, per-source fallback margin, both-laws not-computable class, replicates); collect_split class renamed
- physio_relG 27/27 done; physio_relG_pl 26 production-law windows (19 + 7 extra). Replicate finding: p050 / p068 / p084 / p127 are one deck (sha 500c814ead46...) with verdicts open / pass / open / open -> the first-increment window failure is run-to-run variability (old repo DECISIONS 2026-11-11 00:16).
- ops/fric_compare.py: FALLBACK_MARGIN per source {physio_fric3 0.0431, physio_relG_pl 0.0581 (max rule, relG_law_shift.json n 4)}; folded_early veto removed (p036 flexion -> fallback pass); soft_face_locking (key kept) only when both laws stopped before an evaluation point, evidence text neutral, first_increment_pattern noted; `replicates` per design. ops/collect_split.py: DESIGN/soft-face-locking -> DESIGN/not-computable-both-laws. ops/mu_req_field.py: replicates column. ops/law_shift.py unchanged.
- Verdicts: pass 44 / grey 17 / open 10 (71 designs); collect_split classes: PASS 1, GREY/friction-posterior-0.45-0.55 13, interface-shear-provisional 22, radial-mix-excluded 28, friction-computability 0, [多元]/computability 2, [數值]/unstable-window 2, [觀測]/friction-window 7, DESIGN/not-computable-both-laws 2, friction-check-exceeded 0. e07 shear unchanged (open 22 / fail 37 / pass 11). mu_req_field 149 rows rewritten.
- Foreman items: relGpl_handoff.sh (22:02, workers 2 -> 5), febio_pin.sh (tmux febio_pin, NUMA re-pin once per run) kept; h51 now logs the FEBio normal flag; NUMA-aware core pick in h06/h18/h47 still a request.

## 2026-11-13 13:52 route-E re-run final: verdicts pass 52 / grey 13 / open 4 / fail 2; classes interface-shear-provisional 28, radial-mix-excluded 28, friction-computability 0, friction-check-exceeded 2, PASS 5, GREY 8; e07 pass 12 / fail 53 / open 5; replicate agreement 12/14 within 0.005 mm. Details: old repo DECISIONS 2026-11-13 13:52.

## 2026-11-17 04:4x PI boundary-grey rule (p093 / p145 fail -> grey): verdicts pass 52 / grey 15 / open 4 / fail 0 (71); classes interface-shear-provisional 28, radial-mix-excluded 28, friction-computability 0, friction-check-exceeded 0, GREY 10, PASS 3.

- 2026-11-17 08:00 (old repo DECISIONS): p102 / p149 complete; 73 designs 摩擦判定 pass 53 / 灰區 grey 16 / fail 0 / open 4（73 設計）. Class counts for R5: interface-shear-provisional 28, radial-mix-excluded 28, friction-computability 0, friction-check-exceeded 0, GREY 10, PASS 3.

- 2026-11-18 04:07 (old repo DECISIONS): PI 2026-11-18 shear 3 MPa = flag + ranking; class interface-shear-provisional retired. Class counts for R5: interface-shear 54 (flagged), radial-mix-excluded 28, friction-computability 0, friction-check-exceeded 0, GREY 12, PASS 31.

## 2026-11-18 04:42 PI second message on round 2 (docs/ROUND2_ARCHITECTURE.md rev 2)
PI instructions recorded (not open questions): (1) surrogate validation at a fixed nominal coverage of 90 %, reporting empirical coverage, interval width, MAE / RMSE, per family and for new geometry regions; validation grouped by design (no replicate on both sides); (2) part B: naive ideas must be distinct physical mechanisms, a senior role writes falsifiable experiments, the mentor may repair but must keep the mechanism and may not filter by taste, a Design Grammar + Geometry Compiler turn specifications into models, and build success / design distance / physics are decided by programs only; (3) part C also searches for new meaningful design parameters and hands them to A (out-of-distribution prediction for new topologies), following recent literature; (4) the formal evaluation must prove that the AI ideas increase effective exploration; (5) standing rule: when blocked, search the literature first; (6) Hugging Face repository ast-atp/biocage_evo to be added.
Implementation choices, 依 2026-11-13 授權自行決定: group key = launched deck hash (fallback gene tuple + family), leave-one-group-out + leave-one-family-out; steering rule = empirical coverage 0.80-0.95 at nominal 90 % AND skill >= 0.2 vs the family-mean baseline AND interval narrower than the training spread; cross-conformal recalibration before falling back to exploration-only; OOD label by nearest-neighbour descriptor distance; naive = 10 separate small-model processes in an empty directory with analogy cues; blind mechanism tagger, <= 2 ideas per tag, tag compared before / after the mentor; mentor rejections must cite S1-S10 or a compiler error; 1 mentor-rejected idea compiled per round (audit lane); compiler refuses repairs > 2 % of solid voxels; grammar escape hatch custom_field; tied-screening outputs as surrogate inputs; new QA checks R23-R25 proposed; y3 shear removed from P(pass) (flag since 2026-11-18).
Checked: h14 reads the per-element material map from the cage npz (h14_build_case.py line 134); h12 generates only footprint-minus-window columns -> the Geometry Compiler is the missing generator (2-3 days). Hugging Face: ast-atp/biocage_evo is a PUBLIC, empty model repository; this server has no client, token or registered SSH key -> registered in config.json, nothing uploaded.
Waiting for the PI: acquisition weights, batch size, mentor outside the existing families, control arm (random draws from the grammar, 5 designs = 5-15 GPU-h per round), Hugging Face content / visibility / credentials. No code in ops/ written and nothing launched in this step.

## 2026-11-18 04:58 PI decisions on round 2 (answers to the five pending items)
1. Acquisition weight: biodisc space is not considered for now (PI: 「目前先不管，隨意」) -> the utility in A5 is the fixation margin only (weight 100 : 0). Reading recorded as mine: this drops the void fraction as an OBJECTIVE; rule S4 (void >= 50 %, connected to both endplates) is a constraint owned by the safety guard and stays until the PI says otherwise.
2. Batch per round as recommended: A 20 (4 exploration + 2 replicates inside) + B 5 (+ 5 ablation twins, tied screening only) + control R 5 + 1 audit-lane design.
3. The mentor may leave the existing families; at least 2 of the <= 5 kept ideas beyond the archive-distance floor; Geometry Compiler to be built.
4. Control arm R (random draws from the Design Grammar, no LLM) approved, 5 designs per round.
5. Hugging Face: ast-atp is the PI's account, biocage_evo the repository the PI created; its contributors must show no trace of AI or Claude (same rule as the GitHub commits: uploads under the PI's identity only, no co-author trailer, no AI attribution in commit messages or the repository card). Still open: credentials on this server, what to upload, public or private.

## 2026-11-18 05:11 surrogate validation gate, first run [SUPERSEDED by the 2026-11-18 05:21 entry: the flexion target was mislabelled; file kept as validation_2026-11-18_run1_superseded.json]
CPU only, read-only on verdicts / labels. 137 rows with genes (12 rows without genes or mesh excluded), 120 groups (genes + family, replicate lists, launched deck hashes); no group spans train and test (asserted). Model specification fixed before the run; all 19 variants listed in the file. Nominal coverage 90 %.
| target | n rows / groups | empirical coverage (+-2 SE) | median interval width | MAE | RMSE (family-mean baseline) | skill | cross-conformal coverage / width | steer |
|---|---|---|---|---|---|---|---|---|
| posterior translation, flexion at 1.5 N m (mm) | 70 / 58 | 0.89 (+-0.08) | 0.217 | 0.052 | 0.081 (0.190) | +0.57 | 0.90 / 0.261 | yes |
| posterior translation, extension at ROM (mm) | 72 / 59 | 0.81 (+-0.08) | 0.055 | 0.017 | 0.026 (0.103) | +0.74 | 0.89 / 0.098 | yes (lower edge) |
| mu_req_max (15 lower-bound rows excluded) | 79 / 64 | 0.82 (+-0.07) | 0.007 | 0.003 | 0.004 (0.020) | +0.80 | 0.89 / 0.012 | yes |
| shear_req_p99 (MPa) | 71 / 59 | 0.86 (+-0.08) | 4.1 | 2.46 | 4.49 (2.87) | -0.56 | 0.90 / 6.9 | NO: exploration only |
Input set G (genes + family one-hot) shown; D (genes + 12 geometric descriptors, no family label) is equal within noise (flexion skill +0.60, coverage 0.86; mu_req coverage 0.77 -> conformal 0.90). Tied mu_req as an extra input adds nothing inside the families (flexion skill +0.54 vs +0.57) - expected, the mesh is fixed by family + d.
Per family (leave-one-group-out, G): radial_interleave is under-covered (flexion 0.72, extension 0.73, n 25-26); axial_mix 0.94; radial_mix 1.00 / 0.81; axial_interleave n 2 (no number).
Leave-one-FAMILY-out (D; only 3 usable folds, weak evidence): flexion coverage 0.47, skill -0.07 (radial families 0.24-0.28) -> NOT predictable for an unseen family; extension coverage 0.85, skill +0.30; mu_req coverage 0.82, skill +0.49; shear fails.
Classifier 'tied gate passed' (75 of 137): grouped Brier 0.066 vs family-rate 0.075 vs base-rate 0.253 -> the family label already carries it. Not-computable: 4 positives, cannot be validated.
Decisions, 依 2026-11-13 授權自行決定: (1) intervals used for steering are the cross-conformal ones (pre-declared fallback; Gaussian coverage sits at the lower edge for extension and mu_req); (2) the surrogate steers flexion / extension translation and mu_req INSIDE the existing families only; (3) shear is exploration-only (it is a flag, not a gate); (4) any design of a new family / topology is OOD: never promoted or rejected by the surrogate (the flexion leave-one-family-out result is the evidence), simulated through the exploration quota and part B; (5) the flexion interval (+-0.11 to 0.13 mm) is wider than the grey band (0.10 mm), so near the 0.45 mm limit only the simulation decides. Not done: R23 check in h37, ops/propose_round.py.

## 2026-11-18 05:21 surrogate validation gate, corrected run [numbers SUPERSEDED by the 2026-11-18 05:53 audit-fix run; file kept as validation_2026-11-18_run2_preaudit.json]
Correction: the first run fitted |posterior| in both windows. fric_compare judges the SIGNED posterior (0.45 / 0.55 mm) and the any-direction translation u_h (1 mm). In flexion all 70 signed posterior values are negative (the cage moves anteriorly), so the posterior limit acts only in extension. Targets now: post_ext (signed posterior, extension at the intact ROM) and uh_flex (u_h, flexion at 1.5 N m). Target-definition fix, not tuning; first-run files kept with the suffix _run1_superseded.
CPU only, read-only on verdicts / labels. 137 rows with genes (12 without genes or mesh excluded), 120 groups (genes + family, replicate lists, launched deck hashes), no group on both sides (asserted). Specification fixed before the first run; 20 variants in the file, of which DT (descriptors + tied mu_req) is post-hoc. Nominal coverage 90 %. Input set G (genes + family one-hot), leave-one-group-out:
| target | rows / groups | empirical coverage (+-2 SE) | median interval width | MAE | RMSE (family-mean baseline) | skill | cross-conformal coverage / width | steer |
|---|---|---|---|---|---|---|---|---|
| post_ext: posterior translation, extension (mm; limits 0.45 / 0.55) | 72 / 59 | 0.81 (+-0.08) | 0.055 | 0.017 | 0.026 (0.103) | +0.74 | 0.89 / 0.098 | yes with conformal intervals |
| uh_flex: any-direction translation, flexion (mm; limit 1.0) | 70 / 58 | 0.87 (+-0.08) | 0.206 | 0.053 | 0.080 (0.190) | +0.58 | 0.90 / 0.263 | yes |
| mu_req_max (15 lower-bound rows excluded) | 79 / 64 | 0.82 (+-0.07) | 0.007 | 0.003 | 0.004 (0.020) | +0.80 | 0.89 / 0.012 | yes with conformal intervals |
| shear_req_p99 (MPa) | 71 / 59 | 0.86 (+-0.08) | 4.1 | 2.46 | 4.49 (2.87) | -0.56 | 0.90 / 6.9 | NO: exploration only |
Descriptors instead of the family label (D): equal within noise (post_ext skill +0.73, uh_flex +0.60, mu_req +0.78 with Gaussian coverage 0.77 -> conformal 0.90).
Per family (G; Gaussian / conformal coverage): radial_interleave is UNDER-covered beyond sampling noise (2 SE about 0.12 at n 25-27): post_ext 0.73 / 0.85, uh_flex 0.72 / 0.80, mu_req 0.70 / 0.70. axial_mix 0.94 / 1.00, 0.89 / 0.89, 0.78 / 1.00; radial_mix 0.81 / 0.85, 1.00 / 1.00, 0.96 / 0.96; axial_interleave and both_* too few rows for a number. radial_interleave is the family that holds PASS 15 / GREY 10, and radial_mix is an excluded class (28), so the pooled 'pass' overstates what the surrogate knows where it matters.
Leave-one-FAMILY-out (D; 4-5 folds, weak evidence, no error bar; the conformal figures there are in-sample and not a guarantee): post_ext coverage 0.85, skill +0.30 (radial_mix fold 0.62); uh_flex coverage 0.43, skill +0.02 (radial folds 0.16-0.24): NOT predictable for an unseen family; mu_req coverage 0.82, skill +0.49 (axial_interleave fold 0.00, n 5); shear fails.
C6 (b) test, post-hoc: adding the tied mu_req of the window to the descriptors (DT) does not rescue the unseen-family case (post_ext skill +0.33 but coverage 0.65; uh_flex skill -0.07, coverage 0.47), and adds nothing inside the families. The 'cheap-physics input' idea of C6 is therefore unproven on today's data; C6 must find other features.
Limits: void_frac and contact_area are identical in all 90 meshes (0.597, 37.44 mm2), so any design with a different window is out of distribution by construction. y5 ('not in a compression class', 75 of 137; counts radial-mix-excluded and not-computable as 1): grouped Brier 0.066 vs family-rate 0.075 vs base-rate 0.253 - the family label already carries it. Not-computable: 4 positives, cannot be validated. Fitted noise: post_ext 0.015 mm (replicate spread 0.012 mm), uh_flex 0.004 mm.
Decisions, 依 2026-11-13 授權自行決定 (replace the list of the superseded entry): (1) steering intervals = cross-conformal (pre-declared fallback); (2) the surrogate may steer post_ext, uh_flex and mu_req only inside families with data, and radial_interleave proposals carry the 'under-covered' flag (their share of pure-exploration picks is doubled); (3) shear exploration-only; (4) new family / topology / window size = OOD: never promoted or rejected by the surrogate; (5) the post_ext conformal interval (+-0.05 mm) is as wide as the grey band (0.10 mm): close to 0.45 mm only the simulation decides. Not done: h37 R23, ops/propose_round.py (waits for the layer-B audit).

## 2026-11-18 05:31 PI correction: biodisc space is kept
PI: 「更正：空間還是保留」 (withdraws 「目前先不管」 of 04:58 item 1). Recorded: rule S4 (void >= 50 %, connected to both endplates) stays in force everywhere, including the Design Grammar rule checks and the naive task text. My reading of the weighting, to be confirmed only if the PI objects: with 「先不管」 withdrawn, the acquisition utility returns to the recommended fixation margin 70 : biodisc space 30 (every existing design has void 0.597, so the weight does not change arm A today). Hugging Face: the PI sent the clone / push procedure (git-xet, SSH); state in the next entry.

## 2026-11-18 05:32 Hugging Face set-up (PI sent the procedure: git xet install, git clone git@hf.co:ast-atp/biocage_evo, SSH key, git push)
Done: git-xet 0.2.1 (official release binary of huggingface/xet-core; no sudo on this server, so it is in ~/.local/bin instead of /usr/local/bin); clone at ../biocage_evo_hf (link biocage_home/links/evo_hf); git-lfs and git-xet registered with --local for that clone only (the global ~/.gitconfig is untouched); commit identity of the clone = the identity of the repository's own initial commit, Yi Liu <ast-atp@users.noreply.huggingface.co> (no AI / Claude trace). Not done: push - hf.co still answers "anonymous" for this server's key (SHA256:Hb1Awwwzbcwf/zbl2kU1qOoUyTzzogYsJnoHAG0I3BE, ~/.ssh/id_rsa.pub) and a dry-run push is refused; the PI has to add the public key at huggingface.co/settings/keys. Nothing committed in the clone yet; first content waits for the layer-B audit of the surrogate numbers and the PI's word on public vs private.

## 2026-11-18 05:53 surrogate validation gate, run 3 after the layer-B audit (QA_AUDIT_2026-11-18: 3 不符 + 5 sign-off items)
Audit result: grouping, in-fold fitting, targets vs fric_compare, separation from verdicts / labels and the 05:21 table all confirmed; three statements wrong, fixed here.
- D-20261118-27: the 12 rows were NOT without genes; mu_req_field.csv leaves them blank because they have no source run. surrogate_fit.py now reads genes and mesh from al_v2/cases/pNNN_*_params.json (mu_req_field.py, a gate file, untouched). Of the 12, 8 are design-B cages and 4 design-A (p053 p055 p057 p058) [corrected after the re-check]; the family label carries the design letter. y5 now 149 rows / 77 positives, y4 6 positives (p003 p023 p027 p048 p053 p115).
- D-20261118-28: void and contact area are NOT identical in all meshes: 77 design-A meshes 0.597 / 37.44 mm2, 24 design-B meshes 0.645 / 22.55 mm2 (149 rows, 101 meshes; 23 of the 24 design-B designs are compression-sustained, p023 is [多元]/computability) [counts corrected after the re-check: 73 / 16 were the counts before the 12 rows were added]. The regression rows are all design A. Arm A's candidate pool = design-A families (ROUND2 rev 3), so the space weight does not act today.
- D-20261118-31: ROUND2_ARCHITECTURE.md lines corrected (y1 = post_ext + uh_flex, P(pass), no model pickle, decided items, Hugging Face).
- D-20261118-36 (授權自行決定): inherited copies dropped (the run is p068's; p050 and p084 inherit it; one row is kept, under the name p050, same genes and values); conformal quantile by conservative rank; coverage also per group; rows read under another friction law counted (post_ext: p060 p095 p104; uh_flex: p148), kept; 7 incomplete shear read-outs counted.
- D-20261118-35 (授權自行決定): pooled conformal coverage is near 0.90 by construction, so steering rests on skill >= 0.2, interval narrower than the training spread, and the per-family group-level flag (under_covered = conformal coverage below 0.90 - 2 SE). Leave-one-family-out cells carry no steer flag.
Input set G (genes + family one-hot), leave-one-group-out, nominal 90 %:
| target | rows / groups | Gaussian coverage (by group) | conformal coverage / median width | MAE | RMSE (family-mean baseline) | skill | steer |
|---|---|---|---|---|---|---|---|
| post_ext: posterior translation, extension (mm; limits 0.45 / 0.55) | 70 / 59 | 0.84 (0.87) | 0.91 / 0.098 | 0.019 | 0.034 (0.100) | +0.66 | yes |
| uh_flex: any-direction translation, flexion (mm; limit 1.0) | 68 / 58 | 0.87 (0.85) | 0.91 / 0.249 | 0.051 | 0.073 (0.191) | +0.62 | yes; radial_interleave under-covered |
| mu_req_max (15 lower-bound rows excluded) | 79 / 64 | 0.82 (0.83) | 0.91 / 0.013 | 0.003 | 0.004 (0.020) | +0.79 | yes; radial_interleave under-covered |
| shear_req_p99 (MPa) | 71 / 59 | 0.90 | 0.90 / 7.4 | 2.36 | 4.44 (2.87) | -0.55 | NO: exploration only |
Per family at group level (Gaussian / conformal coverage, 2 SE 0.13-0.15): post_ext axial_mix 0.94 / 1.00 (17 groups), radial_interleave 0.86 / 0.94 (18), radial_mix 0.82 / 0.84 (22) - none under-covered (this corrects 05:21, which counted replicate rows as independent); uh_flex radial_interleave 0.61 / 0.72 (18) UNDER, axial_mix 0.88 / 0.94, radial_mix 1.00 / 1.00; mu_req radial_interleave 0.68 / 0.74 (19) UNDER, axial_mix 0.82 / 1.00, radial_mix 0.95 / 1.00, axial_interleave 0.80 / 1.00 (5).
Descriptors instead of the family label (D): post_ext skill +0.73, uh_flex +0.60, mu_req +0.78. Leave-one-family-out (D; 4-5 folds, no error bar): post_ext coverage 0.84, skill +0.28; uh_flex 0.48, -0.07; mu_req 0.82, +0.49; with the tied input (DT, post-hoc) post_ext coverage 0.64, skill +0.30; uh_flex 0.48, -0.07. Unchanged conclusions: an unseen family is not predictable for flexion and the tied input does not rescue it.
y5 ('not in a compression class', 77 of 149): grouped Brier 0.050 vs family-rate 0.048 vs base-rate 0.254 - no better than the family rate, so P(y5) = family rate. Near the limit (audit D-20261118-23): of the 17 rows with posterior >= 0.45 mm 12 (0.71) were inside the Gaussian interval in run 3 (0.59 in run 2), and for p102 (actual 0.458 mm) the predicted mean is 0.320 mm, on the wrong side of the limit; close to 0.45 mm only the simulation decides.
Decisions (replace the 05:21 list): (1) steering intervals = cross-conformal; (2) the surrogate may steer post_ext, uh_flex and mu_req inside design-A families with data; radial_interleave proposals carry the under-covered flag for uh_flex and mu_req and get a doubled share of pure-exploration picks; (3) shear, y4 and y5 are not steered by a model (exploration / family rate); (4) new family / topology / window size = OOD, never promoted or rejected by the surrogate; (5) near 0.45 mm only the simulation decides. Open for the PI: the weight 70 : 30 is my reading of 「空間還是保留」, no written source (audit D-20261118-30).
PI 2026-11-18 (during this run): SSH key registered (hf.co now answers ast-atp); content: any, repository private first. The repository is still public, so nothing is pushed yet.
- 2026-11-18 05:54 Hugging Face: first commit prepared locally in ../biocage_evo_hf (80212f0, author and committer Yi Liu <ast-atp@users.noreply.huggingface.co>, no trailer): README, data/mu_req_field.csv, data/fric_verdicts.json, surrogate/ (descriptors.py, surrogate_fit.py, validation and held-out predictions of run 3). docs/ left out of the first push (internal operating notes). Not pushed: PI said private first and the repository is still public; a background check waits for the visibility change.

## 2026-11-18 05:58 PI: Hugging Face repository stays public; first push done
PI 「保持公開」 (replaces 「先私人」 of 05:5x; content: any). Pushed 80212f0 to hf.co:ast-atp/biocage_evo main (author and committer Yi Liu <ast-atp@users.noreply.huggingface.co>, no trailer): README.md, data/mu_req_field.csv, data/fric_verdicts.json, surrogate/descriptors.py, surrogate/surrogate_fit.py, surrogate/validation_2026-11-18.json, surrogate/loo_predictions_2026-11-18.csv. Verified on the hub API (sha 80212f0, 8 files). docs/ not pushed (internal operating notes). Re-check of the audit: D-20261118-27 cleared; the remaining counts / sentences of D-28 and D-31 corrected in the 05:53 entry and ROUND2_ARCHITECTURE.md (77 design-A / 24 design-B meshes, 8 + 4 of the 12 rows, 23 of 24, R23 wording, control arm approved, near-limit coverage 12 of 17).

## 2026-11-18 06:02 PI decision: acquisition weight 80 : 20
PI: 「採樣權重 80：20」 = utility 0.8 x fixation-margin score + 0.2 x biodisc-space score (both scores scaled 0-1 over the candidate pool; S4 void >= 50 % stays a hard constraint). Replaces my 70 : 30 reading (audit D-20261118-30 open item closed). No effect on arm A today (all design-A candidates have void 0.597); it acts once designs with other window sizes exist. Also: second re-check of QA_AUDIT_2026-11-18 passed (register 327 items, 不符 0; h37 overall WARN from R20 and the pilot_holdQR settings change of another session).

## 2026-11-18 11:08 PI decisions A1-A7 (topic list of PI_PENDING_DECISIONS.md): all as recommended
PI: 「A1–A7：都照建議」. A1 commit and push today's round-2 files (evo) and the unpushed commits of both repositories; A2 architecture and plan documents go to Hugging Face after the internal operating notes are removed; A3 idle machines: first add samples and replicates for the radial_interleave family (where the estimator is least sure), existing families, no compiler needed; A4 division of work confirmed: this window = round-2 evolution, the other window = platform numerical verification; A5 the release shock after insertion (runs from scratch stop there) is dealt with before round 1; A6 re-score first the capability checks that limit what may be concluded, before round 1; A7 build an automatically generated project status page.
- 2026-11-18 11:09 A1 done: evo 76d5717 and platform d77492c committed and pushed (all unpushed commits of both repositories with them). A2 done: Hugging Face push of docs/PLAN.md and docs/ROUND2_ARCHITECTURE.md as cleaned copies (section G replaced by a one-line data-release note, the contributor-identity sentence removed, 'headless Claude' worded as 'independent headless LLM agents'); the repository copies are unchanged.

## 2026-11-18 11:16 A3 changed after looking at WHERE the estimator misses (no simulation launched); A7 done; A5 / A6 owner
A3 (PI approved "more samples and replicates for radial_interleave"). Before choosing designs the held-out predictions of that family were listed (results/surrogate/loo_predictions_2026-11-18.csv, G / leave-one-group-out):
- The family has only 7 distinct material sets (E_hard, E_soft, theta) reused over distraction values; 27 rows for mu_req, 25 for flexion.
- mu_req: 8 misses, all small (median absolute error 0.0020, largest 0.0108, on values 0.075-0.142) and lined up with WHICH screening pass produced the number (static / slow-dynamic / split windows). Post-hoc test (results/surrogate/posthoc_2026-11-18_mu_req_pass_type.json): with the pass type as an extra input the family's group-level conformal coverage is 0.92 (was 0.74, flag cleared), family MAE 0.0014 (was 0.0025), pooled skill +0.81, conformal width 0.0098. So this was a covariate, not a lack of samples.
- flexion translation: 7 misses, all at d 0.9-1.15 mm in process-G rows, where the translation drops from about 0.86 mm (d 0.9) to 0.10-0.29 mm (d 1.1-1.15) and depends strongly on the material (p101 0.097 vs p039 0.719 mm, both d 1.10). Replicates agree closely there and elsewhere (p082 / p088 0.2608 / 0.2610; p086 / p100 / p142 0.8174 / 0.8185 / 0.8172 mm), so it is model error in a steep transition, not noise.
Consequences, 依 2026-11-13 授權自行決定: (1) no replicate batch (noise is already known to be small); (2) the pass type becomes an input of the mu_req model in ops/propose_round.py (logged as post-hoc; the run-3 validation file is unchanged); (3) the useful new data are radial_interleave designs with NEW material sets at d 0.9-1.2 with friction windows; they need insertion from scratch, i.e. the release-shock item A5 first, and a runner that takes a new design through the screening passes (multi-pass chain h28 / h29 / split passes, median 26 min per first-pass run) - listed as new item B10; (4) these gap-fill designs will be marked 'pre-round gap-fill' and kept out of the arm comparison.
A7 done: scripts/8_audit/h38_project_status.py -> human_study/PROJECT_STATUS.md (platform repo), numbers only from result files with source and time.
A5 (release shock) and A6 (re-scoring the conclusion-limiting capability checks) are platform work: owner = the other window (A4); not started here.
Citations of sections B and C checked against arXiv (2611.11725, 2606.12071, 2609.04303, 2602.12259 exist with the stated content); EvoSci marked not re-verified in both copies.

## 2026-11-18 11:55 round-2 work that does not need the platform (PI: 「其他可以開始做的就先開始，需要等平台被完善的子專案就先等等」)
Done (CPU only, nothing launched; new files only; h12 / h14 untouched):
- B5 Geometry Compiler v0 (ops/geom_compile.py, docs/DESIGN_GRAMMAR.md). Finding: every h12 mesh already holds the full disc-space lattice (2311 columns x K layers, identical for all families at one d), h14 drops void elements and filters the face quads itself, so the compiler only RELABELS region / phi / hard - no meshing. Acceptance (ops/geom_compile_test.py -> results/grammar/acceptance_2026-11-18.json): the six families written in the grammar reproduce 78 of 78 design-A mesh files element for element; L0 checks pass on all. A free-form demo design was built by the unchanged h14 (case.feb written; not run). The 2-3 day estimate is met in one session; verdict-level acceptance waits for simulations.
- B2 ops/propose_round.py, dry run results/round2/dryrun_2026-11-18/proposals.json (status NOT LAUNCHED): 14 steered + 4 exploration + 2 replicates. Post-hoc check first (results/surrogate/posthoc_2026-11-18_leave_material_out.json): leaving out a whole MATERIAL SET (75 sets in 149 rows; 23-24 in the fitted rows) is as good as leaving out a design (post_ext skill +0.69 vs +0.66, uh_flex +0.58 vs +0.62 with a wider interval 0.35 vs 0.25 mm, mu_req +0.81 both), so new material sets inside a family may be steered.
  Findings of the dry run: (i) without a cap all 14 steered picks sat at d 1.45-1.50 mm - what the estimator has learnt inside the families is mostly 'more distraction holds better'; a cap of 2 picks per d value now spreads the batch over d 1.2-1.5 (授權自行決定); (ii) only two design-A families are worth proposing in: radial_interleave (97 % of its designs are not in a compression class) and axial_mix (82 %); axial_interleave 0 %, both_mix 0 %, both_interleave 10 %; radial_mix is the excluded class; (iii) P(pass) is 0.95-0.97 for every steered pick - inside the families the search is nearly settled.
- B4 ops/principles.py -> docs/DESIGN_PRINCIPLES.md, results/principles/features_2026-11-18.json. 27 features (4 genes, 12 geometric descriptors, 11 material x geometry composites: ops/descriptors.py physics_features), list and keep rule declared before scoring. Within-family rank correlations: distraction dominates (post_ext -0.97, uh_flex -0.82, mu_req -0.99); height, posterior / anterior stiffness ratio and stiffness-centre position are collinear with it (same |rho|). Second tier, independent of d: softer soft material and a larger hard / soft contrast go with LESS translation and LESS required friction (soft modulus +0.40 / +0.45, contrast -0.41 / -0.47, column compliance -0.56 / -0.63).
  Composites as estimator inputs (leave-one-family-out RMSE change / leave-one-group-out RMSE change against descriptors): post_ext -51 % / +10 % (unseen-family skill +0.28 -> +0.64, coverage 0.91); mu_req -18 % / +70 %; uh_flex -4 % / +24 %. By the declared rule (>= 10 % better on unseen families AND not more than 5 % worse in-family) NONE is adopted; the post_ext result misses only the second clause. Not re-tuned after the fact: listed as a candidate ('composites for out-of-distribution candidates only') to be declared and tested on the round-1 designs of arm B, which are real new families.
- B7 results/round2/prereg.json (sha256 4359a4f7...): arms, exclusions, frozen baseline (149 designs, 101 meshes, file hashes), distance space and novelty floor 0.907 (largest nearest-neighbour distance in the archive), metrics, tests, detectable gap, card scoring. Note recorded in the file: all 20 random grammar draws are beyond the floor (distances 2.3-11.7), so novelty mainly guards against near-copies and the PRIMARY metric is 'new AND PASS'.
- Control arm sampler ops/grammar_random.py: 20 built of 40 draws (refused: contact over a one-column void 17, void below 50 % 11).
- B6 roles/prompts/naive.md (plain task + S1-S10 in the safety guard's own plain wording, one analogy cue per process, no look-ups), tagger.md, senior.md, mentor.md. No role was run.
- B3 h37 R21 (estimator separation) and R23 (grouped validation newer than its inputs), warning-level, both PASS.
Waiting for the platform (owner: platform window): first-round simulations, the gap-fill batch, verdict-level compiler acceptance - all need insertion from scratch (release shock, A5) and the new-design runner (B10).
For the PI (new discussion items): is the distraction a design variable or a surgical condition (it decides almost everything inside the families); arm A has little left to find inside the two usable families, so the value of round 1 lies mostly in arm B and the control arm.
