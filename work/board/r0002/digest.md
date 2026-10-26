# Round 2 digest, roles: verifier, safety guard, red team (designer not started; no designs yet)
Read first: work/board/r0002/pi_updates.md, docs/DECISIONS.md (last entries), work/board/r0001/*.json and work/findings/F-0001..F-0010.
Since round 1: repository split (paths changed, see README.md); physio load-curve bug fixed in the old study (reruns in the old repo,
al_v2/physio_fix); PI: posterior <= 0.5 mm and >= 135 N, mu 0.3 (0.2 / 0.45), S4 50 %, support period >= 16 weeks, no bone shaping of the
endplates (soft tissue only), any feasible insertion method; contour-matched cages need +2.35 mm transient distraction or 35-41 %
compression (hard PLCL yields at ~5 %).
Tasks this round:
- verifier: check whether round-1 problems (F-0003 friction anchor reset, F-0004 Newton solver without a gate pass) are fixed in gpufe/;
  propose the exact gate for 'no spurious ratcheting' (cyclic load, stick region must not creep).
- safety guard: turn S2 (insertion) into a measurable rule given 'no bone shaping'; recommended transient-distraction limit with sources.
- red team: attack the insertion-feasibility analysis (docs/DECISIONS.md 2026-10-26) and the repository split (anything lost, broken
  paths, data provenance gaps, snapshot vs old repo).
Your round number is 2. Write your verdict to work/board/r0002/<role>.json.
