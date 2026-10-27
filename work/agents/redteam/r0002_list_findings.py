import json, glob
for f in sorted(glob.glob('work/findings/*.json')):
    d = json.load(open(f))
    print(d['id'], d['severity'], d.get('target'), '|', d['claim'][:500], '| status:', d.get('status'), '\n')
