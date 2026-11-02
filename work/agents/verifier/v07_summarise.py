"""Verifier r0003: summarise V07 runs (v07_stick_creep_newton_r*_patched.json) -> v07_summary.json / v07_summary.md.
Hold creep = plate x(1.0) - x(0.5) under constant Fn and Ft (Coulomb answer: 0). usage: python v07_summarise.py"""
import json, os, glob
HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for f in sorted(glob.glob(os.path.join(HERE, 'v07_stick_creep_newton_r*_patched.json'))):
    for r in json.load(open(f)):
        g = r['gpu_rows']; hold = [q for q in g if q['t'] > 0.5 + 1e-9]
        rows.append(dict(ratio=r['ratio_Ft_over_muFn'], E=r['E_up'], n=r['n_increments'], gpu_x05_mm=r['gpu_x_t05'],
                         gpu_hold_creep_mm=r['gpu_creep_hold'], gpu_hold_increments=len(hold),
                         gpu_min_stick_in_hold=min((q['stick'] for q in hold), default=None),
                         gpu_last_increment_dx_mm=(g[-1]['x'] - g[-2]['x']) if len(g) > 1 else None,
                         gpu_max_iters=max(q['iters'] for q in g), gpu_all_converged=r['gpu_all_converged'],
                         febio_normal=r['febio_normal'], febio_x05_mm=None if r['febio_x_t05'] is None else r['febio_x_t05'] - 2.0,
                         febio_hold_creep_mm=r['febio_creep_hold']))
fmt = lambda v: 'n/a' if v is None else (f'{v:.4g}' if isinstance(v, float) else str(v))
txt = ('V07 force hold (block pair mu 0.3, Fn 4 N, Ft = ratio x mu Fn, t 0.5-1.0 constant load; GPU Newton HEAD 1f09ae2 + dirty '
       'tree, run with V07_PATCH=1 so that equilibrium-start increments do not crash, see B2). Coulomb answer: hold creep 0. '
       + '; '.join(f"ratio {r['ratio']} E {r['E']:g} n {r['n']}: GPU x(0.5) {fmt(r['gpu_x05_mm'])} mm, hold creep {fmt(r['gpu_hold_creep_mm'])} mm "
                   f"in {r['gpu_hold_increments']} increments (min stick {fmt(r['gpu_min_stick_in_hold'])}, last-increment dx {fmt(r['gpu_last_increment_dx_mm'])}); "
                   f"FEBio x(0.5) {fmt(r['febio_x05_mm'])} mm, hold creep {fmt(r['febio_hold_creep_mm'])} mm" for r in rows))
note = (' | ratio 0.9 E 400 n 10 (patched): RuntimeError at t 0.6876 in the hold, max_newton 60 x 7 tries, residual 1.55e-7 N (4e-8 of Fn): probably stick / slip switching between iterations (not isolated), the displacement norm never meets dtol 1e-6 (v07_r0.9_patched.log); E 400 n 20 / 40 therefore not run. Unpatched runs: RuntimeError in the hold once all nodes stick (residual ~6e-13 N; v07_r0.5.log, v07_r0.9.log).')
txt += note
md_note = note
json.dump(dict(text=txt, rows=rows), open(os.path.join(HERE, 'v07_summary.json'), 'w'), indent=1)
md = ['# V07 force-hold creep (verifier r0003)', '', 'Script: v07_stick_creep.py; summary: v07_summarise.py. Coulomb answer: hold creep 0, independent of n.', '',
      '| Ft/(mu Fn) | E MPa | n | GPU x(0.5) mm | GPU hold creep mm | hold incr | min stick | GPU last dx mm | FEBio x(0.5) mm | FEBio hold creep mm |', '|' + '---|' * 10]
md += [f"| {r['ratio']} | {r['E']:g} | {r['n']} | {fmt(r['gpu_x05_mm'])} | {fmt(r['gpu_hold_creep_mm'])} | {r['gpu_hold_increments']} | {fmt(r['gpu_min_stick_in_hold'])} | "
       f"{fmt(r['gpu_last_increment_dx_mm'])} | {fmt(r['febio_x05_mm'])} | {fmt(r['febio_hold_creep_mm'])} |" for r in rows]
md += ['', md_note]
open(os.path.join(HERE, 'v07_summary.md'), 'w').write('\n'.join(md) + '\n')
print(txt)
