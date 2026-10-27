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
