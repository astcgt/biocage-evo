# Free-form evolutionary BIOCAGE (evo)

Decisions: `docs/DECISIONS.md`. Code: `gpufe/`, `methods/`, `roles/`.

## Idea
Do not start from a "cage with a window". Let shape and material grow inside the design space and keep a whole map of
different good designs (quality-diversity), not one optimum, so unexpected solutions survive long enough to be tested.

Sources of method:
- Topology optimisation of interbody cages with the bone in the loop (Smit et al. 2024, ETH; Lin et al. 2004 Spine).
- Generative voxel encodings for multi-material structures (CPPN: Cheney et al. 2013 "Unshackling Evolution").
- Quality-diversity archive (MAP-Elites, Mouret & Clune 2015; MAP-Elites + topology optimisation for soft robots, arXiv 2407.07591).
- LLM-written design programs evolved against automatic evaluators (AlphaEvolve, DeepMind 2025).

## Design space
- Voxel grid 0.2 mm (X-Y) x 0.2 mm (Z) between the distracted C3 / C4 endplates (h25 gap library, real gap at distraction d),
  in-plane limit = endplate outline inset 1 mm (as all cages). d itself is a gene (0.5-1.5 mm).
- Each voxel: void or PLCL with hard fraction phi in [0, 1].
- Encodings (all produce the same voxel field, so they compete in one archive):
  1. CPPN: small network f(x, y, z, r, distance-to-endplate, ...) -> (occupancy, phi); mutated by the engine.
  2. Design programs: short Python functions written by the designer role (AlphaEvolve style); engine mutates their numbers.
  3. Direct voxel edits (local growth / erosion, bone-remodelling-like: add material where strain energy is high, remove where low).

## Minimum constraints (safety guard owns this list; anything not listed is free)
| # | What | Rule (S4, S5, S9 and mu agreed 2026-10-26; others default) | Why |
|---|------|-------------------------------|-----|
| S1 | Stays in the disc space | voxels only inside the inset footprint and between the endplates (by construction) | nerves / cord / vertebral artery are outside |
| S2 | Insertable in one piece from anterior | slides along -X with transient disc-height gain <= 2 mm over native (no bone shaping, soft tissue clearing only); hard PLCL strain <= 3 %, compliant PLCL <= 40 % during insertion; Y width <= anterior opening (PI 2026-10-26, default pending surgeon confirmation) | surgery |
| S3 | One connected part | single solid component (6-connectivity), no loose pieces | debris near the cord |
| S4 | Biodisc space | void connected to both endplates, >= 50 % of the disc-space volume (PI 2026-10-26; more is an objective) | purpose: biodisc matures |
| S5 | Printable | min feature 0.4 mm in X-Y, 0.2 mm layers; every solid voxel supported within 45 deg from the layer below (build along Z) (kept, PI 2026-10-26) | fabrication |
| S6 | Load capacity | >= 1164 N compression before failure (Moroney 1988) | support |
| S7 | Height | height loss <= d/2 at 150 N | keep distraction, foramen height |
| S8 | Bone | no endplate overload: peak 1 mm2-averaged contact pressure below the subsidence proxy (calibrated on FEBio) | subsidence |
| S9 | No slip-out (dislocation: rigid-body radial outward migration of the whole cage; local squash / micro-slip allowed, PI 2026-10-27) | at mu 0.3 (sensitivity 0.2 / 0.45): cage-centre translation <= 1 mm relative to C3 and C4 in every direction, 6 directions x 3 cycles, no ratcheting; posterior (toward the cord) net migration <= 0.5 mm and posterior push-out >= 135 N (PI 2026-10-26) | main goal + cord safety |

## Objectives
- Fixation: minimise mu_req = worst friction coefficient needed to hold over the 6 physiological directions (1.5 N m + 100 N follower).
- Biodisc space volume (maximise) -> trade-off chart.
- Archive axes (diversity): biodisc volume fraction x mean hard fraction x shape class (number of struts / cavities).

## Three evaluation levels
- L0 geometry / safety checks (S1-S5): milliseconds, CPU.
- L1 fast physics (< 1 min): reduced GPU model for screening (cage + endplate region), calibrated against L1b / L2.
- L1b full GPU model (10-30 min, PI 2026-10-26): the same C3-C4 FSU as FEBio solved by gpufe (GPU Newton + cuDSS, explicit
  Coulomb friction), real-friction slip-out test for the front runners.
- L2 full FEBio (finalists) (h14 physio test + compression + push-out, h24 preflight, h19 scheduler): only for archive elites, chosen to
  cover the map; results recalibrate L1 (and are the only numbers reported as results).

## The four roles (headless Claude, `roles/prompts/`)
Each round = one engine generation block. Every role reads the round report and writes a JSON verdict into `work/board/rNNNN/`.
- designer: proposes new design programs / encodings / mutation ideas; rewarded for novelty that survives.
- verifier: reruns a sample with fixed seeds, checks code + data versions, mesh / solver convergence, L1-vs-L2 agreement; can block a round.
- safety guard: checks constraints S1-S9 are implemented and applied, no candidate breaks them, the purpose (support + fixation + biodisc space) is met; can veto designs.
- red team: attacks all three (designer exploiting L1 model gaps, verifier blind spots, missing safety items); each finding = severity + evidence + 2-3 fix options.
Disagreements and every rule change go to `docs/ISSUES.md` for the PI; nothing in S1-S9 changes without the PI.
