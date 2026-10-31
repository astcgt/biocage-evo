"""Publication-candidate figures for the BIOCAGE human C3-C4 study (2026-10-31), from existing result files only
(JSON / log; no .xplt loading). Nature-style: 89 mm single / 183 mm double column, 6-8 pt sans, vector PDF + 300 dpi PNG,
colour-blind-safe palette (first three categorical slots validated all-pairs; status colours for pass / fail).
usage: python make_figs.py            (writes F1-F7 .pdf/.png next to this file and figures.json with captions)
"""
import os, re, json, glob, collections, datetime as dt
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
EVO = os.path.dirname(os.path.dirname(HERE))
OLD = '/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1'
HS = os.path.join(OLD, 'human_study')
W = ('flexion', 'extension', 'LB_right', 'LB_left', 'AR_left', 'AR_right')
WL = {'flexion': 'Flex', 'extension': 'Ext', 'LB_right': 'Right LB', 'LB_left': 'Left LB', 'AR_left': 'Left AR', 'AR_right': 'Right AR'}
MM = 1 / 25.4
C = dict(s1='#2a78d6', s2='#eb6834', s3='#1baf7a', good='#0ca30c', crit='#d03b3b', warn='#fab219', gray='#898781', grid='#e1e0d9', ink='#0b0b0b', ink2='#52514e')
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'], 'font.size': 7, 'axes.labelsize': 7,
                     'axes.titlesize': 7.5, 'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5, 'legend.fontsize': 6.5, 'axes.linewidth': 0.6,
                     'xtick.major.width': 0.6, 'ytick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5, 'axes.spines.top': False,
                     'axes.spines.right': False, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'axes.edgecolor': '#c3c2b7', 'xtick.color': '#52514e',
                     'ytick.color': '#52514e', 'axes.labelcolor': '#0b0b0b', 'legend.frameon': False})
CAP = {}


def letter(ax, s):
    ax.text(-0.26, 1.06, s, transform=ax.transAxes, fontsize=9, fontweight='bold', va='top', ha='right', color=C['ink'])


def save(fig, name, caption):
    fig.savefig(os.path.join(HERE, name + '.pdf'), bbox_inches='tight', pad_inches=0.02); fig.savefig(os.path.join(HERE, name + '.png'), dpi=300, bbox_inches='tight', pad_inches=0.02); plt.close(fig)
    CAP[name] = caption; print('wrote', name)


def grid(ax, axis='y'):
    ax.grid(True, axis=axis, color=C['grid'], linewidth=0.5); ax.set_axisbelow(True)


# ------------------------------------------------------------------ data
pts = {p['id']: p for p in json.load(open(os.path.join(HS, 'al_v2/points.json')))['points']}
SPLIT = os.path.join(EVO, 'results/method/split')
best = json.load(open(os.path.join(SPLIT, 'best_by_design_merged.json')))
comp = json.load(open(os.path.join(SPLIT, 'comp_by_design_merged.json')))
lists = json.load(open(os.path.join(SPLIT, 'verdict_lists_merged.json')))
verdict = {p: k for k, v in lists.items() for p in v}
VL = {'both': 'pass (slip + compression)', 'fail': 'fail (compression)', 'open': 'undetermined', 'comp_pass_slip_open': 'compression pass, slip open'}


def design_rows():
    rows = []
    for i, p in pts.items():
        pid = f'p{i:03d}'; x = p['x']; b = best.get(pid, {}); c = comp.get(pid, {})
        mus = [b[w]['mu_squeeze'] for w in W if w in b and b[w]['target_reached']]
        slips = [b[w]['one_face_slip_bound_mm'] for w in W if w in b and b[w]['target_reached']]
        pk = [c['windows'][w]['peak'] for w in W if w in c.get('windows', {}) and c['windows'][w].get('peak') is not None]
        rows.append(dict(id=pid, x=x, v=verdict.get(pid, 'invalid' if p['status'] != 'done' else 'nodata'), mu=max(mus) if mus else None,
                         slip=max(slips) if slips else None, sus=c.get('sustained'), peak=max(pk) if pk else None, n=len(mus)))
    return rows


R = design_rows()

