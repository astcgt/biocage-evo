"""Verifier r0003: writes work/board/r0003/verifier.json (checks, gate criteria, change requests) from this file, keeping
gate_reruns / verdict_reason of the draft. V07 numbers are read from v07_summary.json. usage: python v10_write_verdict.py"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); P = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
F = os.path.join(P, 'work/board/r0003/verifier.json')
d = json.load(open(F)); v7 = json.load(open(os.path.join(HERE, 'v07_summary.json')))
d['gate_reruns'][1]['result'] = v7['text']

C = []
def chk(item, result, sev, ev, fix=()):
    C.append(dict(item=item, result=result, severity=sev, evidence=ev, fix_options=list(fix)))

chk('B1 Friction ratcheting: under a CONSTANT tangential load below mu N, the GPU solver keeps sliding and the amount depends on the increment size (confirms red-team F-0015 by simulation; upgrades my round-2 A8 from minor)',
    'problem', 'critical',
    v7['text'] + ' Mechanism (consistent with F-0015, not isolated by a separate run): gpufe/contact.py:114-117 re-anchors every node that slipped in the last increment at its current projection, so its tangential friction force restarts from zero (stick trial t = k (x_anchor - x), contact.py:175-177); the load moves to the neighbours, which then slip, and so on. A Coulomb interface under constant load must not move once equilibrium is reached (rate-independent law; Wriggers 2006, Computational Contact Mechanics, 2nd ed., Springer, ch. 5; Laursen 2002, Computational Contact and Impact Mechanics, Springer, ch. 5). FEBio has the same rule with laugon 0 (FESlidingElasticInterface.cpp:886-905 slip branch, :136 m_rsp = m_rs) and creeps linearly in the increment count (0.151 mm at n 10, 0.301 mm at n 20, same deck). Consequence: the dislocation limit is 0.5 mm posterior (DECISIONS 2026-10-27); an artefact of 0.05-0.12 mm per load hold at 0.9 mu, per window, accumulated over the 6-direction protocol, is of the same order. The PI decision to use the frictional simulation only as a check of mu_req does not remove this: the check itself would be contaminated.',
    ['Return mapping with the elastic tangential offset kept: when a node slips, store the anchor as current projection + (mu p_n / k) * slip direction (a tangential offset vector per node, like tie_off), so the traction stays on the friction cone at the start of the next increment (Wriggers 2006 ch. 5.2; Simo & Laursen 1992, Comput. Struct. 42:97-116)',
     'Alternatively an augmented-Lagrangian tangential multiplier kept across increments (FEBio Lt, laugon 1) - but then FEBio laugon-1 must be gated too',
     'Gate: V07 (force hold at 0.5 and 0.9 mu, E 10 and 400, n 10 / 20 / 40) inside gpufe/ as gate 1e, criteria in proposed_gate_criteria.gate_1e_force_hold'])

chk('B2 New defect from the round-2 line-search rewrite: an increment whose start state is already in equilibrium (any load hold once everything sticks) fails and the run stops with RuntimeError',
    'problem', 'major',
    'gpufe/newton.py:246 accepts a line-search trial only if |g_new| < |g| (strict); at the start of a hold increment |g| ~ 6e-13 N, no step can lower it, the fresh-tangent retry also fails (:249-253, why = line search), run() halves the increment 6 times with the same outcome and raises (:318). The only residual escape, normR1 <= 1e-24 * normRi (:270), is relative to the same tiny start residual, so it cannot fire. Reproduced: work/agents/verifier/v07_r0.5.log (E 10, n 10: converged to stick 1.0 at t 0.725, then RuntimeError at t 0.72539, res 6.2e-13) and v07_r0.9.log (n 40: RuntimeError at t 0.59385, res 5.5e-13). Not a wrong number (it stops loudly), but every hold, cycle, and the creep-canary of gate 5 cannot run. Verifier-side workaround for measurement only: V07_PATCH=1 in v07_stick_creep.py (accepts the increment if it failed by line search with |g| < 1e-9 N). A second failure type appears with the stiff block (E 400, 0.9 mu, n 10, patched): RuntimeError at t 0.6876 after 60 Newton iterations x 7 tries, although the residual is 1.55e-7 N (4e-8 of Fn); the FEBio displacement norm (dtol 1e-6 in the deck) is never met, probably because nodes switch stick / slip between iterations (not isolated). So a hard-PLCL contact near the friction limit cannot currently be run at all (v07_r0.9_patched.log).',
    ['Before the first Newton step: if |g| <= max(rtol_abs, 1e-10 x |applied load|) accept the increment with 0 iterations',
     'Absolute residual floor in the line search: accept a = 1 when |g| is already below the absolute tolerance'])

chk('B3 Red-team F-0013 (line search accepts a non-descent step with inconsistent rigid / deformable state)',
    'ok', 'major',
    'Confirmed for the code it names (commit 77b7596, newton.py:221-233 at that commit; same defect as my r0001 C2 / r0002 A2). FIXED at HEAD 1f09ae2: the trial state is only accepted when it decreased the residual (newton.py:246 dec = True), otherwise rigid-body c / R are restored on every failed trial and x is not reassigned; a stale tangent is refactorised once, then the increment fails and run() cuts it (:249-253, :288-318); convergence also requires line step a >= ls_conv_min 0.1 (:270, FEBio LSmin idea). The fix introduced B2.',
    ['Close F-0013 as confirmed + fixed in 1f09ae2; open B2 as its follow-up'])

chk('B4 Convergence test without a residual criterion while the friction tangent is approximate',
    'problem', 'major',
    'Default tolerances newton.py _tols(): dtol 0.001, etol 0.01, rtol 0 (FEBio defaults; rtol 0 = residual not checked). With friction the tangent is k I on touching nodes (newton.py:111), not the slip-cone tangent, so the displacement / energy norms can be small while the residual is not (over-stiff tangent = short steps). V07 slip increments need 25-59 iterations (v07_r0.9.log), i.e. linear, not quadratic convergence. gate2_fsu.py:33 and production use the defaults (FEBio decks have rtol 0).',
    ['Add an absolute equilibrium criterion for every increment: |reduced residual| <= 1e-6 x |applied load| (force dofs) and per rigid body |reaction + applied| <= 1e-3 x applied (force and moment); report it per increment',
     'Use the exact frictional tangent (autodiff of sliding_fn as done for the frictionless pair in the dirty tree) or at least mu-scaled slip tangent'])

chk('B5 Uncommitted solver code in the working tree; anything run now (including gate 2 retries and my V07) is not traceable to a commit',
    'problem', 'major',
    'git status: M gpufe/contact.py, M gpufe/newton.py (diff: gap_normal() replaces the facet normal by the direction q - x_slave in the frictionless AND frictional force, contact.py:158-171; pair_forces() + exact autodiff tangent for mu = 0, newton.py:100-106). The frictional tangent still activates contact with the old facet-normal gap (newton.py:109) while the residual uses gap_normal (contact.py:171): residual and tangent no longer use the same gap near facet edges. Gate 1d and gate 2 reports at HEAD were produced before this change (or with an unknown tree: reports carry no commit, see B8).',
    ['Commit before any gate run; every report stores git commit + dirty flag (+ diff hash) and refuses to write a PASS from a dirty tree',
     'Re-run gate 1c / 1d / V07 after the commit; use the same gap in newton.py:109 as in contact.py:171'])

chk('B6 Gate coverage: the production path (Newton + sliding Coulomb contact + force / moment control + curved faces) has no recorded pass; gate 1d tests only 15 % of the friction limit under displacement control; VERIFICATION.md is stale (confirms red-team F-0014)',
    'problem', 'major',
    'gate1b_equilibrium.py:56 and gate1c_friction.py:62 still call slv.Solver (dynamic relaxation), not NewtonSolver. Gate 1d (gate1d_stick_memory.py) is displacement-controlled back to 0 and reaches max |Fx/Fz| 0.073 at mu 0.5 (results/gpufe_verify/gate1d/gate1d_report.json), so it cannot see B1 (which appears at 0.9 mu under force control) or B2 (crash only in holds). Gate 2: only flex_pos_y exists; it passes the rotation (5.781396 vs 5.781395 deg, 1.1e-7) but facet contact is not engaged in flexion (facet force 0) and the tie forces are reported as 0.0 while the moment balance is exact (Fixed My -1500.0 vs Forced +1500.0 N mm, flex_pos_y.json history t 2.0) -> the tie report is a bookkeeping bug, not the load path. gate2_fsu.py:6-7 pass criterion ignores facet force and ligaments. results/gpufe_verify/VERIFICATION.md: title still "GPU explicit solver", no gate-1d row, no solver / commit column, gate 2 "running". Not covered by any gate: large rigid rotation through Newton, near-incompressibility (nu 0.49) in Newton, two-pass sliding, follower pressure vs FEBio, rigid force / moment through Newton vs FEBio, tet4 + hex8 mixed contact, curved contact faces.',
    ['1b and 1c through NewtonSolver (keep slv.Solver rows for the record); gate 1e = V07; gate 1f = new contact cases (two-pass, curved: block on a cylinder / sphere, follower pressure, rigid moment) vs FEBio', 'VERIFICATION.md: one row per gate with solver class, commit, date, criterion, numbers; owner = verifier text, integrator edits on CR'])

chk('B7 e02 (methods/e02_friction_limit.py), now the PRIMARY slip-out method (DECISIONS 2026-10-27 (1), (c)), has no credibility gate and two configuration errors',
    'problem', 'critical',
    '(a) LP itself is correct: v08_e02_checks.py / .json: uniform-pressure disc, pure shear mu = F/N exact (rel -1.7e-14); shear at 11.25 deg off a polygon vertex +1.96 % (= 1/cos(pi/16) - 1, conservative as documented); pure twist mu_LP 0.30199 vs 3T/(2NR) 0.30005 (+0.65 %); combined shear+twist inside [max, sum]. '
    '(b) Configuration mix: face normals, areas and centres come from the REFERENCE geometry (e02:42 X from case.feb Geometry, :50-53) while the stress is the CURRENT Cauchy stress from case.xplt (:66-67); no displacement is read. A face rotated by theta relative to the reference gives, for pure pressure with zero true shear, a spurious shear p sin(theta), i.e. spurious mu = tan(theta): 1 deg 0.017, 3 deg 0.052 (17 % of mu 0.3), 5.78 deg (intact C3-C4 flexion ROM at 1.5 N m, gate 2) 0.101 (34 %) (v08_e02_checks.json, rotated_normal). The actual top-face rotation in the tied cage runs is unverified (expected a few degrees: the top face follows C3). '
    '(c) Curved faces: only tau[:2] and c[:2] are kept (e02:71, :74) - confirms red-team F-0011 by code reading (its p062 numbers not re-run by me). '
    '(d) Element-centroid stress of the face-layer element is used instead of the interface traction (half an element from the face), and there is no equilibrium check (sum of face forces vs the cage load, top vs bottom). '
    '(e) Data: results/method/ holds 79 fl_*.json that point to old-repo cases (e.g. fl_p002_physio.json case = human_study/al_v2/cases/p002_physio, i.e. before the load-curve fix, ISSUES I-001 / I-002 "INVALID") with no validity flag and no provenance; methods/e02_batch.sh:3-4 still cds two levels above the repo and reads human_study/al_v2/... (round-2 CR-v6, not done).',
    ['Use deformed coordinates (x = X + u from the xplt displacement field) for normals, areas, centres; or use FEBio contact traction output of the tied interface (fsu.feb already outputs "contact pressure" / "contact force" plot variables)',
     'Full 6-dof whole-face limit for curved faces (F-0011): friction cone per facet in its own tangent plane, equilibrium of force AND moment in 3D, normal forces may resist (geometric interlock) only where compressive',
     'Gate M3 (proposed_gate_criteria.gate_M3_e02) before any mu_req ranks a design; mark or move the 79 invalid result files'])

chk('B8 Provenance: no result can be traced to code version, inputs, options and FEBio build',
    'problem', 'major',
    'gate1_report.json has no provenance fields (v06_compare_gate1_r0003.json: report_has_provenance_fields = []); same for gate1d_report.json and gate2/flex_pos_y.json (keys: direction, increments, ... no commit / hash / options). Reference FEBio = 4.13 release (32ae206) + 9 locally modified, uncommitted files incl. FESolidSolver2.cpp and FETiedElasticInterface.cpp (diff sha256 4ce68b96..., v09_febio_build_state.txt); the active libfebiomech.so (built 2026-10-22 04:53) sits next to 6 other builds (dbg_bad, good_v3, patch5a, pre_lspatch, pre_prestrainpatch, pre_tiepatch); nothing records which build produced snapshot/reference/fsu_intact or the old-repo physio runs; febio4 binary hash alone (103 kB launcher) does not identify the physics libraries. Uncommitted gpufe/ code: B5. snapshot/MANIFEST.json does have sha256 per copied file (good) but not the physio_fix reruns (F-0020).',
    ['Every report: git commit + dirty flag + sha256 of input .feb + options dict + FEBio build id (sha256 of libfebiomech.so + patch diff hash) + GPU / torch / cuDSS versions',
     'Commit the FEBio patch as a .patch file in the repo, record which build made each reference; delete or archive the unused library variants'])

chk('B9 FEBio contact options still silently ignored: augmented Lagrangian on the facet joints',
    'problem', 'major',
    'snapshot/reference/fsu_intact/flex_pos_y/fsu.feb has laugon 1 on 2 contacts (and two_pass 1 on 2). gpufe/feb.py:3 claims "anything else raises", but _contact (feb.py:155-163) stores every child tag as a number and nothing reads laugon; also the types sliding-tension-compression and sliding-node-on-facet are accepted (feb.py:162) and solved with the same sliding-elastic node-to-facet algorithm although FEBio implements them differently. Repeat of round-1 C5 / round-2 A5 (CR-v5). Matters for gate 2 facet forces in extension / axial rotation.',
    ['Whitelist of contact keywords with values the code implements; raise otherwise', 'Implement augmentation, or prove penalty x0.5 / x2 changes facet force and ROM < 2 %'])

chk('B10 Contact discretisation differs from FEBio sliding-elastic; the docstring overstates "following FEBio"',
    'problem', 'minor',
    'GPU: one node-to-facet pass, closest-point projection on triangles (contact.py:93-104, quads split in two), normal = master facet normal (HEAD) or the closest-point direction (dirty tree, contact.py:158-165), force = eps x tributary node area x gap. FEBio: Gauss points of the slave facets, ray projection along the SLAVE surface normal (FESlidingElasticInterface.cpp:584 nu = SurfaceNormal, :606 np.Project(r, nu, rs) with FENormalProjection, :621 g = nu . (r - q)), slip direction from the relative velocity (SlipTangent, :897). Not wrong in itself, but contact quantities can only be compared with a contact-level tolerance (pressure / force ~ 1e-2, not 1e-6), and mesh / penalty sensitivity must be shown (gate 4d / 4e).',
    ['State the method honestly in contact.py:1-11 and VERIFICATION.md; set contact tolerances as in proposed_gate_criteria'])

chk('B11 Gent locking clamp unchanged',
    'problem', 'minor',
    'gpufe/mech.py:155 den = clamp(1 - (I1~ - 3)/Jm, min=1e-6); FEBio FEGentMaterial does not clamp (round-2 A6, CR-v11). Downgraded to minor only because PI rule (3) caps soft compression at 30 % (DECISIONS 2026-10-27), but the near-locking range is still not gated.',
    ['Raise (invalid result) when den < 1e-3; gate-1 case at (I1~-3)/Jm 0.9 and 0.98'])

chk('B12 Material formulas vs FEBio source after the round-2 code changes', 'ok', 'minor',
    'Only kern.elem_tangent changed (vmap batching of the same jvp, kern.py:125-140) and the pressure force was moved into Solver.pressure_q (solver.py:190-202, same 2x2 Gauss formula). Gate 1 errors identical to round 2 (B gate_reruns[0]), so the residual formulas are unchanged. Pressure load stiffness = forward-mode autodiff of the same pressure_q (newton.py:115-123), consistent by construction; not compared with FEBio (no pressure case in any gate).',
    ['Finite-difference tangent check per material and for pressure (rel < 1e-6) as a gate-1 add-on'])

chk('B13 Round-2 A1 (stick-memory claimed as FEBio behaviour)', 'ok', 'minor',
    'Corrected in contact.py:107-112 and gate1d_stick_memory.py:1-9, :71 (labels now "stick-memory rule" / "re-anchor (old / FEBio) rule"); PI decision 2026-10-27 (1) uses the law, not FEBio, as the frictional reference. VERIFICATION.md not updated (B6).', [])

chk('B14 Change-request process', 'problem', 'minor',
    'No requests/ or work/requests/ folder exists (ls work: agents board findings); none of the round-1 / round-2 CR-v1..v12 became a CR-*.json, although GOVERNANCE.md:33 requires it. Several were fixed in code anyway (A1, A2), others silently not (CR-v4, v5, v6, v9, v10, v11).',
    ['Integrator creates requests/CR-*.json with status for every CR in the board files; verifier closes them'])
d['checks'] = C

d['proposed_gate_criteria'] = {
 'general_every_gate_and_run': 'Production class (NewtonSolver) from a CLEAN commit; report carries commit, input sha256, options, FEBio build id, GPU / library versions (B8). Every increment: converged by FEBio norms AND |reduced residual| <= 1e-6 x |applied load| AND per rigid body |reaction + applied| <= 1e-3 x applied (force and moment) (B4). No increment may be accepted after max cuts. Verifier re-run agrees to 1e-9 relative (GPU atomics: no bit identity, measured 1.5e-16).',
 'gate_1_additions': 'Through NewtonSolver vs FEBio, same deck: 60 deg superposed rigid rotation (objectivity, stress rel err < 1e-9 vs unrotated); neo-Hookean nu 0.49 hex8 + tet4 (< 1e-6); Gent at (I1~-3)/Jm 0.9 and 0.98 (< 1e-6, raise above clamp); follower pressure on a quad block, rigid body under force + moment, two-pass sliding block, tied non-conforming block: < 1e-3 relative for displacements / reactions (contact discretisation differs, B10). Finite-difference vs autodiff tangent < 1e-6 relative per material, pressure and frictionless contact pair.',
 'gate_1e_force_hold': 'V07 deck (gpufe/gate1c geometry, rigid plate under force control) with Ft / (mu Fn) = 0.5 and 0.9, block E 10 and 400 MPa, n = 10 / 20 / 40: (i) every increment converged without workaround (B2); (ii) displacement during the hold (t 0.5-1.0) < 1e-3 mm absolute AND < 1 % of the ramp displacement x(0.5); (iii) x(0.5) independent of n within 2 %; (iv) ramp to 1.2 mu: gross slip, Ft/Fn while sliding within 2 % of mu. Reference = Coulomb law, not FEBio (FEBio fails (ii): 0.151 / 0.301 mm, V07).',
 'gate_1d_stick_cycles': 'Keep the existing displacement cycles, add amplitude at 0.9 mu and force-controlled cycles 0 -> 0.9 mu Fn -> 0 (3 cycles): cycle-end residual displacement < 1e-3 mm and |Fx/Fz| < 1e-3 for n = 10 / 20 / 40.',
 'gate_2_intact_FSU': 'All 6 directions, same .feb as snapshot/reference/fsu_intact (build id recorded): main rotation at 0.3 / 0.6 / 0.9 / 1.2 / 1.5 N m |diff| <= max(5 % of FEBio, 0.1 deg) (in-vitro C3-C4 ROM scatter is much larger: Panjabi et al. 2001, Spine 26:2692-2700); coupled rotations <= max(20 %, 0.2 deg); facet force per side where FEBio > 5 N within 10 % (augmentation implemented, or penalty x0.5 / x2 sensitivity < 2 %, B9); tie force per interface non-zero and within 5 % of FEBio, C3 moment balance <= 1 %; ligament force per set <= max(10 %, 1 N); PASS only if all 6 pass.',
 'gate_3_cage_tied': 'p062 tied physio (after the load-curve fix, physio_fix deck with recorded hash), same .feb: ROM as gate 2 per window; cage axial force <= 5 %; per-face shear force and twist <= max(10 %, 1 N / 20 N mm); mu_req (e02 after B7 fixes) per window |diff| <= max(10 %, 0.03); peak 1 mm2-averaged endplate pressure <= 15 %; cage height after insertion <= max(5 %, 0.005 mm).',
 'gate_M3_e02': 'NEW (B7), required before mu_req ranks anything. (1) Closed forms: flat disc shear / twist / combined as v08 (LP within +2 %, never below the exact value); (2) curved: spherical cap and cylinder-wedge faces under known load, mu_req vs hand / independent LP solution within 2 %; (3) rigid rotation 5 deg of a loaded tied block (pure compression): spurious mu_req < 0.005; (4) equilibrium: sum of face forces vs cage resultant within 2 %, top vs bottom normal force within 2 %; (5) traction source: element-centroid stress vs FEBio contact traction of the tied interface on p062, mu_req within 5 %; (6) shortcut check (with gate 4): frictional GPU run at mu = 0.8 x mu_req must dislocate (rigid-part translation > limit or gross slip) and at mu = 1.2 x mu_req must hold (< 0.05 mm) for 3 designs.',
 'gate_4_real_friction': '4a benchmarks: block slip onset Ft/Fn within 2 % of mu (both directions, reversal); disc under pure twist slips at T = (2/3) mu N R within 3 %; combined onset within 3 % of the e02 LP. 4b vs FEBio ONLY for monotonic ramps to first gross slip (3 designs x mu 0.2 / 0.3 / 0.45): onset load within 10 %, stick-area fraction within 10 points; no FEBio comparison of holds / cycles (FEBio ratchets, V07). 4c increment halving: dislocation (rigid-part translation, DECISIONS 2026-10-27) change <= 0.05 mm (10 % of the 0.5 mm limit), per-cycle ratchet change <= 0.01 mm. 4d penalty x0.5 / x2: <= 0.05 mm. 4e cage voxel 0.2 vs 0.1 mm on one design: dislocation and mu_req within 10 %. 4f dislocation metric: best-fit rigid motion extraction exact (< 1e-6 mm) on a synthetic pure rigid motion, and zero (< 1e-4 mm) on a pure symmetric squash.',
 'gate_5_every_production_run': 'Every increment meets the general criteria, else the design is INVALID and never ranked; each friction run ends with a 10-increment hold at constant load: dislocation change in the hold < 1e-3 mm (creep canary; needs B1 and B2 fixed); no Gent element with (I1~-3)/Jm > 0.95; kinetic-energy check not applicable (static Newton) -> replaced by load-rate independence = 4c on a seeded 10 % sample (dislocation <= 0.05 mm, mu_req <= max(2 %, 0.01)); full provenance block stored in the archive row.'
}

d['change_requests'] = [
 dict(id_hint='CR-v13', owner='engine', target='gpufe/contact.py:106-117 (set_anchor), sliding_fn', reason='B1 ratcheting under constant load below mu N (confirms F-0015)', evidence='work/agents/verifier/v07_summary.md, v07_*.log', request='keep the elastic tangential offset for slipped nodes (return mapping), then pass gate 1e'),
 dict(id_hint='CR-v14', owner='engine', target='gpufe/newton.py:246-253, :270', reason='B2 crash in hold increments that start in equilibrium', evidence='work/agents/verifier/v07_r0.5.log, v07_r0.9.log', request='accept an increment whose start residual is below an absolute tolerance; absolute residual floor in the line search'),
 dict(id_hint='CR-v15', owner='engine', target='gpufe/newton.py _tols, relax', reason='B4 no residual criterion with an approximate friction tangent', evidence='newton.py:111, _tols rtol 0; V07 25-59 iterations per slip increment', request='absolute equilibrium criterion per increment and per rigid body; report it'),
 dict(id_hint='CR-v16', owner='engine', target='gpufe/contact.py, gpufe/newton.py (working tree)', reason='B5 uncommitted solver code; tangent uses a different gap than the residual', evidence='git diff gpufe/; newton.py:109 vs contact.py:171', request='commit, unify the gap, re-run gates 1c / 1d / 1e from the clean commit'),
 dict(id_hint='CR-v17', owner='methods owner (integrator) + PI', target='methods/e02_friction_limit.py, results/method/', reason='B7 e02 is the primary slip-out method without a gate; reference-config normals; curved faces; invalid old outputs', evidence='e02:42, :50-53, :66-74; v08_e02_checks.json; F-0011; fl_p002_physio.json case path', request='deformed configuration, 3D whole-face limit, equilibrium check, gate M3; flag or remove the 79 old outputs'),
 dict(id_hint='CR-v9 (repeat, extended)', owner='engine', target='gpufe/gate1b_equilibrium.py:56, gate1c_friction.py:62, results/gpufe_verify/VERIFICATION.md', reason='B6', evidence='see B6', request='1b / 1c through NewtonSolver; add gate 1e (V07) and 1f (contact cases); rewrite VERIFICATION.md with solver / commit / criterion columns'),
 dict(id_hint='CR-v10 (repeat)', owner='engine', target='tie force bookkeeping (Solver.record / tied passes)', reason='B6 tie forces reported 0.0 while the moment balance is exact', evidence='results/gpufe_verify/gate2/flex_pos_y.json history t 2.0', request='report the tie force sum per interface and compare with FEBio in gate 2'),
 dict(id_hint='CR-v4 (repeat, extended)', owner='engine + PI', target='all report writers; FEBio build', reason='B8', evidence='v06_compare_gate1_r0003.json; v09_febio_build_state.txt', request='provenance block in every report; FEBio patch committed as a file, build id recorded per reference run, unused library variants archived'),
 dict(id_hint='CR-v5 (repeat)', owner='engine', target='gpufe/feb.py:155-163', reason='B9 laugon / contact types silently accepted', evidence='fsu.feb laugon 1; feb.py:3 claim', request='whitelist + raise; augmentation or penalty sensitivity proof'),
 dict(id_hint='CR-v11 (repeat)', owner='engine', target='gpufe/mech.py:155', reason='B11 Gent clamp', evidence='mech.py:155', request='raise when den < 1e-3; gate-1 near-locking case'),
 dict(id_hint='CR-v18', owner='integrator', target='requests/', reason='B14 no CR files exist', evidence='ls work/', request='create requests/CR-*.json for CR-v1..v18 with status'),
]
d['finding_reviews'] = [
 dict(finding='F-0011', status='confirmed by code reading (e02:71, :74 keep only x-y components); p062 magnitude not re-run'),
 dict(finding='F-0013', status='confirmed for 77b7596; fixed at 1f09ae2 (newton.py:246-253); new defect B2'),
 dict(finding='F-0014', status='confirmed (B6)'),
 dict(finding='F-0015', status='confirmed by simulation (V07, B1): creep under constant load below mu N, increment-dependent; FEBio same'),
]
d['summary_zh'] = (
 '結論：暫停（HOLD）。GPU 有限元素求解器（自製的圖形處理器有限元素程式，gpufe）與摩擦需求計算程式（e02，用來算「至少需要多大的摩擦係數，籠子才不會整體滑出」）目前都不能用來排名或挑選設計。'
 '一、重現性：第一關（材料公式測試）在我的資料夾重跑，六個案例全部通過，與原報告相同（差異最多 1.5e-16），可以重現。'
 '二、最嚴重的問題（關鍵）：我做了一個簡單測試（V07）：一塊軟方塊（彈性模數 10 百萬帕）被壓在另一塊上，側向力固定在摩擦極限的 90%，然後保持不變。依照庫倫摩擦定律，負荷不變時方塊不應再移動。'
 '但 GPU 求解器在保持期間又滑了 0.119 毫米（分 20 步計算）；把步長減半時變成 0.046 毫米。也就是說，滑移量取決於計算步數，是數值假象，不是物理現象。FEBio（對照用的商用級開源有限元素軟體）滑得更多，而且與步數成正比（0.151、0.301、0.603 毫米）。'
 '這個量與「向後脫位不得超過 0.5 毫米」的判準同一個數量級，所以目前的摩擦模擬結果不可信。原因很可能是：某個接觸點滑動之後，程式在下一步把它的摩擦力歸零（紅隊 F-0015 已指出，我用模擬證實）。'
 '三、新的程式錯誤（主要）：上一輪修好了線搜尋（牛頓法中縮小步長的步驟），但修正帶來新問題：當負荷保持不變、模型已經完全平衡時，程式會誤判為不收斂並中止。另外，硬方塊（彈性模數 400 百萬帕）在 90% 摩擦極限下根本算不完。'
 '四、e02（主任 2026-10-27 決定以它作為判斷滑脫的主要方法）還沒有任何驗證關卡：(1) 它的線性規劃核心是正確的，我用解析解驗證過，誤差在 2% 以內且偏保守；'
 '(2) 但它用「未變形時」的面方向去配「變形後」的應力。如果籠子上表面隨第三頸椎轉了 3 度，算出的摩擦需求會憑空多出約 0.05（相當於摩擦係數 0.3 的 17%）；轉 5.8 度則多出約 0.10；'
 '(3) 它把彎曲的接觸面當成平面（紅隊 F-0011 指出，我讀程式碼確認）；(4) results/method 裡的 79 個舊結果檔來自修正負荷曲線之前的資料，已知無效，但檔案上沒有任何標記。'
 '五、可追溯性不足：結果檔沒有記錄程式版本、輸入檔雜湊值與設定；目前工作目錄裡還有尚未提交的接觸力程式修改；當作對照的 FEBio 是本地修改過的 4.13 版（改了 9 個檔案），旁邊還放著 7 個不同的函式庫版本，沒有紀錄哪一個版本算出哪個參考結果。'
 '六、紅隊發現的審查結果：F-0013（線搜尋）在舊版本確實存在，目前版本已修好；F-0014（實際使用的求解路徑沒有通過任何關卡）成立；F-0015（滑動後摩擦力歸零）已用模擬證實；F-0011（曲面當平面）讀程式碼確認。'
 '七、我提出了第二到第五關以及 e02 專用關卡的具體數字標準（見 proposed_gate_criteria）。其中最重要的是：負荷保持期間滑移量必須小於 0.001 毫米，而且不能隨計算步數改變；e02 必須在變形後的幾何上計算，並通過曲面與 5 度旋轉的測試。')
json.dump(d, open(F, 'w'), indent=1, ensure_ascii=False)
print('written', F)
