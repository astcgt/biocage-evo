# Four-agent kickoff plan: starting the designer and the engine (2026-10-31, proposal for the PI)

Source material: the evo-infrastructure audit of 2026-10-31 (findings A5-F01..F14, summarised in RISKS.md and in the
OLD-repo progress report), GOVERNANCE.md, PLAN.md, the three role prompts. Nothing here is started; the designer prompt is a
draft in `roles/prompts/designer.md` marked DRAFT.

## 1. Readiness checklist

| Item | State today | Needed for round 1 |
|---|---|---|
| Verifier, safety guard, red team | prompts exist; 3 rounds run (10-26..10-28); every verifier verdict HOLD; 29 findings unanswered; no round since 10-28 | answer findings (status file each), schedule round 4 with a digest of the new items |
| Designer | no prompt, no schema | `designer.md` (draft below), `designer.json` schema, workspace `work/agents/designer/` |
| L0 constraints code (S1-S9) | none | `constraints.py` for S1, S3, S4, S5 (geometry) and S2 (insertion sweep) on the voxel field; S6-S9 on loaded results |
| Voxel design space and encodings | none | 0.2 mm grid between the distracted endplates (h25 gap library); CPPN + design programs + direct edits emitting the same field |
| Evaluation path | FEBio L2 via OLD h14/h30/h31 works for the human families (23 min per design on a GPU); EVO copy of h14 is stale; gpufe gate 2 fails 5/6 | voxel field -> h12-format npz -> OLD h14 (split2 settings) -> h24 -> h19 -> h31 -> e04/e05; pilot one free-form design through preflight |
| Archive | none | append-only JSONL/SQLite with genome, field hash, L0/L2 results, provenance, descriptors, fitness, status, verified_by |
| Engine loop | none | MAP-Elites generation: select from filled cells, mutate, L0 filter, batch to L2, insert, round report |
| Governance plumbing | HOLD not enforced; no frozen tree; no CR register; GPU whitelist missing | evo_daemon HOLD gate, frozen.json per round, work/requests/CR-*.json, config.json gpus [1,2,3,4] |

## 2. Designer role (draft prompt: `roles/prompts/designer.md`)
Rights: read the whole project except other roles' private folders; write only `work/agents/designer/` and
`work/board/rNNNN/designer.json`. Duties: propose at most 10 designs or design programs per round that fill EMPTY or weakly
filled archive cells, each with a rationale kept in the private folder (the verifier and safety guard see only the proposal
and its numbers: blinding). Scoring: archive cells filled by its proposals that later pass verifier and safety; novelty that
does not survive scores zero. Forbidden: editing code, the archive, the constraints, or proposing anything outside the disc
space, with bone penetration, or in several pieces (S1, S3). Anti-gaming (red team F-0009, F-0016, F-0022): d is evaluated at
fixed values {0.5, 1.0, 1.5}, fitness is taken after the follower load, spin and posterior-most-node motion are reported with
the rigid-body dislocation.

## 3. `designer.json` schema (board file, schema-checked by the engine)
```json
{"round": 4, "role": "designer", "proposals": [
  {"id": "E-4-1", "kind": "program | cppn | voxel_edit | mutation_idea",
   "source": "python function text (program) | weights+topology (cppn) | parent id + edit list (voxel_edit) | text (mutation_idea)",
   "seed": 12345, "target_cells": [{"void_frac": [0.5, 0.6], "mean_E_MPa": [20, 100], "shape_class": "rim+struts"}],
   "novelty_claim": "one sentence", "predicted_risks": ["insertion compression of the crown", "..."]}],
 "summary_zh": "給 PI 的白話摘要"}
```
Programs run in a subprocess sandbox (timeout 60 s, no network, memory limit) and must return (occupancy, phi) arrays on the
grid; anything else is rejected, not interpreted.

