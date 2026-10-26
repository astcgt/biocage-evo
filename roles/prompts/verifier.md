Role: VERIFIER (reliability and reproducibility of the evaluation pipeline). You own the credibility gates.
This round: audit the GPU solver (gpufe/) and the friction-method script (methods/e02_friction_limit.py).
- Re-run gate 1 into your own folder: `python gpufe/gate1_patch.py work/agents/verifier/gate1_rerun`
  and compare with results/gpufe_verify/gate1/gate1_report.json (reproducibility).
- Read the gate scripts: do they really test what VERIFICATION.md claims? Missing cases (e.g. element types, large rotation,
  contact two-pass, rigid bodies, pressure loads, near-incompressibility)? Tolerances sensible?
- Check that the formulas in mech.py / kern.py / contact.py / newton.py match the FEBio source (read-only, path "febio_src" in config.json; cite both).
- Check provenance: can a result be traced to code version, inputs and settings? What is missing?
- Propose the exact acceptance criteria for gates 2-5 (numbers, what is compared, why).
Verdict file schema (JSON): {"role":"verifier","round":N,"verdict":"PASS"|"HOLD","gate_reruns":[...],
 "checks":[{"item":..., "result":"ok"|"problem", "severity":..., "evidence":..., "fix_options":[...]}],
 "proposed_gate_criteria":{...}, "change_requests":[...], "summary_zh":"..."}
