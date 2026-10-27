"""Safety guard r0002: arithmetic behind the S2 (insertion) recommendation. No model files read.
Inputs (all from docs/DECISIONS.md 2026-10-26 'insertion feasibility' and DECISIONS_baseline_human_c34.md:46-47, 115-116):
  native gap inside the footprint: min (anterior) 2.95 mm, max (central-posterior) 5.30 mm
  final distraction d 0.5 / 1.0 / 1.5 mm; transient total distraction T over native (candidate limit 2.0 mm)
  hard PLCL 85:15: E 250 / 400 / 900 MPa, strength 15 / 25 / 40 MPa; inter-layer 0.8 x strength
Run: python3 work/agents/safety/s02_insertion_numbers.py  (prints a table; writes nothing)
"""
G_MIN, G_MAX = 2.95, 5.30

print("1) compression a contour-matched full-height column needs to pass the anterior gap at transient distraction T")
print("   strain = 1 - (G_MIN + T) / (G_MAX + d)")
for d in (0.5, 1.0, 1.5):
    for T in (d, 1.5, 2.0, 2.5, 3.0):
        if T < d:
            continue
        s = 1 - (G_MIN + T) / (G_MAX + d)
        print(f"   d {d:.1f}  T {T:.1f}  -> {100 * max(s, 0):5.1f} %")
print("   extra transient distraction for zero compression = G_MAX - G_MIN =", round(G_MAX - G_MIN, 2), "mm beyond d")

print("2) elastic strain limit of hard PLCL = strength / E (worst = low strength with high modulus)")
for S in (15, 25, 40):
    row = []
    for E in (250, 400, 900):
        row.append(f"E{E}: {100 * S / E:4.1f} % (inter-layer {100 * 0.8 * S / E:4.1f} %)")
    print(f"   strength {S}: " + "; ".join(row))

print("3) height of a rigid (hard) core that slides in at T with zero strain: H_core <= G_MIN + T (anterior gap)")
for T in (1.0, 1.5, 2.0):
    for d in (0.5, 1.0, 1.5):
        if T < d:
            continue
        print(f"   T {T:.1f}: core <= {G_MIN + T:.2f} mm; final gap max {G_MAX + d:.2f} mm at d {d:.1f} -> "
              f"{G_MAX + d - (G_MIN + T):.2f} mm must be compliant or left empty")
