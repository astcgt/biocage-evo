"""Safety guard r0003: native C3-C4 gap profile along the midline (Y=0) and at Y=+/-3 mm, from the anterior outline
edge to the posterior outline edge (frame: +X anterior, docs: snapshot/model/frame_c3c4.json). Read-only.
Purpose: is there a posterior 'lip' (gap closing toward the canal) that a hard core inserted from anterior would hit?
Run from repo root: python work/agents/safety/s04_midline_profile.py -> s04_midline_profile.json
"""
import json, sys
import numpy as np
sys.path.insert(0, 'common')
from cage_geom import Endplates
import shapely.geometry as sg
ep = Endplates('snapshot/model/C34_fsu_refined.feb', 'snapshot/model/frame_c3c4.json')
ox0, _, ox1, _ = ep.outline.bounds
fx0, _, fx1, _ = ep.footprint.bounds
out = dict(outline_x=[ox0, ox1], footprint_x=[fx0, fx1], profiles={})
for yy in (0.0, -3.0, 3.0):
    rows = []
    for x in np.arange(ox0 + 0.05, ox1, 0.25):
        if not ep.outline.contains(sg.Point(x, yy)):
            continue
        g = float(ep.z_top(np.array([x]), np.array([yy]))[0] - ep.z_bot(np.array([x]), np.array([yy]))[0])
        rows.append([round(float(x), 2), round(g, 3), bool(ep.footprint.contains(sg.Point(x, yy)))])
    out['profiles'][f'y{yy:+.0f}'] = rows
    fp = [r for r in rows if r[2]]
    gmax = max(r[1] for r in fp); xmax = [r[0] for r in fp if r[1] == gmax][0]
    post = [r for r in fp if r[0] < xmax]
    out['profiles'][f'y{yy:+.0f}_summary'] = dict(
        footprint_ant_edge_gap=fp[-1][1], footprint_post_edge_gap=fp[0][1], footprint_max_gap=gmax, x_of_max=xmax,
        posterior_closure_in_footprint=round(gmax - fp[0][1], 3),
        outline_post_edge_gap=rows[0][1], outline_ant_edge_gap=rows[-1][1])
json.dump(out, open('work/agents/safety/s04_midline_profile.json', 'w'), indent=1)
for k, v in out['profiles'].items():
    if k.endswith('summary'):
        print(k, v)
print('midline y0:', [(r[0], r[1]) for r in out['profiles']['y+0']][::2])
