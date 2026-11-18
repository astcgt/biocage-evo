#!/bin/bash
# Bring all unattended BIOCAGE work back after a Jupyter server stop / cull (which kills every process of this account).
# Idempotent: starts only what is not already running. Called by ~/.jupyter/jupyter_server_config.py at every server start.
# the server-start PATH lacks ~/.local/bin (claude) and cuda: without this, foreman / role rounds fail "claude: command not found" (11-01 23:21)
export PATH="/raid/jupyter-alz.ee09/.local/bin:/raid/jupyter-alz.ee09/bin:/usr/local/cuda/bin:$PATH"
OLD="/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026"
EVO="$(cd "$(dirname "$0")/.." && pwd)"
# the pgrep -u "$USER" relaunch guards need USER; a minimal server-start env may lack it (empty -> pgrep fails -> duplicate launches)
export USER="${USER:-$(id -un)}"
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
# pilot_holdH wave 5 (h47, FLEXION window, launch_wave5.sh), started 11-08 02:28 in tmux holdH5: same re-run rule, marker done_flexion
# (foreman 11-08 02:3x)
if ! tmux has-session -t holdH5 2>/dev/null; then
  for a in p062_sm:3 p062_ctl:3 p139_sm:4 p139_ctl:4; do
    c="human_study/al_v2/pilot_holdH/${a%:*}"; [ -f "$OLD/$c/done_flexion" ] || pgrep -u "$USER" -f "h47_restart_pilot.py run $c " >/dev/null || \
      tmux new-session -d -s "holdH5_${a%:*}" "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c ${a#*:} 5 flexion >> $c.flexion.resume.log 2>&1"
  done
fi
# pilot_holdH wave 7 (h47, half-step smRh arms, extension window, launch_wave7.sh), started 11-08 05:09 in tmux holdH7: marker done
# (foreman 11-08 05:3x)
if ! tmux has-session -t holdH7 2>/dev/null; then
  for a in p062_smRh:3 p139_smRh:4; do
    c="human_study/al_v2/pilot_holdH/${a%:*}"; [ -f "$OLD/$c/done" ] || pgrep -u "$USER" -f "h47_restart_pilot.py run $c " >/dev/null || \
      tmux new-session -d -s "holdH7_${a%:*}" "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c ${a#*:} 5 >> $c.resume.log 2>&1"
  done
fi
# pilot_holdH p139_smR7b smoke (h47, extension window, GPU 4, 5 cores), started 11-09 11:41 in tmux smoke7b: marker done (foreman 11-09 11:5x)
c=human_study/al_v2/pilot_holdH/p139_smR7b
if ! tmux has-session -t smoke7b 2>/dev/null && [ ! -f "$OLD/$c/done" ] && ! pgrep -u "$USER" -f "h47_restart_pilot.py run $c " >/dev/null; then
  tmux new-session -d -s smoke7b "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c 4 5 >> $c.resume.log 2>&1"
fi
# physio_fric5 rebuild (h48 build, idempotent: skips cases with a valid preflight), started 11-09 11:44 in tmux fric5build2: marker BUILD DONE
f=human_study/al_v2/physio_fric5/build2.log
if ! tmux has-session -t fric5build2 2>/dev/null && ! grep -q 'BUILD DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "h48_fric5_batch.py build" >/dev/null; then
  tmux new-session -d -s fric5build2 "cd '$OLD' && python3 -u scripts/5_compute/h48_fric5_batch.py build >> ${f%.log}.resume.log 2>&1 && echo BUILD DONE >> $f"
fi
# physio_fric5 run (h48 run: 5 workers, GPUs 3,4, 5 cores; per-window done markers, an interrupted window reruns from case.dmp),
# started 11-09 12:14 in tmux fric5batch: marker BATCH DONE (foreman 11-09 12:5x)
f=human_study/al_v2/physio_fric5/run_batch.log
if ! tmux has-session -t fric5batch 2>/dev/null && ! grep -q 'BATCH DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "h48_fric5_batch.py run" >/dev/null; then
  tmux new-session -d -s fric5batch "cd '$OLD' && python3 -u scripts/5_compute/h48_fric5_batch.py run 5 3,4 5 >> ${f%.log}.resume.log 2>&1 && echo BATCH DONE >> $f"
