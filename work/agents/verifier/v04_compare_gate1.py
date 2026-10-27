"""Verifier r0002: compare results/gpufe_verify/gate1 (integrator) with work/agents/verifier/gate1_rerun (verifier re-run,
code at git HEAD, no local edits in gpufe/) - reproducibility of gate 1 after the repository split.
usage: python work/agents/verifier/v04_compare_gate1.py
"""
import json, hashlib, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); P = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
A = os.path.join(P, 'results/gpufe_verify/gate1'); B = os.path.join(HERE, 'gate1_rerun')
a = json.load(open(os.path.join(A, 'gate1_report.json'))); b = json.load(open(os.path.join(B, 'gate1_report.json')))
md5 = lambda f: hashlib.md5(open(f, 'rb').read()).hexdigest()
rows = []
for x, y in zip(a['cases'], b['cases']):
    assert x['case'] == y['case']
    d = max(abs(x['per_time'][t][k] - y['per_time'][t][k]) for t in x['per_time'] for k in x['per_time'][t])
    fe = {f: md5(os.path.join(A, x['case'], f)) == md5(os.path.join(B, y['case'], f))
          for f in ('case.feb', 'stress.txt', 'react.txt') if os.path.exists(os.path.join(A, x['case'], f))}
    rows.append(dict(case=x['case'], orig_worst=x['worst_rel_err'], rerun_worst=y['worst_rel_err'], orig_pass=x['passed'],
                     rerun_pass=y['passed'], files_identical=fe, max_abs_diff_of_metrics=d))
    print(rows[-1])
head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=P, capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(['git', 'status', '--short', 'gpufe'], cwd=P, capture_output=True, text=True).stdout.strip()
last = subprocess.run(['git', 'log', '-1', '--format=%h %ci', '--', 'results/gpufe_verify/gate1/gate1_report.json'], cwd=P,
                      capture_output=True, text=True).stdout.strip()
json.dump(dict(code_head=head, gpufe_dirty=dirty or None, reference_report_last_commit=last,
               report_has_provenance_fields=[k for k in a if k not in ('gate', 'all_passed', 'cases')], cases=rows),
          open(os.path.join(HERE, 'v04_compare_gate1.json'), 'w'), indent=1)