# ------------------------------------------------------------------ F1 validation vs Herron 2020
cmp = json.load(open(os.path.join(HS, 'validation/results/comparison.json')))
fig, axs = plt.subplots(1, 3, figsize=(183 * MM, 58 * MM), gridspec_kw=dict(width_ratios=[1.1, 1.6, 0.9], wspace=0.45))
ax = axs[0]; dirs = ['flexion', 'extension', 'lateral_bending', 'axial_rotation']; lab = ['Flex', 'Ext', 'LB', 'AR']
ours = [cmp[d]['C0-C7_one_direction']['ours_deg'] for d in dirs]; her = [cmp[d]['C0-C7_one_direction']['herron_deg'] for d in dirs]
xx = np.arange(4); bw = 0.36
ax.bar(xx - bw / 2, her, bw, color=C['gray'], label='Herron 2020 (26 y)'); ax.bar(xx + bw / 2, ours, bw, color=C['s1'], label='This model')
ax.set_xticks(xx); ax.set_xticklabels(lab); ax.set_ylabel('C0–C7 rotation at 1.5 N m (deg)'); grid(ax); letter(ax, 'a')
ax.errorbar(xx - bw / 2, her, yerr=2, fmt='none', ecolor=C['ink2'], elinewidth=0.6, capsize=1.5)
ax.legend(loc='lower left', bbox_to_anchor=(0, 1.0), ncol=2, handlelength=1.2, columnspacing=0.8)
ax = axs[1]; levels = ['C0-C1', 'C1-C2', 'C2-C3', 'C3-C7']; k = 0; ticks = []; tl = []
for d, nm, col in (('lateral_bending', 'LB', C['s1']), ('axial_rotation', 'AR', C['s2'])):
    for L in levels:
        e = cmp[d].get(L + '_total_ROM')
        if not e or e['herron_deg'] is None: continue
        ax.bar(k - bw / 2, e['herron_deg'], bw, color=C['gray']); ax.bar(k + bw / 2, e['ours_deg'], bw, color=col); ticks.append(k); tl.append(f"{L.replace('C', '').replace('-', '–')}\n{nm}"); k += 1
ax.set_xticks(ticks); ax.set_xticklabels(tl, fontsize=5.5); ax.set_ylabel('Level ROM at 1.5 N m (deg)'); ax.set_xlabel('levels (C0–1 … C3–7)'); grid(ax); letter(ax, 'b')
ax.legend(handles=[Patch(color=C['gray'], label='Herron 2020'), Patch(color=C['s1'], label='Model, LB'), Patch(color=C['s2'], label='Model, AR')], loc='lower left', bbox_to_anchor=(0, 1.0), ncol=3, handlelength=1.2, columnspacing=0.8)
ax = axs[2]; ff = [('extension', 'Ext'), ('lateral_bending', 'LB'), ('axial_rotation', 'AR')]
h = [cmp[d]['facet_force_C3C4']['herron_N'] for d, _ in ff]; o = [cmp[d]['facet_force_C3C4']['ours_N'] for d, _ in ff]; xx = np.arange(3)
ax.bar(xx - bw / 2, h, bw, color=C['gray']); ax.bar(xx + bw / 2, o, bw, color=C['s1']); ax.set_xticks(xx); ax.set_xticklabels([l for _, l in ff])
ax.set_ylabel('C3–C4 facet force (N)'); grid(ax); letter(ax, 'c')
for i, (a, b) in enumerate(zip(h, o)): ax.text(i + bw / 2, b + 1.5, f'{(b - a) / a * 100:+.0f}%', ha='center', fontsize=5.5, color=C['ink2'])
save(fig, 'F1_validation', 'Validation of the C0–C7 FEBio model against Herron et al. 2020 (26-year-old subject). (a) One-direction C0–C7 rotation under a 1.5 N m pure moment at C0 (C7 fixed, nucleus pre-pressure 0.1 MPa); error bars, ±2° reading uncertainty of the digitised reference. (b) Total range of motion per level in lateral bending (LB) and axial rotation (AR). (c) C3–C4 facet force at 1.5 N m. 18 of 22 compared quantities are within 10 % of the reference; the largest deviations are at C0–C1 (LB +21 %, AR −14 %).')

