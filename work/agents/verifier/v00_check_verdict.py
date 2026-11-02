"""Verifier: schema check of the round verdict. usage: python work/agents/verifier/v00_check_verdict.py r0003 (paths updated r0003)"""
import json, os, sys
P = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
d = json.load(open(os.path.join(P, 'work/board', sys.argv[1], 'verifier.json')))
need = ['role', 'round', 'verdict', 'gate_reruns', 'checks', 'proposed_gate_criteria', 'change_requests', 'summary_zh']
assert all(k in d for k in need), [k for k in need if k not in d]
assert d['role'] == 'verifier' and d['verdict'] in ('PASS', 'HOLD')
for c in d['checks']:
    assert set(('item', 'result', 'severity', 'evidence')) <= set(c) and c['result'] in ('ok', 'problem'), c['item']
print('OK', d['verdict'], len(d['checks']), 'checks', len(d['change_requests']), 'CRs')
