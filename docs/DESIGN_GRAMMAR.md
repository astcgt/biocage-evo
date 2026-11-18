# Design Grammar v0 and Geometry Compiler (PI 2026-11-18)

What it is: a small JSON language for describing a cage as "where is solid" and "how hard is it there" on the 0.2 mm lattice
of the disc space, and a program (`ops/geom_compile.py`) that turns such a description into a model file the unchanged case
builder accepts. The lattice of the wanted distraction already exists in every h12 mesh file; the compiler only relabels it.
The grammar grows by request: anything it cannot express goes through the `custom` escape hatch, and every use of it is
logged as a grammar-extension request, so the grammar never caps an idea.

Acceptance (results/grammar/acceptance_2026-11-18.json): the six parametric design-A families written in this grammar
reproduce all 78 existing design-A mesh files element for element (region, phi, hard). A free-form demonstration design was
built by the unchanged h14. Verdict-level acceptance (a compiled family design gives the same verdict as its h12 twin)
waits for simulations.

What v0 cannot do (state it in a rejection, do not work around it silently): shapes outside the lattice (nothing can stick
out beyond the endplates or the footprint), faces that do not follow the endplates, more than two base materials,
contact on a recessed face (a solid column that stops short of an endplate has no contact surface - counted as C3 warning),
distraction values without a base mesh (a base mesh is made by running h12 once for that d).

## Language and checks (from the compiler's own documentation)
```
Specification (JSON):
  {"name": "...", "base_mesh": "<any design-A h12 mesh at the wanted d>", "fabrication": "interleave" | "mix",
   "solid": <region>, "phi": [{"where": <region>, "value": 0..1, "mode": "set" | "min" | "max"}, ...],   # start 1.0, rules in order
   "line_clip": N (optional: clip the print-line index to N-1 as h12 does), "mechanism": "...", "source": "..."}
Regions (boolean over the lattice elements; lengths in mm; x = anterior (+) / posterior (-), y = lateral, frame coordinates):
  {"op": "all"}
  {"op": "ring", "outer": a, "inner": b}            between the footprint outline inset by a and inset by b (a < b)
  {"op": "band", "axis": "x" | "y", "lo": v, "hi": w}   slab, coordinates relative to the footprint centroid
  {"op": "lines", "from": a, "to": b, "clip": N}      0.4 mm print lines a..b-1 counted from the outline (0 = outermost)
  {"op": "disk", "cx": .., "cy": .., "r": ..}       cylinder through the height, centre relative to the centroid
  {"op": "face", "side": "top" | "bottom" | "both", "lo": s0, "hi": s1}   distance to that endplate face in [s0, s1)
  {"op": "bars", "axis": "x" | "y", "pitch": p, "width": w, "phase": f}  periodic bars
  {"op": "union" | "intersect", "of": [...]}, {"op": "subtract", "a": .., "b": ..}, {"op": "not", "of": ..},
  {"op": "mirror_y", "of": ..}                      union with its mirror image about the sagittal plane
  {"op": "custom", "file": "x.py", "func": "f"}     escape hatch: f(fields) -> boolean array; every use is logged
Interleave realisation (as h12): an element is hard when (print-line index + layer) mod 4 < round(4 phi); the print-line
index is the 0.4 mm contour line counted from the footprint outline.
L0 checks by code (safety rules of docs/PLAN.md; the numbers marked provisional are owned by the safety guard):
  S3 one connected solid part (islands are removed and logged; refused when > 2 % of the solid voxels would change -
     provisional limit);
  S4 the void that touches BOTH endplates (one connected region) is >= 50 % of the disc-space volume (PLAN.md S4: 'void
     connected to both endplates, >= 50 %'); and that region meets EACH endplate over >= 25 % of the footprint (provisional number: a void that
     reaches an endplate only through a small hole does not let the endplate feed the biodisc); the total void is reported
     next to it (audit D-20261118-38: the first version tested the total void and only required some through-going void);
  S5 in-plane feature >= 0.4 mm (2 columns; provisional tolerance 2 % for staircase cells) and every solid element
     supported from the layer below by the element underneath or one of its four side neighbours (45 degrees in the axis
     directions; a diagonal step would be 55 degrees and is not accepted; provisional tolerance 0.5 %);
  C1 the part touches both endplates; C2 no face quad over a void column that h14 would still take as contact;
  C3 solid columns that do not reach a face are counted (no contact surface is defined there - warning).
```

## Examples
- families: `ops/geom_compile_test.py` (function family_spec) writes the six parametric families.
- control arm: `ops/grammar_random.py` draws random specifications (ring + struts / bars + material rules).