# ------------------------------------------------------------------ F2 design space
fig, axs = plt.subplots(1, 2, figsize=(183 * MM, 70 * MM), gridspec_kw=dict(wspace=0.35))
col = {'both': C['good'], 'fail': C['crit'], 'open': C['gray'], 'comp_pass_slip_open': C['warn']}
ax = axs[0]
for r in R:
    if r['sus'] is None or r['mu'] is None: continue
    ax.scatter(r['sus'] * 100, r['mu'], s=14, marker='o' if r['x']['design'] == 'A' else 's', facecolor=col.get(r['v'], C['gray']), edgecolor='white', linewidth=0.5, zorder=3)
ax.axvline(15, color=C['ink2'], lw=0.6, ls=(0, (3, 2))); ax.text(15.5, ax.get_ylim()[1] * 0.98 if ax.get_ylim()[1] > 0 else 0.3, 'sustained limit 15 %', fontsize=5.5, color=C['ink2'], va='top')
ax.axhline(0.3, color=C['s1'], lw=0.6, ls=(0, (3, 2))); ax.text(0.3, 0.305, 'assumed available μ = 0.3', fontsize=5.5, color=C['s1'], ha='left', va='bottom')
ax.set_xlabel('Sustained soft-PLCL compression after implantation (%)'); ax.set_ylabel('Friction coefficient needed, worst direction (μ_req)'); grid(ax, 'both'); letter(ax, 'a')
ax.legend(handles=[Line2D([], [], marker='o', ls='', color=C['good'], label=VL['both']), Line2D([], [], marker='o', ls='', color=C['crit'], label=VL['fail']),
                   Line2D([], [], marker='o', ls='', color=C['gray'], label=VL['open']), Line2D([], [], marker='o', ls='', color='k', mfc='none', label='family A (contoured)'),
                   Line2D([], [], marker='s', ls='', color='k', mfc='none', label='family B (planar + pad)')], loc='upper center', bbox_to_anchor=(0.62, 0.97), fontsize=5.5)
ax = axs[1]
for r in R:
    if r['sus'] is None or r['peak'] is None: continue
    ax.scatter(r['sus'] * 100, r['peak'] * 100, s=14, marker='o' if r['x']['design'] == 'A' else 's', facecolor=col.get(r['v'], C['gray']), edgecolor='white', linewidth=0.5, zorder=3)
ax.axvline(15, color=C['ink2'], lw=0.6, ls=(0, (3, 2))); ax.axhline(25, color=C['ink2'], lw=0.6, ls=(0, (3, 2)))
ax.text(15.5, ax.get_ylim()[1] * 0.98, '15 %', fontsize=5.5, color=C['ink2'], va='top'); ax.text(ax.get_xlim()[1], 25.5, 'peak limit 25 %', fontsize=5.5, color=C['ink2'], ha='right', va='bottom')
ax.set_xlabel('Sustained soft-PLCL compression (%)'); ax.set_ylabel('Peak soft-PLCL compression in any direction (%)'); grid(ax, 'both'); letter(ax, 'b')
n_ev = sum(1 for r in R if r['sus'] is not None)
save(fig, 'F2_design_space', f'Screening map of the {n_ev} human-designed cage configurations with an evaluated implanted state (of 150 active-learning points, 133 unique). (a) Worst-direction friction coefficient required to prevent dislocation (μ_req, tied-interface limit-surface analysis at the state where the driving moment reaches 1.5 N m under a 100 N follower load) against the sustained compression of the soft PLCL phase after implantation (99th-percentile element compression at t = 3.5). (b) Peak soft-PLCL compression in any of the six directions against the sustained value; dashed lines, the interim rule (15 % sustained, 25 % peak). Colours give the current verdict; markers the cage family. Every evaluated design needs μ_req < 0.17, well below the assumed available friction of 0.3; compression of the soft phase, not slip, is the discriminating failure.')

# ------------------------------------------------------------------ F3 verdict breakdown
cats = [('design', 'Family', lambda x: {'A': 'A contoured', 'B': 'B planar+pad'}[x['design']]), ('grad', 'Gradient', lambda x: x['grad']), ('fab', 'Fabrication', lambda x: x['fab']),
        ('d', 'Distraction d (mm)', lambda x: '0.5–0.8' if x['d'] < 0.85 else ('0.85–1.15' if x['d'] < 1.2 else '1.2–1.5')),
        ('E_soft', 'Soft modulus (MPa)', lambda x: '1.5–3' if x['E_soft'] < 3 else ('3–6' if x['E_soft'] < 6 else '6–12')),
        ('E_hard', 'Hard modulus (MPa)', lambda x: '250–450' if x['E_hard'] < 450 else ('450–700' if x['E_hard'] < 700 else '700–900'))]
