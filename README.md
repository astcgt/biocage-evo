# BIOCAGE free-form evolution (biocage-evo)

**English** | [繁體中文](README.zh-TW.md)

Free-form, evolution-driven design of a **bioresorbable PLCL cage for the human cervical spine (C3-C4)** that gives
**temporary support and fixation while a tissue-engineered intervertebral disc (biodisc) matures in the body**. Shape and
material distribution are not drawn by a designer; they are grown inside the disc space and judged by simulation. Four
independent AI agents (designer, verifier, safety guard, red team) generate, check, guard and attack the work under
explicit rules.

> **Status (2026-10-26):** research-infrastructure stage. The GPU solver has passed its first credibility gates; three of the
> four agents (verifier, safety guard, red team) run in daily rounds; the designer and the evolution engine have **not**
> started. No design result exists yet. See [Current status](#6-current-status).

---

## 1. Research background

### 1.1 Clinical problem
Degenerative disc disease is a leading cause of neck and back pain. End-stage treatment is either fusion or total disc
replacement with a mechanical prosthesis; both treat the symptoms and are associated with adjacent-segment disease.
Tissue-engineered total disc replacement aims instead to restore a living disc. Composite engineered discs (collagen
annulus around an alginate nucleus) integrated with host tissue and reached native-like stiffness after 6 weeks to 9 months
in rats, 16 weeks in dogs and 8 weeks in goats. Before implantation, however, they are about ten times softer than a native
disc and cannot carry spinal loads on their own.

### 1.2 Why a cage, and why it failed before
The engineered disc therefore needs a **temporary, resorbable support** while it matures. The lab's previous attempt
(Lintz, PhD dissertation, Cornell 2021, ch. 4; summary in [`docs/PRIOR_FAILURES_Lintz2021.md`](docs/PRIOR_FAILURES_Lintz2021.md))
implanted FDM-printed PLA cages in the minipig cervical spine (C3/4, C5/6, 4 weeks):

- the two-piece cage collapsed within one week (disc-height index -64 %);
- the one-piece cage stayed in place, but every cage fractured at the same two posterior sites, caused by a posterior bony
  process that concentrated repeated loads: a geometry problem, not a material one;
- a uniform platen compression test (134 MPa without failure) had predicted success and was misleading;
- PLA softened during culture at 37 °C (hydrolysis);
- in the earlier canine study, constructs were displaced at some levels: **slip-out** is the dominant failure mode.

### 1.3 The predecessor simulation study
The parent repository (`biocage-stimulation-test-1`) built a validated FEBio model of the human C3-C4 functional spinal unit
(26-year-old female cervical model, Herron et al. 2020, J Biomech; deformable C3/C4 bone, facet contact, ligaments),
simulated anterior cervical disc arthroplasty and screened two human-designed cage families with active learning. Two
lessons drive this repository: (1) with friction alone at physiological loads, every screened design slipped; (2) the design
space of "a wall around a central window" is narrow. This repository opens the design space completely.

### 1.4 Purpose of the device (what success means)
For at least 16 weeks (26 weeks sensitivity) the BIOCAGE must keep the disc height, **not slide out in any direction**
(never toward the spinal cord), not overload or sink into the endplates, and keep enough connected space for the biodisc.
It is neither a fusion cage nor a permanent motion-preserving disc.

---

## 2. Idea: let the design grow

### 2.1 Free-form design space
- **Space**: a 0.2 mm voxel grid between the distracted C3 and C4 endplates, laterally the endplate outline inset by 1 mm.
  The cage stays strictly inside the disc space (no teeth, keels, screws or plates into bone).
- **Material**: every voxel is void or PLCL with a local hard fraction φ ∈ [0, 1], a blend of PLCL 85:15 (hard,
  E ≈ 250-900 MPa wet at 37 °C) and PLCL 50:50 (elastomer, E ≈ 1.5-12 MPa), within the 0.4 mm line / 0.2 mm layer resolution
  of FDM printing. The distraction height d (0.5-1.5 mm) is also a gene.
- **Encodings** (all produce the same voxel field and compete in one archive): compositional pattern-producing networks
  (CPPN, Cheney et al. 2013), short design programs written by the designer agent and evolved against an automatic evaluator
  (AlphaEvolve-style, DeepMind 2025), and direct growth / erosion moves inspired by bone remodelling.

### 2.2 Quality-diversity instead of a single optimum
A MAP-Elites archive (Mouret & Clune 2015) keeps the best design in each cell of a behaviour map (biodisc-space fraction ×
mean hard fraction × structural class), so unconventional solutions survive long enough to be tested, and the PI receives a
trade-off chart rather than a single answer.

### 2.3 Objectives
- **Fixation (main)**: minimise the friction coefficient needed to prevent slip-out, worst of six physiological directions
  (flexion, extension, left / right lateral bending, left / right axial rotation; 1.5 N·m pure moments with a 100 N follower
  load, one direction at a time).
- **Biodisc space**: maximise the connected void volume (trade-off with fixation).

### 2.4 Evaluation levels
| Level | Model | Cost | Use |
|---|---|---|---|
| L0 | geometry and rule checks (S1-S5) | milliseconds | every candidate |
| L1 | reduced GPU model, calibrated on L1b / L2 | < 1 min | screening |
| L1b | full C3-C4 model on the GPU (`gpufe`: same mesh and materials as FEBio, real Coulomb friction) | 10-30 min | front runners |
| L2 | full FEBio (the validated reference) | hours | finalists; the only numbers reported as results |

---

## 3. Minimum constraints

Only what the purpose, the surgery and the safety of the spinal cord, nerve roots, vertebral artery and bone require is
fixed; everything else is free. The list is owned by the safety-guard agent, and every change needs the PI
([`docs/PLAN.md`](docs/PLAN.md), [`docs/DECISIONS.md`](docs/DECISIONS.md)).

| # | Constraint | Rule |
|---|---|---|
| S1 | Stays in the disc space | inside the 1 mm-inset endplate outline, between the endplates |
| S2 | Insertable in one piece from anterior | transient disc-height gain ≤ 2 mm over native during insertion (default from surgical technique guides, pending surgeon confirmation); **no bone shaping of the endplates** (soft-tissue clearing only); hard PLCL strain ≤ 3 %, compliant PLCL ≤ 40 % during insertion |
| S3 | One connected part | no loose pieces (debris near the cord; the two-piece cage collapsed in vivo) |
| S4 | Biodisc space | connected to both endplates, ≥ 50 % of the disc-space volume |
| S5 | Printable | 0.4 mm minimum feature, 0.2 mm layers, ≤ 45° overhang |
| S6 | Load capacity | ≥ 1164 N compression without cage failure |
| S7 | Height maintenance | height loss ≤ d/2 at 150 N |
| S8 | Bone protection | endplate contact pressure below a subsidence limit calibrated on FEBio |
| S9 | **No slip-out** (main goal) | at μ = 0.3 (sensitivity 0.2 / 0.45): cage translation ≤ 1 mm relative to C3 and C4 in every direction, 6 directions × 3 cycles, no ratcheting; toward the cord ≤ 0.5 mm and posterior push-out ≥ 135 N |

**A key finding behind S2.** The C3-C4 endplates are concave (gap 2.95-5.30 mm in the footprint). A cage that fills the
concavity needs an extra 2.35 mm of transient distraction to slide in, or 35-41 % compression of its tallest part, while hard
PLCL yields at about 5 % strain. Because bone shaping is excluded, the concavity stays, and the same concavity that blocks
insertion also blocks expulsion. Designs with a hard core inside the insertable envelope and compliant PLCL that refills the
concavity are therefore a promising family for the evolution to explore.

---

## 4. The four agents

Each agent is a separate headless Claude (Opus 5.5) process with its own system prompt and its own write permissions. The
rules are in [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md). They borrow from independent verification and validation
(NASA, IEEE 1012), separation of duties in medical-device design reviews (ISO 13485), the blackboard architecture of
multi-expert AI systems, structured hand-overs (MetaGPT), AI-safety debate and red teaming, blinded review, data-provenance
practice (W3C PROV) and the ASME V&V 40 credibility framework for medical-device simulation.

| Agent | Job | Owns | Power |
|---|---|---|---|
| **Designer** | free ideation: new encodings, design programs, mutation ideas; rewarded for novelty that survives checking | design proposals | proposes |
| **Verifier** | reliability and reproducibility: re-runs samples with fixed seeds, checks code against the FEBio source, provenance, convergence and the credibility gates | test suite, credibility gates | can **hold** a round |
| **Safety guard** | minimum purpose and anatomical safety (cord, nerve roots, vertebral artery, oesophagus, bone), surgical feasibility, degradation over the support period | constraint list S1-S9 (changes need the PI) | can **veto** designs |
| **Red team** | attacks everyone, the integrator included: model exploits, unverifiable claims, missing safety items, governance loopholes; every finding has a severity, reproducible evidence and 2-3 fix options | findings register | escalates |

**One round:** designer proposes → engine evaluates (L0 → L1 → L1b / L2) → verifier audits (blinded to the designer's
reasoning) → safety guard audits → red team attacks → the integrator (the main Claude session) applies the verdicts, answers
every finding and writes a digest for the PI. A round is not promoted while the verifier holds it or a critical finding is open.

**Data hygiene:** one owner per artefact; agents write only to their own workspace (`work/agents/<role>/`), their verdict on
the shared board (`work/board/rNNNN/`) and, for the red team, `work/findings/`; hand-overs are schema-checked JSON; archive
entries are immutable and every number carries the code version, input hashes, seed and settings.

**Known limitation** (red-team finding F-0008, round 1): permissions restrict the agents' editing tools, but an agent that may
run Python can still write anywhere as the shared Unix user, so isolation is partly agreed rather than enforced.

**First round (2026-10-26):** the red team independently found a load-curve bug in the parent study (lateral-bending and
axial-rotation moments ramped up during flexion / extension, i.e. combined instead of pure loading), which the integrator
confirmed and fixed. It also found a friction-anchor issue in the GPU solver (F-0003) and that the production Newton solver has
not yet passed a gate (F-0004). The safety guard proposed the posterior limits now in S9 and flagged insertion strain and
long-term creep and degradation.

---

## 5. Simulation methods

- **gpufe** (`gpufe/`): a GPU finite-element solver in PyTorch that reads the same FEBio 2.5 input files. Material laws are
  transcribed from the FEBio 4 source (orthotropic cortical bone, neo-Hookean trabecular bone and cartilage, Holmes-Mow +
  fibre annulus, uncoupled Gent cage material with three-field hex8 and prestrain, nonlinear ligament springs). Large models
  use Newton iterations with exact autodiff element tangents and the cuDSS sparse direct solver; contact is node-to-facet
  penalty with FEBio's Coulomb stick / slip return mapping, so stick-slip cannot cause the convergence failures that forced the
  parent study to glue the cage to the bone.
- **Credibility gates** ([`results/gpufe_verify/VERIFICATION.md`](results/gpufe_verify/VERIFICATION.md)): (1) patch tests
  against FEBio, all materials < 1e-8; (1b) non-homogeneous equilibrium < 2e-6; (1c) sliding block vs Coulomb's law,
  error ≤ 1.1 % (FEBio itself reached only 0.457 at μ = 0.5); (2) intact C3-C4 range of motion and facet force vs FEBio;
  (3) cage case vs FEBio; (4) real-friction cases; (5) quasi-static checks. Gates 2-5 are pending.
- **Slip-out bracket** (`methods/e02_friction_limit.py`): from a bonded solution, the friction needed to hold is bracketed
  between the force ratio (optimistic) and a friction-limit linear program that also requires the twisting moment to be held
  (pessimistic; limit-surface theory). The deciding number comes from real-friction simulation.

---

## 6. Current status

| Item | State (2026-10-31) |
|---|---|
| Constraints S1-S9, objectives | agreed with the PI (S2 transient distraction pending surgeon confirmation; S8 number pending) |
| Parent-study physiological screen | re-run with the fixed load curves and the independent-window protocol: 148 valid designs (133 unique) -> 62 pass, 62 fail (soft-phase compression), 24 undetermined; every evaluable design needs mu_req < 0.17 (lateral bending governs); real-friction check of 7 designs queued (`results/method/split/*_merged.json`, `paper/figures/`) |
| GPU solver | gates 1, 1b, 1c, 1d passed; gate 2 passes flexion only, fails the other five directions at facet-contact onset (last attempt 2026-10-28); gates 3-5 not started |
| Agents | verifier, safety guard, red team: 3 rounds (10-26..10-28), verifier HOLD each time, 29 findings open; designer: DRAFT prompt only (`roles/prompts/designer.md`, `docs/DESIGNER_KICKOFF.md`) |
| Evolution engine, archive | not started; plan and effort estimate in `docs/DESIGNER_KICKOFF.md` |
| Paper material | `paper/LITERATURE.md`, `paper/ABSTRACT_OUTLINE.md`, `paper/figures/F1-F7`; risks in `docs/RISKS.md`; ideas in `docs/IDEAS_ARCHITECTURE.md` |

## 7. Repository layout

| Path | Content |
|---|---|
| `docs/` | `PLAN.md`, `GOVERNANCE.md`, `DECISIONS.md` (PI decisions), `METHODS_COMPARISON.md`, `ISSUES.md`, `PRIOR_FAILURES_Lintz2021.md`, `DECISIONS_baseline_human_c34.md` (read-only model decisions inherited from the parent study) |
| `gpufe/` | GPU solver (`feb.py` reader, `mech.py` / `kern.py` materials and elements, `contact.py`, `solver.py`, `newton.py`) and gate scripts |
| `methods/` | friction-check methods |
| `roles/` | agent prompts and `run_roles.sh` |
| `work/` | agent workspaces, shared board, findings, change requests, design archive |
| `results/` | verification reports and method results |
| `common/`, `l2_febio/` | geometry tools and the FEBio case builder copied from the parent repository (`h24_preflight.py` not wired to this repository yet) |
| `snapshot/` | C3-C4 model, coordinate frame and intact-FSU reference runs; `MANIFEST.json` lists sources and SHA-256 |
| `config.json` | external tools: FEBio 4 binary, MKL, FEBio source |

### Running
```bash
python gpufe/gate1_patch.py                      # gate 1 (FEBio 4 and MKL as in config.json, CUDA GPU)
roles/run_roles.sh 2 verifier safety redteam     # one agent round (headless Claude CLI)
```
Requirements: Python 3.10, PyTorch with CUDA, CuPy, nvmath-python with cuDSS ≥ 0.8, NumPy, SciPy, Shapely; FEBio 4 for the
reference runs.

---

## 8. Limitations

- One subject-specific, idealised left-right symmetric C3-C4 model; patient variability is not yet included.
- No direct measurements were found for the compressive yield of PLCL 85:15 or for PLCL-bone friction; values are bracketed
  from analogous materials and need coupon tests.
- Time-dependent behaviour (creep, relaxation of the clamp force, degradation over 16-26 weeks) is not yet modelled.
- Insertion limits are defaults from surgical technique guides, pending surgeon confirmation.
- Agent isolation is partly convention (F-0008).

## 9. Key references

Herron MR et al. 2020, J Biomech (FEBio cervical spine model) · Lintz M 2021, PhD dissertation, Cornell University ·
Moriguchi Y et al. 2017, PLoS One · Mojica-Santiago JA et al. 2018, JOR Spine · Moroney SP et al. 1988, J Orthop Res ·
Panjabi MM et al. 2001, Spine · Wilke HJ et al. 1998, Eur Spine J · Cheney N et al. 2013, GECCO (CPPN) ·
Mouret JB, Clune J 2015, arXiv 1504.04909 (MAP-Elites) · Novikov A et al. 2025, AlphaEvolve (Google DeepMind) ·
Smit T et al. 2024, ETH Zürich (cage topology optimisation with bone) · Joldes GR et al. 2011, Int J Numer Meth Biomed Eng ·
Rancourt D et al. 1990, J Biomed Mater Res · Duan et al. 2021 (PLCL blends, PMC8296602) · ASME V&V 40-2018.

Author: Yi Liu (astcgt), Cornell University.
