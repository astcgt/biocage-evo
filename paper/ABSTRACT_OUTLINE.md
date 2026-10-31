# BIOCAGE paper: abstract draft and outline (2026-10-31)

Status: a draft written from the results that exist today. Every number below is in `human_study/DECISIONS.md` (OLD repo),
`results/method/split/*_merged.json` or `paper/figures/figures.json`; items marked **[TBD]** do not exist yet and name what
is needed. Nothing here has been reviewed by the PI.

## Title options
1. A resorbable cage that holds a living disc in place without screws, designed and judged by adversarial AI agents
2. Friction-only fixation of a tissue-engineered disc: in-silico design of a bioresorbable cervical support cage
3. Design space of a bioresorbable PLCL cage for temporary cervical disc support: dislocation is not the limit, soft-phase compression is

## Abstract (Nature style, <= 200 words; current draft 196 words)

Tissue-engineered intervertebral discs restore disc structure in animals but are about ten times softer than native tissue at
implantation and are expelled or crushed unless supported; in the only large-animal attempts, rigid polylactide cages fractured
and half of the constructs supported by flexible cages extruded within two weeks. A support that holds the construct for its
maturation period, then resorbs, must be fixed by shape and friction alone, since screws, keels or bone shaping would destroy
the endplate surface the disc must integrate with. Here we screen bioresorbable poly(L-lactide-co-caprolactone) cages with
hard and compliant phases in a validated finite-element model of the human C3-C4 segment, using the friction coefficient
required to prevent dislocation under six physiological pure moments with a follower load as the design metric. Across 148
human-designed configurations (133 unique), every evaluable cage needed a friction coefficient below 0.17, lateral bending
governing, well under the 0.3 available from a smooth wet polymer; the discriminating failure was instead compression of the
compliant phase, which exceeded an interim 15 % sustained limit in 62 designs and inverted the mesh of 12 under 100 N. **[TBD:
real-friction confirmation on 7 designs (queued); bench friction, modulus and compression-set data; free-form designs from the
evolutionary agent study.]** These results invert the usual cage design question: for a temporary resorbable support, the
constraint is not fixation but the durability of the compliant material that provides it.

## Main text outline (claims, evidence, figures)

| Section | Claim | Evidence today | Figure |
|---|---|---|---|
| Introduction | TE discs need temporary support; prior cages fractured or let constructs extrude; a fixation-free resorbable cage is a new device class | Bowles 2011, Moriguchi 2017, Mojica-Santiago 2018, Fidai 2024, Lintz 2021; Smit 2024 (optimised cages exist for fusion, none for dislocation) | - |
| Model and validation | C3-C4 FSU cut from a validated C0-C7 model reproduces Herron 2020 within 10 % (18/22 quantities), facet forces within 2 % | DECISIONS "Validation result"; `validation/results/comparison.json` | F1 |
| Protocol | Insertion by distraction (0.5-1.5 mm), release, 100 N follower load, six rotation-controlled windows to 1.5 N m; independent restarts per direction validated against the sequential run (<= 1 % flexion/LB, 4-9 % extension/AR explained by target-crossing sampling) | DECISIONS 2026-10-28/31; `results/method/split/p062__*.e04.json` | F4 |
| Metric | mu_req from a limit-surface analysis of both tied faces (squeeze-out mode) and a one-face slip bound; compression of the compliant phase (99th percentile) | `methods/e04_dislocation.py`, `e05_compression.py`; definition entries 2026-10-27 | - |
| Result 1 | Dislocation demand is low for every evaluable design (mu_req < 0.17; lateral bending governs; flexion/extension an order of magnitude lower) | `best_by_design_merged.json` (62 pass, 62 fail, 24 undetermined) | F2a, F7 |
| Result 2 | Compliant-phase compression discriminates: sustained > 15 % in 62 designs; E_soft is the dominant factor; 12 designs invert under the follower load at E_soft 1.5-4 MPa | `comp_by_design_merged.json`; F5 correlation | F2b, F3, F5 |
| Result 3 | Posterior push-out of a contour-matched cage without annular rim is 93 N peak at mu 0.35 (below the 135 N guard), ISO cycles complete for one design | proc_val pilots (DECISIONS 2026-10-31 01:40) | **[TBD figure: push-out curves]** |
| Result 4 **[TBD]** | Real friction reproduces the tied-interface ranking (7 designs queued: physrotFr_) | - | **[TBD]** |
| Result 5 **[TBD]** | Free-form designs from the four-agent evolutionary study extend the Pareto front biodisc volume vs fixation | engine not started (docs/DESIGNER_KICKOFF.md) | **[TBD]** |
| Discussion | For a temporary resorbable support, durability of the compliant phase (creep, compression set, hydrolysis in weeks) is the design constraint; implications for TE-disc trials; limitations (one subject, tied interface, quasi-static, no degradation) | literature sweep polymer (Smit 2008, Fernandez 2013, Duan 2021) | - |

