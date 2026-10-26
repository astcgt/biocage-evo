# BIOCAGE free-form evolution (biocage-evo)

Free-form, evolution-style design of a PLCL-only cervical (C3-C4) cage that gives temporary support and fixation while a
tissue-engineered disc matures, with four independent AI roles that supervise each other (designer, verifier, safety
guard, red team). Split from `biocage-stimulation-test-1` (commit in `snapshot/MANIFEST.json`), history of the moved files kept.

| Folder | What |
|---|---|
| `docs/` | `PLAN.md` (idea, constraints S1-S9, evaluation levels), `GOVERNANCE.md` (how the roles work), `DECISIONS.md` (PI decisions for this repo), `METHODS_COMPARISON.md`, `ISSUES.md`, `PRIOR_FAILURES_Lintz2021.md`, `DECISIONS_baseline_human_c34.md` (read-only copy of the model decisions inherited from the old study) |
| `gpufe/` | GPU finite-element solver (reads FEBio 2.5 files; Newton + cuDSS, Coulomb friction) and its credibility gates |
| `methods/` | friction-check methods (e02) |
| `roles/` | role prompts and `run_roles.sh` (one headless Claude process per role, own write permissions) |
| `work/` | role workspaces (`agents/`), shared board (`board/rNNNN/`), red-team findings, change requests, design archive |
| `results/` | verification reports and method results |
| `common/`, `l2_febio/` | code copied from the old repo (endplate geometry, xplt reader, FEBio case builder) for the full-FEBio level; `h24_preflight.py` still has old-repo paths and is not wired yet |
| `snapshot/` | model data copied from the old repo (local only, not in git) + `MANIFEST.json` with source paths and SHA-256 |

External tools (FEBio binary, MKL, FEBio source) are referenced in `config.json`.