## 4. Engine MVP (rounds 1-3), FEBio-L2 first
- Design space: 0.2 mm voxels in the frame (X anterior, Y left, Z normal), between the distracted endplates from the gap
  library; in-plane limit = endplate outline inset 1 mm; layer-conforming columns (h12 style) so the field maps to the h12 npz
  contract (nodes, hex connectivity, region, phi, hard flag, face quads, node sets).
- Encodings in order: design programs first (the designer writes them; simplest to sandbox), CPPN second, direct edits third.
- L0: `constraints.py` S1 (by construction), S3 (6-connected single component), S4 (void >= 50 % of disc-space volume AND
  connected to both endplates), S5 (0.4 mm opening, 45 deg support), S2 (insertion sweep along -X: hard voxels fit the gap
  profile without compression; soft compression <= 30 %; width <= anterior opening). Unit tests from the red team's synthetic
  cases.
- L2: OLD pipeline with the split2 settings class (physio_rot, physio_dynamic, physio_split), preflight h24, scheduler h19,
  runner h31, post-processing collect_split (e04 mu_squeeze per window, e05 compression). Budget: <= 24 designs per round
  (~1 h of 4 GPUs + 8 CPU slots).
- Archive: `work/archive/archive.jsonl`, immutable entries {id, round, genome, field_sha256, L0, L2 {per window mu_squeeze,
  slip bound, target_reached; sustained, peak}, provenance {OLD git hash, h14/h30/h31 sha256, case.feb sha256, settings class,
  FEBio build id}, descriptors {void_frac, mean_E, shape_class}, fitness {mu_req_worst, compression_pass}, status,
  supersedes, verified_by}.
- Round report: `work/board/rN/engine_report.json` (numbers only) and a generated `digest.md`.
- L1 (fast screen) is NOT on the critical path: a GP surrogate on voxel descriptors trained on the archive after ~40 entries
  (SAIL). gpufe L1b joins when gates 2-4 pass.

## 5. Round-0 content for the designer (seeds)
1. Concavity interlock (hard core inside the insertable envelope + compliant crown refilling the C3 concavity).
2. Radial grading made explicit (hard rim, compliant inner band) - the basin the human screen found.
3. Posterior compliant lip inside the disc space.
4. Biodisc-void topology variants (central window vs lateral channels) at fixed void fraction 50-60 %.
5. Anything else, but each proposal must state the cell it targets and the risk it expects.

## 6. Integrator checklist per round
1. Freeze: frozen.json (git hash, dirty flag, sha256 of gpufe/, methods/, docs/, OLD h12/h14/h30/h31).
2. Validate designer.json against the schema; reject invalid entries with a reason.
3. L0 -> L2 batch through preflight; collect; archive insert with provenance.
4. Hand the round report to verifier and safety (blinded: no designer rationale); then the red team.
5. Apply verdicts (HOLD stops promotion; VETO removes designs); answer every finding (status file); write the PI digest with
   summary_zh.
6. Commit board/, archive/, findings/ with the OLD-repo hash in the message.

## 7. Timeline and decisions needed
- Integrator work before round 1 (from the audit): W0 governance plumbing 8-10 h; W1 designer prompt/schema 4-6 h; W2 L0
  constraints 10-12 h (+ S9 metric 6-8 h); W3 voxel space 8-10 h; W3b encodings 6-16 h; W4 archive 6-8 h; W5 engine loop
  10-16 h; W6a L2 path incl. one pilot 12-20 h; W7 report format 4 h; W8 verifier/safety hooks 6 h. Total ~100-140 h, i.e.
  2-3 weeks at full time; critical path W3 -> W6a pilot -> W2 -> W4/W5 -> W1.
- Compute per round: 24 designs x 23 min / 4 GPUs (+ CPU slots) ~ 1.5-2 h; 2-3 rounds per day possible once the chain works.
- PI decisions before round 1: (a) S8 subsidence number; (b) verdict rule for designs that invert under the follower load;
  (c) fitness = e04 mu_squeeze (dislocation mode) with e03 per-face mu as diagnostic, or both as Pareto objectives;
  (d) designer model and round cadence; (e) whether gpufe stays on the plan or is parked until gate 2 passes.
