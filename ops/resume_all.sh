#!/bin/bash
# Bring all unattended BIOCAGE work back after a Jupyter server stop / cull (which kills every process of this account).
# Idempotent: starts only what is not already running. Called by ~/.jupyter/jupyter_server_config.py at every server start.
# the server-start PATH lacks ~/.local/bin (claude) and cuda: without this, foreman / role rounds fail "claude: command not found" (11-01 23:21)
export PATH="/raid/jupyter-alz.ee09/.local/bin:/raid/jupyter-alz.ee09/bin:/usr/local/cuda/bin:$PATH"
OLD="/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026"
EVO="$(cd "$(dirname "$0")/.." && pwd)"
tmux has-session -t biocage_watchdog 2>/dev/null || tmux new-session -d -s biocage_watchdog "cd '$OLD' && python scripts/5_compute/h23_watchdog.py 2>> human_study/watchdog.err"
tmux has-session -t evo_daemon 2>/dev/null || tmux new-session -d -s evo_daemon "cd '$EVO' && ops/evo_daemon.sh >> work/agents/evo_daemon.log 2>&1"
[ -f "$OLD/human_study/al_v2/physio_v3_prerun.done" ] || tmux has-session -t biocage_physio_v3 2>/dev/null || \
  tmux new-session -d -s biocage_physio_v3 "cd '$OLD' && python scripts/6_active_learning/h28_physio_prerun.py 12 >> human_study/al_v2/physio_v3_prerun.log 2>&1 && touch human_study/al_v2/physio_v3_prerun.done"
[ -f "$OLD/human_study/al_v2/physio_rot_prerun.done" ] || tmux has-session -t biocage_physio_rot 2>/dev/null || \
  tmux new-session -d -s biocage_physio_rot "cd '$OLD' && python scripts/6_active_learning/h28_physio_prerun.py 12 physio_rot al_v2/physio_rot physrot_ >> human_study/al_v2/physio_rot_prerun.log 2>&1 && touch human_study/al_v2/physio_rot_prerun.done"
# physio_rot pass chain (slow dynamic passes, 2026-10-30): queues the next pass when one ends, then exits
[ -f "$OLD/human_study/rot_chain.done" ] || tmux has-session -t rot_chain 2>/dev/null || \
  tmux new-session -d -s rot_chain "cd '$OLD' && python scripts/6_active_learning/h29_rot_chain.py 2>> human_study/rot_chain.err && touch human_study/rot_chain.done"
# h36 NAS archive (PI 2026-11-03), started by hand 02:14 outside tmux: re-run is safe (rsync --partial, archived sets are symlinks
# and skipped, source removed only after a clean verify) (foreman 11-03 04:35)
[ -f "$OLD/human_study/nas_archive.done" ] || tmux has-session -t nas_archive 2>/dev/null || pgrep -u "$USER" -f h36_nas_archive >/dev/null || \
  tmux new-session -d -s nas_archive "cd '$OLD' && bash scripts/5_compute/h36_nas_archive.sh cases_invalid physio_rot_split_test physio_rot_invalid_overshoot physio_rot_invalid_rigidpresc physio_rot_invalid_symstiff physio_fix physio_rot_facet0 physio_rot_facet3 physio_rot_split physio_rot_dyn2 physio_rot_r2 physio_rot_dyn physio_rot physio_v3 cases && touch human_study/nas_archive.done"
# h37 QA regression check every 6 h (PI 2026-11-04, human_study/qa/QA_SYSTEM.md), started by hand 11-04 14:02, not in h23 DAEMONS:
# report-only, re-run is safe (foreman 11-04 14:27)
[ -f "$OLD/scripts/8_audit/h37_qa_check.py" ] && ! tmux has-session -t biocage_qa 2>/dev/null && ! pgrep -u "$USER" -f 'h37_qa_check.py --daemon' >/dev/null && \
  tmux new-session -d -s biocage_qa "cd '$OLD' && python scripts/8_audit/h37_qa_check.py --daemon 6 2>> human_study/qa/qa.err"
# h45 per-face mu scan (post-processing, no solver), started by hand 11-06 04:10 with nohup outside tmux: no partial resume, a
# re-run from scratch rewrites the same json; finished when scan.log has the "done" line (foreman 11-06 04:30)
grep -qs '^done ' "$OLD/human_study/figures/mu_requirement/scan.log" || tmux has-session -t h45_mu_scan 2>/dev/null || pgrep -u "$USER" -f h45_mu_face_scan >/dev/null || \
  tmux new-session -d -s h45_mu_scan "cd '$OLD/human_study/figures/mu_requirement' && python3 ../../../scripts/8_audit/h45_mu_face_scan.py 14 > scan.log 2>&1"
# pilot_holdG p062 (h06 CPU batch, fric build), started by hand 11-06 23:56 in tmux holdG: h06 resumes from case.dmp and h31
# skips finished windows; p139 of that batch ended ERROR 00:08 and is not re-run; done when batch_patch6.out has "finished p062"
# (foreman 11-07 00:30)
grep -qs '^finished p062' "$OLD/human_study/al_v2/pilot_holdG/batch_patch6.out" || tmux has-session -t holdG 2>/dev/null || pgrep -u "$USER" -f 'h06_run_cpu_batch.py .*pilot_holdG' >/dev/null || \
  tmux new-session -d -s holdG "cd '$OLD' && BIOCAGE_FEBIO='$OLD/third_party/FEBio/cbuild_fric/bin/febio4' python3 scripts/5_compute/h06_run_cpu_batch.py --cores 16 human_study/al_v2/pilot_holdG p062 >> human_study/al_v2/pilot_holdG/batch_patch6.out 2>&1"
# pilot_holdH wave 1 (h47 restart pilots, extension window from a t 3.5 checkpoint), started by hand 11-07 13:16 in tmux holdH:
# a re-run restarts the window from restart.feb (h47 recopies case.xplt), h47 writes <case>/done at exit (also on error/kill), so
# only arms without done are relaunched; the 5 stick-memory arms killed 13:28 have done and are not re-run (foreman 11-07 13:30)
if ! tmux has-session -t holdH 2>/dev/null; then
  for a in pilot_holdH/p062_ctl:3 pilot_holdH/p062_al:3 pilot_holdH/p139_ctl:4 pilot_holdH/p139_al:4 pilot_holdHf/p139_sm:4; do
    c="human_study/al_v2/${a%:*}"; [ -f "$OLD/$c/done" ] || pgrep -u "$USER" -f "h47_restart_pilot.py run $c " >/dev/null || \
      tmux new-session -d -s "holdH_$(echo ${a%:*} | tr / _)" "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c ${a#*:} 3 >> $c.resume.log 2>&1"
  done
fi
# report real work as Jupyter activity so the idle culler does not stop a computing server (PI-authorised 2026-10-26)
tmux has-session -t evo_keepalive 2>/dev/null || tmux new-session -d -s evo_keepalive "cd '$EVO' && python ops/activity_keepalive.py"
echo "$(date -Is) resume_all" >> "$EVO/work/agents/resume_all.log"
tmux ls