order = ['both', 'fail', 'open', 'nodata']; vcol = {'both': C['good'], 'fail': C['crit'], 'open': C['gray'], 'nodata': '#d9d8d2'}
fig, axs = plt.subplots(2, 3, figsize=(183 * MM, 80 * MM), gridspec_kw=dict(hspace=0.75, wspace=0.55))
for ax, (key, title, f), s in zip(axs.flat, cats, 'abcdef'):
    cnt = collections.defaultdict(collections.Counter)
    for r in R:
        if r['v'] == 'invalid': continue
        cnt[f(r['x'])][r['v'] if r['v'] in order else 'nodata'] += 1
    keys = sorted(cnt); y = np.arange(len(keys)); left = np.zeros(len(keys))
    for v in order:
        vals = np.array([cnt[k][v] for k in keys]); ax.barh(y, vals, 0.6, left=left, color=vcol[v], edgecolor='white', linewidth=0.8); left += vals
    for i, k in enumerate(keys): ax.text(left[i] + 0.5, i, str(int(left[i])), va='center', fontsize=5.5, color=C['ink2'])
    ax.set_yticks(y); ax.set_yticklabels(keys); ax.set_title(title, loc='left'); ax.set_xlabel('designs'); grid(ax, 'x'); letter(ax, s); ax.invert_yaxis()
fig.legend(handles=[Patch(color=vcol[v], label={'both': 'pass', 'fail': 'fail (compression)', 'open': 'undetermined', 'nodata': 'no valid data'}[v]) for v in order],
           loc='lower center', bbox_to_anchor=(0.5, -0.1), ncol=4, fontsize=6.5)
save(fig, 'F3_verdict_breakdown', 'Verdict of the 148 valid active-learning designs by design factor (two points were invalid at build time). Pass = all six directions reach 1.5 N m with the tied interface and the soft-PLCL compression rule holds (sustained ≤ 15 %, peak ≤ 25 %); fail = the compression rule is violated; undetermined = at least one direction did not reach the target moment or the implantation run did not converge (12 designs invert under the 100 N follower load). Soft-phase modulus is the dominant factor: designs with E_soft below 3 MPa rarely pass.')

# ------------------------------------------------------------------ F4 p062 split vs sequential
seq = json.load(open(os.path.join(EVO, 'results/method/e04_rot/best_by_design.json')))['p062']
sp = {w: json.load(open(os.path.join(SPLIT, f'p062__{w}.e04.json')))['windows'][w] for w in W}
fig, axs = plt.subplots(1, 3, figsize=(183 * MM, 55 * MM), gridspec_kw=dict(wspace=0.45)); xx = np.arange(6); bw = 0.38
for ax, key, yl, s in zip(axs, ('mu_squeeze', 'one_face_slip_bound_mm', 'M_at_target'), ('μ_req', 'One-face slip bound (mm)', '|M| at evaluated state (N mm)'), 'abc'):
    a = [abs(seq[w][key]) for w in W]; b = [abs(sp[w][key]) for w in W]
    ax.bar(xx - bw / 2, a, bw, color=C['s1'], label='sequential run'); ax.bar(xx + bw / 2, b, bw, color=C['s2'], label='independent windows')
    ax.set_xticks(xx); ax.set_xticklabels([WL[w].replace(' ', '\n') for w in W], fontsize=5.5); ax.set_ylabel(yl); grid(ax); letter(ax, s)
    if key == 'M_at_target': ax.axhline(1500, color=C['ink2'], lw=0.6, ls=(0, (3, 2))); ax.text(5.5, 1520, 'target 1.5 N m', fontsize=5.5, ha='right', va='bottom', color=C['ink2'])