## Methods subsections
1. Anatomical model and validation (Herron 2020 26-year-old model; FEBio 4.13 + cuDSS; mesh convergence; FSU vs full spine).
2. Cage families, material model (Gent, prestrain insertion), hard/soft PLCL properties and blend map (Duan 2021 sigmoid; stated as estimate).
3. Surgical sequence in the model (distraction, insertion, release, follower load) and the physiological protocol (rotation control to 1.5 N m; Wilke 1998 / Panjabi conventions; Anderst 2013 ICR).
4. Dislocation metric (limit-surface mu_req; one-face slip bound; rigid-body dislocation definition) and compression rule (99th percentile; interim limits and their basis).
5. Independent-window restarts and their validation; dynamic relaxation parameters (density 1e-6 t/mm3, rho_inf 0).
6. Design screen: Sobol + GP active learning over d, moduli, strengths, threshold; 150 points (133 unique; duplicate handling).
7. Post-processing provenance (git hashes, input hashes, invalid-run registers); scheduler and preflight.
8. **[TBD]** Real-friction simulations; push-out and ISO protocols; bench tests (friction, modulus, compression set); agent study governance (GOVERNANCE.md).

## Extended Data / Supplementary
- ED1 model geometry, mesh, material table; ED2 validation curves (moment-rotation C0-C7); ED3 insertion sequence and clamp force;
  ED4 split vs sequential for all shared windows; ED5 per-design table (148 rows: parameters, verdict, mu_req per direction,
  compression); ED6 failure modes of non-computable designs (element inversion maps) **[TBD images]**; ED7 compute and
  provenance (10,149 core-h, 996 GPU-h; invalid-run registers); ED8 sensitivity to friction coefficient and follower load **[TBD]**.
- Supplementary: DECISIONS.md as a dated decision log; code (OLD scripts h12-h32, EVO methods e02-e05); data (points.json, merged
  verdicts); FEBio patch set **[TBD: commit the 9 patched files]**.

## Gap to a Nature-tier claim (ranked by necessity)
1. **Real-friction confirmation** of the tied shortcut on >= 7 designs (queued today, ~1 day of compute) and a statement of the
   mu_req error vs the first-step sampling (interpolate to 1.5 N m). Without it the main metric is a surrogate.
2. **Bench material data for the printed PLCL grades**: modulus, yield, creep rupture (Eyring fit) of 85:15; compression set and
   relaxation of 50:50 at 15/25 % strain (1 h-28 d, 37 C wet); hydrolysis 0-26 weeks. Replaces the interim 15/25 % rule.
   Effort: 6-10 weeks of lab work.
2b. **Friction coefficient of printed PLCL vs wet endplate bone** (0.25-1 MPa); currently an assumption (0.3). 2-4 weeks.
3. **Degradation-aware fixation**: recompute mu_req and compression with soft-phase E reduced 50-90 % (literature: CL-rich PLCL
   half-life 18-32 days) and biodisc E rising; 1-2 days of compute.
4. **Patient variability**: repeat the passing designs on the 59- and 64-year-old Herron models (PI to supply); 2-3 days of
   compute per model plus mesh work.
5. **Bench or cadaver validation of dislocation**: push-out of printed prototypes in foam blocks (100 N preload, both
   directions) and one C3-C4 cadaver FSU test with cage tracking. Months; needed for the device claim.
6. **The AI-agent contribution**: free-form designs that beat the human families on the biodisc-volume vs fixation trade-off,
   with blinded verification (designer not started; ~100-140 h of integrator work before round 1, see DESIGNER_KICKOFF.md).
7. **Cyclic / fatigue and posterior hot spots** (Lintz fractures) for the final designs; ISO cycles completed for one design only.
8. Reproducibility package: FEBio build identity (4.13 + patches), container, data DOIs.

## Venue fit
- Nature / Nature Biomedical Engineering: needs items 1-6 (a validated in-silico claim plus bench data plus the AI-design result).
- Nature Communications / Science Advances: items 1-4 with the human-design screen as the main result and the agent framework as methods.
- npj Digital Medicine / Computer Methods in Biomechanics: the in-silico pipeline, credibility framework and agent governance.
- JOR Spine / J Biomech / Acta Biomaterialia: the present screen (Results 1-3) with the friction confirmation; fastest path to a
  first publication; cite the TE-disc precedents.
