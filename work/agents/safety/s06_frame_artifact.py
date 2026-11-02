"""Safety guard r0003: how much 'cage translation relative to C3' a cage that does not slip at all on C4 shows,
only because C3 rotates about the instantaneous centre of rotation (ICR, frame origin, snapshot/model/frame_c3c4.json).
Apparent translation of the cage centroid = 2 r sin(theta/2), r = distance centroid-ICR. Also the half value
(reference = mean of the C3 and C4 motions). Read-only. Run from repo root.
"""
import json, sys
import numpy as np
sys.path.insert(0, 'common')
from cage_geom import Endplates
ep = Endplates('snapshot/model/C34_fsu_refined.feb', 'snapshot/model/frame_c3c4.json')
c = ep.footprint.centroid
zc = float((ep.z_top(np.array([c.x]), np.array([c.y]))[0] + ep.z_bot(np.array([c.x]), np.array([c.y]))[0]) / 2)
r = float(np.hypot(c.x, zc))
out = dict(cage_centroid_frame=[c.x, c.y, zc], r_to_ICR_mm=r, rows=[])
for th in (3.0, 5.78, 8.0):
    t = np.radians(th)
    full = 2 * r * np.sin(t / 2)
    # x component of the apparent motion (vector r rotated about Y): dx = zc*sin(t) + c.x*(cos t - 1) (sign per direction)
    dx = zc * np.sin(t) + c.x * (np.cos(t) - 1)
    out['rows'].append(dict(rotation_deg=th, apparent_translation_vs_C3_mm=round(full, 3),
                            apparent_AP_component_mm=round(abs(dx), 3), with_mean_C3C4_reference_mm=round(full / 2, 3)))
json.dump(out, open('work/agents/safety/s06_frame_artifact.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