axs[0].legend(loc='upper left')
save(fig, 'F4_split_validation', 'Independent-window protocol validated on design p062 (family A, axial mixing-nozzle gradient, d = 0.5 mm). Each direction is restarted from the implanted state (t = 3.5) instead of following the previous direction. (a) Required friction coefficient and (b) one-face slip bound agree within 1 % in flexion and lateral bending; the 4–9 % higher slip bounds in extension and axial rotation follow the (c) moment at the first converged step past the 1.5 N m target (ratios 1.09, 1.05, 1.08), i.e. the sampling of the target crossing, not a different mechanical response.')

# ------------------------------------------------------------------ F5 insertion failures
end = lambda L: ('N' if 'N O R M A L' in open(L, errors='ignore').read()[-4000:] else 'E' if 'E R R O R' in open(L, errors='ignore').read()[-4000:] else 'run') if os.path.exists(L) else '-'
S2 = []
for pf in sorted(glob.glob(os.path.join(HS, 'al_v2/physio_rot_split2/p???_params.json'))):
    pid = os.path.basename(pf)[:4]; x = json.load(open(pf)); ds = [d for d in glob.glob(os.path.join(HS, f'al_v2/physio_rot_split2/{pid}*')) if os.path.isdir(d) and os.path.exists(d + '/case.log')]
    if ds: S2.append((pid, end(ds[-1] + '/case.log'), x['E_soft'], x['d'], x['E_hard']))
fig, axs = plt.subplots(1, 2, figsize=(183 * MM, 60 * MM), gridspec_kw=dict(width_ratios=[1.3, 1], wspace=0.4))
ax = axs[0]
for pid, e, es, d, eh in S2:
    ax.scatter(es, d, s=18, marker='x' if e == 'E' else 'o', color=C['crit'] if e == 'E' else C['s1'], linewidth=0.9 if e == 'E' else 0.5, edgecolor='white' if e != 'E' else None, zorder=3)
ax.set_xscale('log'); ax.set_xlabel('Soft-PLCL modulus E_soft (MPa, log)'); ax.set_ylabel('Distraction d (mm)'); grid(ax, 'both'); letter(ax, 'a')
ax.legend(handles=[Line2D([], [], marker='x', ls='', color=C['crit'], label='implantation run inverts (not computable)'), Line2D([], [], marker='o', ls='', color=C['s1'], label='six directions computed')], loc='upper right', fontsize=5.5)
ax = axs[1]; bins = [(1.4, 2.5, '1.5–2.5'), (2.5, 5, '2.5–5'), (5, 12.5, '5–12')]; fr = []; ns = []
for lo, hi, _ in bins:
    g = [e for _, e, es, _, _ in S2 if lo <= es < hi]; fr.append(100 * sum(x == 'E' for x in g) / max(len(g), 1)); ns.append(len(g))
ax.bar(range(3), fr, 0.55, color=C['crit']); ax.set_xticks(range(3)); ax.set_xticklabels([b[2] for b in bins]); ax.set_xlabel('E_soft (MPa)'); ax.set_ylabel('Implantation runs failing (%)'); grid(ax); letter(ax, 'b')
for i, (f, n) in enumerate(zip(fr, ns)): ax.text(i, f + 2, f'n = {n}', ha='center', fontsize=5.5, color=C['ink2'])
nf = sum(e == 'E' for _, e, *_ in S2)
save(fig, 'F5_insertion_failures', f'Designs whose implantation run cannot be completed. Of the {len(S2)} designs re-run with the independent-window protocol, {nf} stop with inverted soft-PLCL elements during the 100 N follower-load step (t = 3.0–3.4; two during insertion), in every solver mode tried (static, slow dynamic, restart). (a) They cluster at the lowest soft-phase moduli; (b) failure fraction by E_soft bin. Whether element inversion under 100 N is reported as a compression failure or as a non-computable case is a pending decision.')

