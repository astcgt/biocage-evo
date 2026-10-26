"""Report real background work as Jupyter activity, so the hub's idle culler does not stop a server that is computing.

PI 2026-10-26 (explicitly authorised, permission rule added by the PI): the account runs long simulations without a browser
open; Jupyter only counts kernels, terminals and API requests as activity, so a computing server looks idle and gets
culled (every process dies). This script reports activity ONLY while real work exists and stops reporting as soon as
everything has finished, so a truly idle server can still be culled as the policy intends. Every report and every state
change is logged (work/agents/keepalive.log).

Work = any FEBio process of this account, any job waiting or running in the old study's queue, or a GPU solver / agent
round of this repository. Activity = one authenticated, light API request (directory listing) to this user's own Jupyter
server every INTERVAL s; the server URL and token are read from the running jupyterhub-singleuser process (they change at
every server start, and the token never appears on a command line or in the log).
usage: python ops/activity_keepalive.py
"""
import os, glob, time, subprocess, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_QUEUE = '/raid/jupyter-alz.ee09/projects/claude-work/biocage stimulation test 1/human_study/queue'
LOG = os.path.join(ROOT, 'work/agents/keepalive.log')
INTERVAL = 600
UID = str(os.getuid())


def log(msg):
    with open(LOG, 'a') as f: f.write(time.strftime('%m-%d %H:%M:%S ') + msg + '\n')


def pgrep(pattern):
    return subprocess.run(['pgrep', '-u', UID, '-f', pattern], capture_output=True).returncode == 0


def work():
    """Reason string if real work exists, else None."""
    if pgrep('febio4'): return 'FEBio running'
    jobs = glob.glob(os.path.join(OLD_QUEUE, '*.job')) + glob.glob(os.path.join(OLD_QUEUE, 'running', '*.job'))
    if jobs: return f'{len(jobs)} queued / running jobs'
    if pgrep('gpufe') or pgrep('roles/run_roles.sh'): return 'GPU solver or agent round running'
    return None


def server():
    pid = subprocess.run(['pgrep', '-u', UID, '-f', 'jupyterhub-singleuser'], capture_output=True, text=True).stdout.split()
    if not pid: return None
    raw = open(f'/proc/{pid[0]}/environ', 'rb').read().decode(errors='ignore')
    env = dict(kv.split('=', 1) for kv in raw.split('\0') if '=' in kv)
    return env.get('JUPYTERHUB_SERVICE_URL'), env.get('JPY_API_TOKEN') or env.get('JUPYTERHUB_API_TOKEN')


def report():
    url, tok = server() or (None, None)
    if not url or not tok: return 'no Jupyter server found'
    req = urllib.request.Request(url.rstrip('/') + '/api/contents?content=0', headers={'Authorization': f'token {tok}'})
    with urllib.request.urlopen(req, timeout=30) as r: return f'HTTP {r.status}'


def main():
    state = None
    log('keepalive started')
    while True:
        why = work()
        if why:
            try: res = report()
            except Exception as e: res = f'error {type(e).__name__}'
            log(f'active ({why}): {res}')
        elif state is not None:
            log('no work left: not reporting activity (server may be culled as idle)')
        state = why
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