fi
# pilot_relE p068 run2 (h18 on the cbuild_fric patch8 binary, GPU 4, 6 cores; resumes from its checkpoint), started 11-09 12:05
# in tmux febuild2 after the make: marker RELE P068 RUN2 DONE (foreman 11-09 12:5x)
f=human_study/al_v2/pilot_relE/p068_run2.log
if ! tmux has-session -t febuild2 2>/dev/null && [ -f "$OLD/$f" ] && ! grep -q 'RELE P068 RUN2 DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "h18_run_gpu_case.py 4 human_study/al_v2/pilot_relE/p068" >/dev/null; then
  tmux new-session -d -s febuild2 "cd '$OLD' && BIOCAGE_FEBIO=$OLD/third_party/FEBio/cbuild_fric/bin/febio4 BIOCAGE_STICK_MEMORY=1 python3 -u scripts/5_compute/h18_run_gpu_case.py 4 human_study/al_v2/pilot_relE/p068 6 >> ${f%.log}.resume.log 2>&1; echo RELE P068 RUN2 DONE >> $f"
fi
# pilot_relE p062/p094/p129(run2) + pilot_relF p068 (h18, cbuild_fric, 6 cores each; resume from case.dmp), started by hand
# 11-09 18:02-18:41 in tmux relE_p062/relE_p094/relE_p129b/relF_p068: marker "<TAG> DONE" in the run log (foreman 11-09 18:4x)
# + pilot_relE3 p062 (h30 split case: h31 skips ended windows on re-run), started 11-09 19:32 in tmux relE3_p062 (foreman 11-09 19:4x)
# + pilot_relE3 p068 (GPU 4), started 11-09 20:17 in tmux relE3_p068 (foreman 11-09 20:4x)
# + pilot_relE3 p052 (GPU 2) and pilot_relF2 p062/p068/p094/p129 (GPUs 1/3/6/5), started 11-09 20:51-21:27 (foreman 11-09 21:4x)
# + pilot_relG p068/p094/p062 (GPUs 3/4/6), started 11-09 22:08-22:18 (foreman 11-09 22:4x)
# + pilot_relG p121/p116/p050/p109 (GPUs 1/2/4/6), started 11-09 23:05 (foreman 11-09 23:4x)
for a in relE_p062:6:pilot_relE/p062:p062_run:RELE_P062 relE_p094:3:pilot_relE/p094:p094_run:RELE_P094 \
         relE_p129b:5:pilot_relE/p129:p129_run2:RELE_P129_RUN2 relF_p068:1:pilot_relF/p068:p068_run:RELF_P068 \
         relE3_p062:6:pilot_relE3/p062:p062_run:RELE3_P062 relE3_p068:4:pilot_relE3/p068:p068_run:RELE3_P068 \
         relE3_p052:2:pilot_relE3/p052:p052_run:RELE3_P052 relF2_p062:1:pilot_relF2/p062:p062_run:RELF2_P062 \
         relF2_p068:3:pilot_relF2/p068:p068_run:RELF2_P068 relF2_p094:6:pilot_relF2/p094:p094_run:RELF2_P094 \
         relF2_p129:5:pilot_relF2/p129:p129_run:RELF2_P129 \
         relG_p068:3:pilot_relG/p068:p068_run:RELG_P068 relG_p094:4:pilot_relG/p094:p094_run:RELG_P094 \
         relG_p062:6:pilot_relG/p062:p062_run:RELG_P062 \
         relG_p121:1:pilot_relG/p121:p121_run:RELG_P121 relG_p116:2:pilot_relG/p116:p116_run:RELG_P116 \
         relG_p050:4:pilot_relG/p050:p050_run:RELG_P050 relG_p109:6:pilot_relG/p109:p109_run:RELG_P109; do
  IFS=: read -r s g c l t <<< "$a"; t=${t//_/ }; f=human_study/al_v2/${c%/*}/$l.log
  if ! tmux has-session -t $s 2>/dev/null && [ -f "$OLD/$f" ] && ! grep -q "$t DONE" "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "h18_run_gpu_case.py $g human_study/al_v2/$c( |$)" >/dev/null; then
    tmux new-session -d -s $s "cd '$OLD' && BIOCAGE_FEBIO=$OLD/third_party/FEBio/cbuild_fric/bin/febio4 BIOCAGE_STICK_MEMORY=1 python3 -u scripts/5_compute/h18_run_gpu_case.py $g human_study/al_v2/$c 6 >> ${f%.log}.resume.log 2>&1; echo '$t DONE' >> $f"
  fi
done
# physio_relG production batch (h50, 27 insertion-stopped designs): the 14:36 hand-started h50 run (tmux relG_batch) is not
# restartable on its own and lost 23 designs to a full GPU 5; ops/relG_drive.py (tmux relG_drive) finishes and resumes the set,
# max 5 runs x 6 cores, GPUs 4/1/3/2, interrupted run dirs resume on their GPU: marker RELG DRIVE DONE (foreman 11-10 14:5x)
f=human_study/al_v2/physio_relG/drive.log
if ! tmux has-session -t relG_drive 2>/dev/null && ! grep -q 'RELG DRIVE DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "ops/relG_drive.py" >/dev/null; then
  tmux new-session -d -s relG_drive "cd '$EVO' && python3 ops/relG_drive.py 2>> '$OLD/human_study/al_v2/physio_relG/drive.err'"
fi
# physio_relG_pl fallback windows (h51 driver, tmux relGpl_drive, started 11-10 17:1x): production-law restarts of the process-G windows
# that stopped under the stick law (+ 6 control windows); waits for free quota behind the relG drive: marker RELG_PL DONE
# workers 2 -> 5 (foreman 11-10 22:0x, ops/relGpl_handoff.sh): the 32-core quota check in h51 still limits the total
f=human_study/al_v2/physio_relG_pl/run_batch.log
if ! tmux has-session -t relGpl_drive 2>/dev/null && ! grep -q 'RELG_PL DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "h51_relG_fallback.py run" >/dev/null; then
  tmux new-session -d -s relGpl_drive "cd '$OLD' && python3 -u scripts/5_compute/h51_relG_fallback.py run 5 1,2,3,4 6 +p039:extension +p039:flexion +p052:extension +p052:flexion +p061:extension +p061:flexion >> $f 2>&1"
fi
# relG_pl ctrl2 (h51 'only' list of 7 'first increments' windows), started 11-10 23:51 in tmux relGpl_ctrl2; h51 skips windows with a
# done marker on re-run; marker: a RELG_PL DONE line after the last 'ctrl2:' line of run_batch.log (foreman 11-10 23:5x)
if ! tmux has-session -t relGpl_ctrl2 2>/dev/null && ! awk '/ctrl2:/{c=1;d=0} c&&/RELG_PL DONE/{d=1} END{exit !(c&&d)}' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "h51_relG_fallback.py run" >/dev/null; then
  tmux new-session -d -s relGpl_ctrl2 "cd '$OLD' && python3 -u scripts/5_compute/h51_relG_fallback.py run 5 1,2,3,4 6 p050:flexion p074:flexion p084:extension p109:flexion p109:extension p115:flexion p127:flexion >> $f 2>&1"
fi
# pilot_relGdrv (h51 'only' list, window_drive="from_state", 5 windows), started 11-11 01:07 in tmux relGdrv_pilot; h51 skips windows
# with a done marker on re-run; marker RELG_PL DONE in its run_batch.log (foreman 11-11 01:1x)
f=human_study/al_v2/pilot_relGdrv/run_batch.log
if ! tmux has-session -t relGdrv_pilot 2>/dev/null && ! grep -q 'RELG_PL DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "H51_DST=pilot_relGdrv" >/dev/null; then
  tmux new-session -d -s relGdrv_pilot "cd '$OLD' && H51_DST=pilot_relGdrv H51_KEYS='window_drive=\"from_state\"' python3 -u scripts/5_compute/h51_relG_fallback.py run 3 2,3,4 6 p050:flexion p068:flexion p084:extension p039:extension p048:flexion >> $f 2>&1"
fi
# pilot_relGfix (h51 'only' list, window_joint penalty + from_state, 4 windows, tmux relGfix_pilot, started 11-11 01:33) and
# pilot_relGrel (window_drive_mode="rigid_relative", 4 windows, tmux relGrel_pilot, started 11-11 01:45); h51 skips windows with a
# done marker on re-run; marker RELG_PL DONE in each run_batch.log (foreman 11-11 02:1x)
f=human_study/al_v2/pilot_relGfix/run_batch.log
if ! tmux has-session -t relGfix_pilot 2>/dev/null && ! grep -q 'RELG_PL DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "H51_DST=pilot_relGfix" >/dev/null; then
  tmux new-session -d -s relGfix_pilot "cd '$OLD' && H51_DST=pilot_relGfix H51_KEYS='window_joint={\"laugon\": 0, \"penalty\": 1000000.0}|window_drive=\"from_state\"' python3 -u scripts/5_compute/h51_relG_fallback.py run 3 3,4,2 6 p050:flexion p068:flexion p084:extension p039:extension >> $f 2>&1"
fi
f=human_study/al_v2/pilot_relGrel/run_batch.log
if ! tmux has-session -t relGrel_pilot 2>/dev/null && ! grep -q 'RELG_PL DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "H51_DST=pilot_relGrel" >/dev/null; then
  tmux new-session -d -s relGrel_pilot "cd '$OLD' && H51_DST=pilot_relGrel H51_KEYS='window_drive_mode=\"rigid_relative\"' python3 -u scripts/5_compute/h51_relG_fallback.py run 3 2,3,4 6 p050:flexion p068:flexion p084:extension p039:extension >> $f 2>&1"
fi
# pilot_relGrel validation set (7 windows, tmux relGrel_val, started 11-11 15:00; same log, so marker = RELG_PL DONE after the
# 'only p039:flexion p068:extension p048:flexion' start line) and pilot_fric5rel (H51_SRC=physio_fric3, 6 windows, tmux
# fric5rel_val, started 11-11 15:00, marker RELG_PL DONE); h51 skips windows with a done marker on re-run (foreman 11-11 15:0x)
if ! tmux has-session -t relGrel_val 2>/dev/null && ! awk '/only p039:flexion p068:extension p048:flexion/{c=1;d=0} c&&/RELG_PL DONE/{d=1} END{exit !(c&&d)}' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "H51_DST=pilot_relGrel" >/dev/null; then
  tmux new-session -d -s relGrel_val "cd '$OLD' && H51_DST=pilot_relGrel H51_KEYS='window_drive_mode=\"rigid_relative\"' python3 -u scripts/5_compute/h51_relG_fallback.py run 3 2,3,4 6 p039:flexion p068:extension p048:flexion p048:extension p109:flexion p109:extension p084:extension >> $f 2>&1"
fi
# pilot_relGrel p039/p068 re-run (4 windows, tmux relGrel_val2, started 11-13 03:07; marker RELG_PL DONE after its 'only p039:flexion
# p039:extension' start line). pilot_fric5rel relaunched 11-13 03:09 as tmux fric5rel_val2, 3 workers GPUs 1,4,2 (foreman 11-13 03:1x)
f=human_study/al_v2/pilot_relGrel/run_batch.log
if ! tmux has-session -t relGrel_val2 2>/dev/null && ! awk '/only p039:flexion p039:extension p068:flexion p068:extension/{c=1;d=0} c&&/RELG_PL DONE/{d=1} END{exit !(c&&d)}' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "H51_DST=pilot_relGrel" >/dev/null; then
  tmux new-session -d -s relGrel_val2 "cd '$OLD' && H51_DST=pilot_relGrel H51_KEYS='window_drive_mode=\"rigid_relative\"' python3 -u scripts/5_compute/h51_relG_fallback.py run 2 2,3 6 p039:flexion p039:extension p068:flexion p068:extension >> $f 2>&1"
fi
f=human_study/al_v2/pilot_fric5rel/run_batch.log
if ! tmux has-session -t fric5rel_val2 2>/dev/null && [ -f "$OLD/$f" ] && ! grep -q 'RELG_PL DONE' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "H51_DST=pilot_fric5rel" >/dev/null; then
  tmux new-session -d -s fric5rel_val2 "cd '$OLD' && H51_SRC=physio_fric3 H51_DST=pilot_fric5rel H51_KEYS='window_drive_mode=\"rigid_relative\"|restart_env={\"BIOCAGE_STICK_MEMORY\": \"1\"}|window_min_residual=0.0001' python3 -u scripts/5_compute/h51_relG_fallback.py run 3 1,4,2 6 p002:flexion p002:extension p036:flexion p100:extension p026:flexion p026:extension >> $f 2>&1"
fi
# physio_fric3 p102 / p149 (h18, default cbuild binary, no BIOCAGE_ env, 6 cores, GPUs 1 / 4; resume from case.dmp), started by hand
# 11-17 03:43 in tmux fric3_p102 / fric3_p149: done when h18 wrote <case>_gpu<g>/resources.json (also on ERROR) (foreman 11-17 03:5x)
# physio_fric3 p060 (same rule, GPU 1), started by hand 11-18 12:59 in tmux p060_fric3 (foreman 11-18 13:0x)
for a in fric3_p102:1:p102 fric3_p149:4:p149 p060_fric3:1:p060; do
  IFS=: read -r s g c <<< "$a"; d=human_study/al_v2/physio_fric3/$c
  if ! tmux has-session -t $s 2>/dev/null && [ -f "$OLD/$d/case.feb" ] && [ ! -f "$OLD/${d}_gpu$g/resources.json" ] && ! pgrep -u "$USER" -f "h18_run_gpu_case.py $g $d( |$)" >/dev/null; then
    tmux new-session -d -s $s "cd '$OLD' && python3 -u scripts/5_compute/h18_run_gpu_case.py $g $d 6 >> ${d}_run.log 2>&1"
  fi
done
# physio_fric5r p102 route-E windows (h51 'only p102:flexion p102:extension', GPUs 1,2, tmux fric5r_p102, started 11-17 04:22; h51 skips
# windows with a done marker; marker RELG_PL DONE after that start line) and physio_relG p149 (h50 run 1 4 6 p149, tmux relG_p149,
# started 11-17 04:22). p149 resumes with h18 directly (h18 resumes p149_gpu4 from case.dmp, env as h50 sets it): h50's running()
# would skip p149 for 20 min after a stop (case.log mtime) and exit; done when p149_gpu4/resources.json exists, also on ERROR (foreman 11-17 04:5x)
f=human_study/al_v2/physio_fric5r/run_batch.log
if ! tmux has-session -t fric5r_p102 2>/dev/null && [ -f "$OLD/$f" ] && ! awk '/only p102:flexion p102:extension/{c=1;d=0} c&&/RELG_PL DONE/{d=1} END{exit !(c&&d)}' "$OLD/$f" 2>/dev/null && ! pgrep -u "$USER" -f "H51_DST=physio_fric5r" >/dev/null; then
  tmux new-session -d -s fric5r_p102 "cd '$OLD' && H51_SRC=physio_fric3 H51_DST=physio_fric5r H51_KEYS='window_drive_mode=\"rigid_relative\"|restart_env={\"BIOCAGE_STICK_MEMORY\": \"1\"}|window_min_residual=0.0001' python3 -u scripts/5_compute/h51_relG_fallback.py run 2 1,2 6 p102:flexion p102:extension >> $f 2>&1"
fi
d=human_study/al_v2/physio_relG
if ! tmux has-session -t relG_p149 2>/dev/null && [ -d "$OLD/$d/p149_gpu4" ] && [ ! -f "$OLD/$d/p149_gpu4/resources.json" ] && ! pgrep -u "$USER" -f "h18_run_gpu_case.py 4 \S*$d/p149( |$)" >/dev/null; then
  tmux new-session -d -s relG_p149 "cd '$OLD' && BIOCAGE_FEBIO=$OLD/third_party/FEBio/cbuild_fric/bin/febio4 BIOCAGE_STICK_MEMORY=1 python3 -u scripts/5_compute/h18_run_gpu_case.py 4 $d/p149 6 >> $d/p149_run.log 2>&1"
fi
# pilot_holdQ p062 / p139 (h18 split case, default cbuild binary, no BIOCAGE_ env, 6 cores, GPUs 1 / 4; launch.sh in tmux holdQ_pilot,
# started 11-18 03:22): h18 resumes from case.dmp, h31 skips ended windows; done when <case>_gpu<g>/resources.json exists (foreman 11-18 04:1x)
if ! tmux has-session -t holdQ_pilot 2>/dev/null; then
  for a in p062:1 p139:4; do
    IFS=: read -r c g <<< "$a"; d=human_study/al_v2/pilot_holdQ/$c
    if [ -f "$OLD/$d/case.feb" ] && [ ! -f "$OLD/${d}_gpu$g/resources.json" ] && ! pgrep -u "$USER" -f "h18_run_gpu_case.py $g $d( |$)" >/dev/null; then
      tmux new-session -d -s holdQ_$c "cd '$OLD' && python3 -u scripts/5_compute/h18_run_gpu_case.py $g $d 6 >> ${d}_run.log 2>&1"; sleep 10
    fi
  done
fi
# pilot_holdR wave 1 (h47, route-E hold windows, launch_wave1.sh), started 11-18 02:02 in tmux holdR_pilot: a re-run restarts the
# window from restart.feb; h47 writes <case>/done (extension) / done_flexion at exit, also on error (foreman 11-18 02:1x)
# pilot_holdRh wave 1 (same windows, window_dt 0.025), started 11-18 02:38 in tmux holdRh_pilot: same rule (foreman 11-18 03:0x)
# pilot_holdQR wave 1 (holdQ t 3.5 checkpoints, deck dtmax 0.025 over the hold), started 11-18 05:47 in tmux holdQR_pilot: same rule (foreman 11-18 06:0x)
for k in holdR holdRh holdQR; do
if ! tmux has-session -t ${k}_pilot 2>/dev/null; then
  for a in p062:1:extension p062:1:flexion p139:4:extension p139:4:flexion; do
    IFS=: read -r p g w <<< "$a"; c="human_study/al_v2/pilot_$k/$p"; m=done; [ $w = extension ] || m=done_$w
    [ -f "$OLD/$c/$m" ] || pgrep -u "$USER" -f "h47_restart_pilot.py run $c [0-9]+ [0-9]+ $w" >/dev/null || \
      { tmux new-session -d -s "${k}_${p}_$w" "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c $g 5 $w >> $c.$w.resume.log 2>&1"; sleep 5; }
  done
fi
done
# pilot_rep3 wave 1 (h47, third replicate of physio_fric5r p093/p145 extension GPU 1, p051/p075 flexion GPU 4), started 11-18 11:28
# in tmux rep3_pilot: same rule, markers done / done_flexion (foreman 11-18 11:3x)
if ! tmux has-session -t rep3_pilot 2>/dev/null; then
  for a in p093:1:extension p145:1:extension p051:4:flexion p075:4:flexion; do
    IFS=: read -r p g w <<< "$a"; c="human_study/al_v2/pilot_rep3/$p"; m=done; [ $w = extension ] || m=done_$w
    [ -f "$OLD/$c/$m" ] || pgrep -u "$USER" -f "h47_restart_pilot.py run $c [0-9]+ [0-9]+ $w" >/dev/null || \
      { tmux new-session -d -s "rep3_${p}_$w" "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c $g 5 $w >> $c.$w.resume.log 2>&1"; sleep 5; }
  done
fi
# pilot_rep3 p093 variants (launch_p093_variants.sh, tmux p093var, started 11-18 13:00): p093n extension GPU 4, 6 cores, same rule;
# p093d not covered (its h24 preflight failed at launch: window_dt not in PILOT_KEYS) (foreman 11-18 13:0x)
if ! tmux has-session -t p093var 2>/dev/null; then
  c=human_study/al_v2/pilot_rep3/p093n
  [ ! -d "$OLD/$c" ] || [ -f "$OLD/$c/done" ] || pgrep -u "$USER" -f "h47_restart_pilot.py run $c [0-9]+ [0-9]+ extension" >/dev/null || \
    tmux new-session -d -s rep3_p093n_extension "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c 4 6 extension >> $c.extension.resume.log 2>&1"
fi
# FEBio core pinner (foreman 11-10 22:5x): moves each new FEBio run once to disjoint idle cores on its GPU's NUMA node (log work/ops/febio_pin.log)
tmux has-session -t febio_pin 2>/dev/null || pgrep -u "$USER" -f "ops/febio_pin.sh" >/dev/null || tmux new-session -d -s febio_pin "cd '$EVO' && while true; do ops/febio_pin.sh; echo \"\$(date '+%m-%d %H:%M:%S') febio_pin exit \$?, restart in 30 s\" >> work/ops/febio_pin.log; sleep 30; done"
# report real work as Jupyter activity so the idle culler does not stop a computing server (PI-authorised 2026-10-26)
tmux has-session -t evo_keepalive 2>/dev/null || tmux new-session -d -s evo_keepalive "cd '$EVO' && python ops/activity_keepalive.py"
echo "$(date -Is) resume_all" >> "$EVO/work/agents/resume_all.log"
tmux ls