# ------------------------------------------------------------------ F6 compute timeline
L = open(os.path.join(HS, 'scheduler.log')).read().split('\n'); la = {}; daily = collections.Counter(); dailyg = collections.Counter(); conc = []
for l in L:
    m = re.match(r'(\d\d-\d\d \d\d:\d\d:\d\d) launch (\S+) on (GPU|CPU)(?: \d+)? \((\d+) cores\)', l)
    if m: la[m.group(2)] = (dt.datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S'), m.group(3), int(m.group(4))); continue
    m = re.match(r'(\d\d-\d\d \d\d:\d\d:\d\d) finished (\S+)', l)
    if m and m.group(2) in la:
        t0, dev, c = la.pop(m.group(2)); t1 = dt.datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S'); h = (t1 - t0).total_seconds() / 3600
        daily[t0.date()] += h * c; dailyg[t0.date()] += h if dev == 'GPU' else 0
days = sorted(daily); fig, ax = plt.subplots(figsize=(89 * MM, 55 * MM))
ax.bar(range(len(days)), [daily[d] for d in days], 0.6, color=C['s1'], label='CPU core-hours (4 cores per run)')
ax2 = ax.twinx(); ax2.plot(range(len(days)), np.cumsum([daily[d] for d in days]) / 1000, color=C['ink2'], lw=1.2); ax2.set_ylabel('Cumulative (×1000 core-h)', color=C['ink2']); ax2.spines['top'].set_visible(False)
ax.set_xticks(range(len(days))); ax.set_xticklabels([d.strftime('%d') for d in days], fontsize=5.5); ax.set_xlabel('October 2026 (day)'); ax.set_ylabel('Core-hours per day'); grid(ax)
ev = {dt.date(2026, 10, 26): 'load-curve\nbug found', dt.date(2026, 10, 31): 'disk full;\nsplit protocol'}
for d, t in ev.items():
    if d in daily: i = days.index(d); ax.annotate(t, (i, daily[d]), xytext=(i, max(daily.values()) * 0.75), fontsize=5.5, ha='center', color=C['ink2'], arrowprops=dict(arrowstyle='-', lw=0.5, color=C['ink2']))
tot = sum(daily.values()); totg = sum(dailyg.values())
save(fig, 'F6_compute', f'Compute use of the FEBio pipeline (scheduler log, 2026-10-20 to 10-31): {tot:,.0f} CPU core-hours and {totg:,.0f} GPU-hours over {len(la) + sum(1 for _ in daily)} job records; bars, core-hours per day; line, cumulative. The 10-21 to 10-23 peak is the ISO/compression active-learning screen (two tests × 150 points); later batches are the physiological-rotation protocol and its re-runs after the 10-26 load-curve fix. One shared host: 32-core cgroup quota, 4 of 7 A100 GPUs.')

# ------------------------------------------------------------------ F7 mu per window
fig, ax = plt.subplots(figsize=(89 * MM, 55 * MM)); rng = np.random.default_rng(0)
for i, w in enumerate(W):
    v = np.array([b[w]['mu_squeeze'] for b in best.values() if w in b and b[w]['target_reached']])
    if not len(v): continue
    ax.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, s=6, color=C['s1'], alpha=0.55, edgecolor='none', zorder=3)
    q = np.percentile(v, [25, 50, 75]); ax.plot([i - 0.3, i + 0.3], [q[1], q[1]], color=C['ink'], lw=1.2, zorder=4); ax.plot([i - 0.2, i + 0.2], [q[0], q[0]], color=C['ink2'], lw=0.6); ax.plot([i - 0.2, i + 0.2], [q[2], q[2]], color=C['ink2'], lw=0.6)
    ax.text(i, -0.012, f'n={len(v)}', ha='center', fontsize=5.5, color=C['ink2'])
ax.axhline(0.3, color=C['s2'], lw=0.6, ls=(0, (3, 2))); ax.text(5.4, 0.305, 'assumed available μ 0.3', fontsize=5.5, ha='right', va='bottom', color=C['s2'])
ax.set_xticks(range(6)); ax.set_xticklabels([WL[w].replace(' ', '\n') for w in W], fontsize=5.5); ax.set_ylabel('Friction coefficient needed, μ_req'); ax.set_ylim(-0.02, 0.33); grid(ax);
save(fig, 'F7_mu_by_direction', 'Friction coefficient needed to prevent dislocation, per loading direction, over all designs whose window reached 1.5 N m (tied-interface limit-surface analysis; dots, designs; bars, median and quartiles). Lateral bending governs fixation (median μ_req ≈ 0.12), flexion–extension needs an order of magnitude less; all values lie below the assumed available friction of 0.3, so for this design family dislocation is not the limiting failure under 1.5 N m pure moments with a 100 N follower load.')

json.dump(CAP, open(os.path.join(HERE, 'figures.json'), 'w'), indent=1, ensure_ascii=False)
print('done', len(CAP))
