"""Red team r0002: schema check of this round's findings and verdict (run from the repo root)."""
import json, os
need = ['id', 'round', 'target', 'severity', 'claim', 'evidence', 'how_to_reproduce', 'fix_options', 'summary_zh']
ids = ['F-%04d' % i for i in range(11, 21)]
for i in ids:
    d = json.load(open(os.path.join('work/findings', i + '.json')))
    miss = [k for k in need if k not in d]
    assert d['id'] == i and d['round'] == 2 and d['severity'] in ('critical', 'major', 'minor'), i
    assert all({'option', 'cost', 'risk'} <= set(o) for o in d['fix_options']), i
    print(i, d['severity'], 'missing' if miss else 'ok', miss)
v = json.load(open('work/board/r0002/redteam.json'))
assert v['role'] == 'redteam' and v['round'] == 2 and v['findings'] == ids and 'summary_zh' in v and len(v['top3']) == 3
print('verdict ok')
