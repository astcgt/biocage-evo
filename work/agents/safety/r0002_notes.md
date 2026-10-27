# Safety guard r0002 - working notes

Python is still not executable for this role (Bash `python3 ...` -> "requires approval", 2026-10-27). The script
`s02_insertion_numbers.py` (this folder) contains the arithmetic; the numbers below were computed by hand from it and
can be re-checked by running it.

## N1 S2 compression of a contour-matched column (strain = 1 - (2.95 + T) / (5.30 + d))
Inputs: native gap in footprint min 2.95 / max 5.30 mm (DECISIONS.md, 2026-10-26 insertion feasibility).
| d | T = d | T 1.5 | T 2.0 | T 2.5 | T 3.0 |
|---|---|---|---|---|---|
| 0.5 | 40.5 % | 23.3 % | 14.7 % | 6.0 % | 0 |
| 1.0 | 37.3 % | 29.4 % | 21.4 % | 13.5 % | 5.6 % |
| 1.5 | 34.6 % | 34.6 % | 27.2 % | 19.9 % | 12.5 % |
T = d column reproduces the analyst's 35-41 % (DECISIONS.md) -> inputs consistent.

## N2 Elastic strain limit of hard PLCL 85:15 = strength / E (DECISIONS_baseline_human_c34.md:46, 115-116)
| strength \ E | 250 | 400 | 900 MPa |
|---|---|---|---|
| 15 MPa | 6.0 % | 3.75 % | 1.67 % |
| 25 MPa | 10.0 % | 6.25 % | 2.78 % |
| 40 MPa | 16.0 % | 10.0 % | 4.44 % |
Inter-layer (x 0.8): worst corner 1.33 %. The PLAN.md S2 default 3 % exceeds 3 of 9 corners (15/900, 25/900 and
inter-layer 15/400 = 3.0 %). Recommendation: stress-based rule (von Mises <= 0.5 x local LOW strength set) or strain <= 1.5 %.

## N3 Hard core envelope at transient distraction T (zero strain): core height <= 2.95 + T
T 2.0: core <= 4.95 mm; the tallest final column (5.30 + d) then needs 0.85 / 1.35 / 1.85 mm of compliant height
reduction for d 0.5 / 1.0 / 1.5. With compliant strain <= 40 %, compliant thickness t >= excess / 0.4 = 2.1 / 3.4 / 4.6 mm,
so the hard part of that column <= 3.7 / 2.9 / 2.2 mm (column height 5.8 / 6.3 / 6.8 mm).
Consequence: in the tallest (central-posterior) region the designs will be mostly soft or void; void there also serves S4.

## N4 Insertion reverses into expulsion
A shape that passes the anterior gap at T also leaves anteriorly at T. Posteriorly, the native midline gap falls from
~5.4 (mid) to 4.1 mm (posterior) (DECISIONS_baseline_human_c34.md:15). A hard core cut to the anterior envelope
(<= 4.95 mm at T 2.0) vs final posterior gap 4.1 + d = 4.6 mm at d 0.5 -> only ~0.35 mm geometric overlap blocks the
posterior path (midline values; full 3-D check needed). So S2-compliant designs lose much of the concavity interlock
that the analyst counted on; posterior safety relies on friction + clamp + compliant parts. S9 at mu 0.2 is therefore
the binding check for the cord.

## N5 Literature checked this round
- Hsueh LL et al. 2023 Sci Rep (doi:10.1038/s41598-023-44998-4; Europe PMC abstract read): over-distraction =
  postop - preop index disc height >= 2 mm (FINAL, not transient); subsidence 47 vs 31 %, radiological ASP 48 vs 15 %.
  Volume/page number not verified.
- J Korean Neurosurg Soc 2013 (koreascience JAKO201334460141077), 'Vertebral distraction during ACDF causes postoperative
  neck pain': Caspar torque > 6 kgf cm -> more posterior neck pain day 1 / 3 (n 24); authors not verified.
- Rancourt et al. 1990 J Biomed Mater Res 24:1503 (abstract read): porous metal and smooth stainless steel on tibial
  cancellous bone mu 0.3-1.3, smooth lowest.
- Damm, Morlock, Bishop 2015 J Biomech 48:3517 (abstract): polished surface mu low and stress-independent (numbers not read).
- Europe PMC search ("friction coefficient" AND PEEK/PLA/PLLA AND bone AND cage/endplate/trabecular), 40 hits, 2026-10-27:
  no direct polymer-on-bone measurement; all FE studies assume a value.
- PEEK untreated vs sandblasted 0.14 / 0.25 against a non-bone counterface (search summary, source not opened: unverified).
