#!/bin/bash
# Bring all unattended BIOCAGE work back after a Jupyter server stop / cull (which kills every process of this account).
# Idempotent: starts only what is not already running. Called by ~/.jupyter/jupyter_server_config.py at every server start.
# the server-start PATH lacks ~/.local/bin (claude) and cuda: without this, foreman / role rounds fail "claude: command not found" (11-01 23:21)
export PATH="/raid/jupyter-alz.ee09/.local/bin:/raid/jupyter-alz.ee09/bin:/usr/local/cuda/bin:$PATH"
OLD="/raid/jupyter-alz.ee09/projects/claude-work/biocage_simulation_test_oct2026"
EVO="$(cd "$(dirname "$0")/.." && pwd)"
# the pgrep -u "$USER" relaunch guards need USER; a minimal server-start env may lack it (empty -> pgrep fails -> duplicate launches)
export USER="${USER:-$(id -un)}"
bash "$EVO/ops/resume_daemons.sh"   # resident daemon: the platform watchdog (it brings back scheduler, samplers, preflight, QA); own file since 2026-11-22 so that lane edits below do not touch it
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
# pilot_rep3 full-Newton set 2 (launch_fullnewton2.sh, tmux fullnewton2, started 11-18 13:56): p093n2 GPU 1 5 cores,
# p093n3 GPU 3 6 cores, p145n GPU 4 6 cores, extension; same rule, marker done (foreman 11-18 14:0x)
if ! tmux has-session -t fullnewton2 2>/dev/null; then
  for a in p093n2:1:5 p093n3:3:6 p145n:4:6; do
    IFS=: read -r p g n <<< "$a"; c="human_study/al_v2/pilot_rep3/$p"
    [ ! -d "$OLD/$c" ] || [ -f "$OLD/$c/done" ] || pgrep -u "$USER" -f "h47_restart_pilot.py run $c [0-9]+ [0-9]+ extension" >/dev/null || \
      { tmux new-session -d -s "rep3_${p}_extension" "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c $g $n extension >> $c.extension.resume.log 2>&1"; sleep 5; }
  done
fi
# pilot_push p062 (h47, push-out windows push_post then push_ant, GPU 1, 6 cores), started 11-19 04:56 in tmux biocage_push: a re-run
# restarts the window from restart.feb (hard-linked case.dmp, never rewritten); markers done_push_post / done_push_ant, only missing
# windows are relaunched, in order (foreman 11-19 05:0x)
c=human_study/al_v2/pilot_push/p062
if ! tmux has-session -t biocage_push 2>/dev/null && [ -d "$OLD/$c" ] && ! pgrep -u "$USER" -f "h47_restart_pilot.py run $c " >/dev/null; then
  cmd=""; for w in push_post push_ant; do [ -f "$OLD/$c/done_$w" ] || cmd="$cmd python scripts/5_compute/h47_restart_pilot.py run $c 1 6 $w >> ${c%/*}/$w.resume.log 2>&1;"; done
  [ -n "$cmd" ] && tmux new-session -d -s biocage_push "cd '$OLD' && $cmd"
fi
# pilot_cyc3 p062 (h18 split case, GPU 4) / pilot_lbar p062 (GPU 3), default cbuild binary, no BIOCAGE_ env, 6 cores, started by hand
# 11-19 05:02 / 05:04 in tmux biocage_cyc3 / biocage_lbar: h18 resumes from case.dmp, h31 skips ended windows; done when
# <case>_gpu<g>/resources.json exists (foreman 11-19 06:0x)
for a in biocage_cyc3:4:pilot_cyc3 biocage_lbar:3:pilot_lbar; do
  IFS=: read -r s g k <<< "$a"; d=human_study/al_v2/$k/p062
  if ! tmux has-session -t $s 2>/dev/null && [ -f "$OLD/$d/case.feb" ] && [ ! -f "$OLD/${d}_gpu$g/resources.json" ] && ! pgrep -u "$USER" -f "h18_run_gpu_case.py $g $d( |$)" >/dev/null; then
    tmux new-session -d -s $s "cd '$OLD' && python3 -u scripts/5_compute/h18_run_gpu_case.py $g $d 6 >> ${d}_run.log 2>&1"
  fi
done
# pilot_cyc3r p062 (h47, flexion window, GPU 2, 6 cores), started 11-19 05:19 in tmux biocage_cyc3r: a re-run restarts the window
# from restart.feb; marker done_flexion (foreman 11-19 06:0x)
c=human_study/al_v2/pilot_cyc3r/p062
if ! tmux has-session -t biocage_cyc3r 2>/dev/null && [ -d "$OLD/$c" ] && [ ! -f "$OLD/$c/done_flexion" ] && ! pgrep -u "$USER" -f "h47_restart_pilot.py run $c [0-9]+ [0-9]+ flexion" >/dev/null; then
  tmux new-session -d -s biocage_cyc3r "cd '$OLD' && python scripts/5_compute/h47_restart_pilot.py run $c 2 6 flexion >> ${c}_run.log 2>&1"
fi
# pilot_mu03r (PI 11-19 option 乙; drive_mu03r.sh in tmux biocage_mu03, started 05:20): all 5 designs were built 05:48, so a resume
# runs only its h51 run phase (re-running the script would rebuild the built dirs); h51 skips windows with a done marker; marker
# RELG_PL DONE in drive.log. The 5 pilot_mu03 base runs are h19 queue jobs (re-queued by the scheduler) (foreman 11-19 06:0x)
f=human_study/al_v2/pilot_mu03/drive.log; o="p062:flexion p062:extension p131:flexion p131:extension p100:flexion p100:extension p063:flexion p063:extension p110:flexion p110:extension"
if ! tmux has-session -t biocage_mu03 2>/dev/null && [ -f "$OLD/$f" ] && grep -q '^built: ' "$OLD/$f" && ! grep -q 'RELG_PL DONE' "$OLD/$f" && ! pgrep -u "$USER" -f "h51_relG_fallback.py run 3 2,3,4 6 p062:flexion p062:extension p131" >/dev/null; then
  tmux new-session -d -s biocage_mu03 "cd '$OLD' && H51_SRC=pilot_mu03 H51_DST=pilot_mu03r H51_KEYS='restart_env={\"BIOCAGE_STICK_MEMORY\": \"1\"}|window_drive_mode=\"rigid_relative\"|window_min_residual=0.0001' python3 -u scripts/5_compute/h51_relG_fallback.py run 3 2,3,4 6 $o >> $f 2>&1; echo MU03R DONE >> $f"
fi
# pilot_fl250r p062 (GPU 1) / pilot_lbarr p062 (GPU 3): h51 only-mode restarts of pilot_fl250 / pilot_lbar, started by hand 11-19 08:44
# in tmux biocage_fl250r / biocage_lbarr; h51 skips windows with a done marker (done for extension, done_<w> otherwise); a missing
# marker = still to run (foreman 11-19 09:0x). lbarr removed (foreman 11-19 12:0x): LB done, AR windows stopped on purpose ~11:22
# (DECISIONS 11-19, stalled near t 3.9) without done markers, so the cover would have relaunched them
for a in "biocage_fl250r:pilot_fl250:pilot_fl250r:1:p062:flexion p062:extension"; do
  IFS=: read -r s src dst g o <<< "$a"; d=human_study/al_v2/$dst; todo=0
  for it in $o; do w=${it#*:}; m=done_$w; [ "$w" = extension ] && m=done; [ -f "$OLD/$d/${it%%:*}/$m" ] || todo=1; done
  if [ $todo = 1 ] && [ -d "$OLD/$d/p062" ] && ! tmux has-session -t $s 2>/dev/null && ! pgrep -u "$USER" -f "h51_relG_fallback.py run 2 $g 6 $o" >/dev/null; then
    tmux new-session -d -s $s "cd '$OLD' && H51_SRC=$src H51_DST=$dst H51_KEYS='restart_env={\"BIOCAGE_STICK_MEMORY\": \"1\"}|window_drive_mode=\"rigid_relative\"|window_min_residual=0.0001' python3 -u scripts/5_compute/h51_relG_fallback.py run 2 $g 6 $o >> $d/run.log 2>&1"
  fi
done
# pilot_cyc3v S9 cycle lanes (lanes.sh, tmux biocage_cycA/B/C, 11-19 10:38), pilot_push batch (push_batch.sh, tmux biocage_pushB,
# 10:38), pilot_mu03 drivers (drive_mu03r_b.sh / drive_mu03G.sh, tmux biocage_mu03b / biocage_mu03G, 10:51), all started by hand:
# a lane re-runs with the designs its log does not report ended (an interrupted insertion resumes from case.dmp via h18; one whose
# insertion had ended normal re-runs it from case.feb); push_batch skips valid / started builds and h51 skips done windows; h51
# build skips valid / started dirs. Markers: LANE <g> DONE / PUSH BATCH DONE / MU03R_B DONE / MU03G DONE (foreman 11-19 11:1x)
A=human_study/al_v2
for a in "biocage_cycA:1:A:p036 p121 p088 p062" "biocage_cycB:4:B:p064 p067 p140" "biocage_cycC:2:C:p066 p082 p110 p124"; do
  IFS=: read -r s g l ids <<< "$a"; f=$OLD/$A/pilot_cyc3v/lane$l.log; left=""
  [ -f "$f" ] && ! grep -q "LANE $g DONE" "$f" || continue
  for p in $ids; do grep -qE "^[0-9:]+ $p (relG done|route-E cycle window done|insertion not normal)" "$f" || left="$left $p"; done
  if [ -n "$left" ] && ! tmux has-session -t $s 2>/dev/null && ! pgrep -u "$USER" -f "lanes.sh $g 6 " >/dev/null; then
    tmux new-session -d -s $s "cd '$OLD/$A' && bash pilot_cyc3v/lanes.sh $g 6$left 2>&1 | tee -a pilot_cyc3v/lane$l.log"
  fi
done
# push_batch v2 (11-19 11:14, tmux biocage_pushB0/B1, usage <gpu> <lane> <n lanes>) replaced the v1 biocage_pushB batch (batch.log,
# no done marker): lane skips designs with done_push_post + normal, h47 resumes a started window. Marker PUSH LANE <l> DONE (foreman 11-19 12:0x)
# 11-20 12:1x lane 1 split (live push_batch list truncated after p129): lanes 1 and 2 restart through ops/push_lanes.sh on explicit,
# disjoint design lists (push_batch.sh 3 1 would regenerate the full lane-1 list and re-run lane 2's designs). Lane 0 unchanged.
# 11-20 13:1x lane 1 split again (live list truncated after p120, offset 560): p122 p129 -> lane 3 on GPU 4 (tmux biocage_pushB3).
for a in "biocage_pushB0:0:0:" "biocage_pushB1:3:1:p110 p114 p120" "biocage_pushB2:1:2:p135 p140 p143 p146" "biocage_pushB3:4:3:p122 p129"; do
  IFS=: read -r s g l ds <<< "$a"; f=$OLD/$A/pilot_push/batch_lane$l.log
  if [ -f "$f" ] && ! grep -q "PUSH LANE $l DONE" "$f" && ! tmux has-session -t $s 2>/dev/null && ! pgrep -u "$USER" -f "pilot_push/push_batch.sh $g $l " >/dev/null && ! pgrep -u "$USER" -f "ops/push_lanes.sh $g $l " >/dev/null; then
    if [ -z "$ds" ]; then
      tmux new-session -d -s $s "mkdir -p /tmp/claude-1024; cd '$OLD/$A' && bash pilot_push/push_batch.sh $g $l 2 2>&1 | tee -a pilot_push/batch_lane$l.log"
    else
      tmux new-session -d -s $s "bash '$EVO/ops/push_lanes.sh' $g $l $ds 2>&1 | tee -a '$f'; sleep 86400"
    fi
  fi
done
# ASTM F2077 static tests (h55, astm_f2077/batch.sh, tmux biocage_astm, 11-19 11:20, by hand): skips designs with e11 json and tests with
# resources.json (an interrupted test re-runs, ~5 min). Marker ASTM BATCH DONE (foreman 11-19 12:0x)
f=$OLD/$A/astm_f2077/batch.log
if [ -f "$f" ] && ! grep -q 'ASTM BATCH DONE' "$f" && ! ls $OLD/$A/astm_f2077/lane_*.log >/dev/null 2>&1 && ! tmux has-session -t biocage_astm 2>/dev/null && ! pgrep -u "$USER" -f "astm_f2077/batch.sh" >/dev/null; then
  tmux new-session -d -s biocage_astm "mkdir -p /tmp/claude-1024; cd '$OLD/$A' && bash astm_f2077/batch.sh 2>&1 | tee -a astm_f2077/batch.log"
fi
# ASTM 2-lane hand-over (ops/astm_lanes.sh F|R, tmux biocage_astmF / biocage_astmR, log astm_f2077/lane_<L>.log): once a lane log
# exists batch.sh is not restarted; a lane re-takes its own claims, skips e11 / resources.json. Marker ASTM LANE <L> DONE (foreman 11-20 08:1x)
for l in F R; do
  f=$OLD/$A/astm_f2077/lane_$l.log
  if [ -f "$f" ] && ! grep -q "ASTM LANE $l DONE" "$f" && ! tmux has-session -t biocage_astm$l 2>/dev/null && ! pgrep -u "$USER" -f "ops/astm_lanes.sh $l" >/dev/null; then
    tmux new-session -d -s biocage_astm$l "bash '$EVO/ops/astm_lanes.sh' $l 2>&1 | tee -a '$f'; sleep 86400"
  fi
done
# 11-20 13:42 drive_mu03r_c.sh (p111 p051 p075, tmux biocage_mu03c, by hand), same pattern as _b, marker MU03R_C DONE (foreman 11-20 14:1x)
for a in "biocage_mu03b:drive_mu03r_b.sh:drive_b.log:MU03R_B DONE" "biocage_mu03G:drive_mu03G.sh 4:drive_G.log:MU03G DONE" "biocage_mu03c:drive_mu03r_c.sh:drive_c.log:MU03R_C DONE"; do
  IFS=: read -r s sh lg m <<< "$a"; f=$OLD/$A/pilot_mu03/$lg
  if [ -f "$f" ] && ! grep -q "$m" "$f" && ! tmux has-session -t $s 2>/dev/null && ! pgrep -u "$USER" -f "pilot_mu03/${sh%% *}" >/dev/null; then
    tmux new-session -d -s $s "cd '$OLD/$A' && bash pilot_mu03/$sh 2>&1 | tee -a pilot_mu03/$lg"
  fi
done
# 11-20 22:04 pilot_mu06/drive_mu06r.sh (tmux biocage_mu06, by hand): waits for the h19 insertion mu06_p062 (h19 resumes it), then
# h51 build (skips valid / started dirs) + run (skips done windows). Marker MU06R DONE in pilot_mu06/drive.log (foreman 11-20 22:1x)
f=$OLD/$A/pilot_mu06/drive.log
if [ -f "$f" ] && ! grep -q 'MU06R DONE' "$f" && ! tmux has-session -t biocage_mu06 2>/dev/null && ! pgrep -u "$USER" -f "pilot_mu06/drive_mu06r.sh" >/dev/null; then
  tmux new-session -d -s biocage_mu06 "cd '$OLD' && bash human_study/al_v2/pilot_mu06/drive_mu06r.sh >> $A/pilot_mu06/drive.log 2>&1"
fi
# 11-20 22:06 pilot_cyc3vnum/run_one.sh (tmux biocage_cycnum, 4 windows, by hand): h47 flexion window from the insertion checkpoint;
# done = <class>/<design>/resources_flexion.json (written at the end), a killed window re-runs from restart.feb (foreman 11-20 22:1x)
for a in "pilot_cyc3vdt:p062:4" "pilot_cyc3vpen:p062:0" "pilot_cyc3vdt:p124:4" "pilot_cyc3vpen:p124:3"; do
  IFS=: read -r c p g <<< "$a"; D=$A/$c/$p
  if [ -d "$OLD/$D" ] && [ ! -f "$OLD/$D/resources_flexion.json" ] && ! pgrep -u "$USER" -f "run_one.sh $c $p " >/dev/null && ! pgrep -u "$USER" -f "h47_restart_pilot.py run $D " >/dev/null; then
    cmd="cd '$OLD' && bash $A/pilot_cyc3vnum/run_one.sh $c $p $g 4 >> $A/pilot_cyc3vnum/lanes.log 2>&1"
    if tmux has-session -t biocage_cycnum 2>/dev/null; then tmux new-window -t biocage_cycnum "$cmd"; else tmux new-session -d -s biocage_cycnum "$cmd"; fi
  fi
done
# 11-20 22:43 / 22:52 pilot_mu03/drive_mu03r_d.sh fric (tmux biocage_mu03d, insertions = h19 jobs *_mu03d) and G 2 3 (tmux biocage_mu03dG,
# h18 lanes resume from case.dmp); h51 build skips valid dirs, run skips done windows. Marker MU03R_D <mode> DONE (foreman 11-20 23:08)
for a in "biocage_mu03d:GPUS=0,3,4:fric:drive_d.log" "biocage_mu03dG:GPUS=2,3:G 2 3:drive_dG.log"; do
  IFS=: read -r s g m lg <<< "$a"; f=$OLD/$A/pilot_mu03/$lg
  if [ -f "$f" ] && ! grep -q "MU03R_D ${m%% *} DONE" "$f" && ! tmux has-session -t $s 2>/dev/null && ! pgrep -u "$USER" -f "drive_mu03r_d.sh ${m%% *}" >/dev/null; then
    tmux new-session -d -s $s "cd '$OLD' && $g bash $A/pilot_mu03/drive_mu03r_d.sh $m >> $A/pilot_mu03/$lg 2>&1"
  fi
done
# 11-20 22:44 astm_f2077_plastic_hard/lane.sh (tmux biocage_astmP, by hand): skips tests with resources.json, a killed test re-runs from its
# deck. Marker ASTM PLASTIC LANE DONE in lane.log (foreman 11-20 23:08)
f=$OLD/$A/astm_f2077_plastic_hard/lane.log
if [ -f "$f" ] && ! grep -q 'ASTM PLASTIC LANE DONE' "$f" && ! tmux has-session -t =biocage_astmP 2>/dev/null && ! pgrep -u "$USER" -f "astm_f2077_plastic_hard/lane.sh" >/dev/null; then
  tmux new-session -d -s biocage_astmP "cd '$OLD' && bash $A/astm_f2077_plastic_hard/lane.sh >> $A/astm_f2077_plastic_hard/lane.log 2>&1"
fi
# 11-21 09:5x ops/astm_plastic_lanes.sh 1 / 2 (+ 3 / 4 11-21 10:4x, + 5 11-21 12:4x) (tmux biocage_astmP<L>, log plastic_hard/plastic_lane_<L>.log): reverse walk with claims,
# gated on lane.sh still at p064 (exits otherwise), so a relaunch is safe. Marker ASTM PLASTIC LANE <L> DONE (foreman 11-21 09:5x)
for l in 1 2 3 4 5 6; do
  f=$OLD/$A/astm_f2077_plastic_hard/plastic_lane_$l.log
  floor=; [ "$l" = 6 ] && floor=p064  # lane 6 (foreman 11-21 13:4x) does p066 / p065
  if [ -f "$f" ] && ! grep -q "ASTM PLASTIC LANE $l DONE" "$f" && ! tmux has-session -t biocage_astmP$l 2>/dev/null && ! pgrep -u "$USER" -f "ops/astm_plastic_lanes.sh $l" >/dev/null; then
    tmux new-session -d -s biocage_astmP$l "bash '$EVO/ops/astm_plastic_lanes.sh' $l $floor >> '$f' 2>&1"
  fi
done
# 11-21 14:34 pilot_push/push2_lane.sh <gpu> 4 <designs> (tmux biocage_push2, 3 windows, by hand): skips done_push_post2, h24 check, add2
# only without restart.feb, h47 window re-runs from restart.feb. Marker PUSH2 LANE <gpu> DONE in push2_lane<gpu>.log (foreman 11-21 14:5x)
# + lanes 3 / 4 / 5 (11-21 15:0x, by hand; log lane5 runs on GPU 2): entry = log no : gpu : designs, guard = the exact lane command
# line (two lanes share GPU 2) (foreman 11-21 15:5x)
for a in "0:0:p062 p036" "1:1:p051 p105" "2:2:p061 p140" "3:3:p039 p052 p060 p072 p082 p083 p086 p092 p063 p065 p066 p067 p076" \
         "4:4:p093 p100 p101 p117 p121 p142 p143 p077 p094 p110 p111 p122" "5:2:p064 p075 p088 p114 p120 p129 p145 p124 p131 p135 p139 p146"; do
  IFS=: read -r l g ds <<< "$a"; f=$OLD/$A/pilot_push/push2_lane$l.log
  if [ -f "$f" ] && ! grep -q "PUSH2 LANE $g DONE" "$f" && ! pgrep -u "$USER" -f "push2_lane.sh $g 4 $ds" >/dev/null; then
    cmd="cd '$OLD' && bash $A/pilot_push/push2_lane.sh $g 4 $ds >> $A/pilot_push/push2_lane$l.log 2>&1"
    if tmux has-session -t biocage_push2 2>/dev/null; then tmux new-window -t biocage_push2 "$cmd"; else tmux new-session -d -s biocage_push2 "$cmd"; fi
  fi
done
# 11-21 16:19 pilot_push/push2_retry.sh <gpu> 4 <designs> (tmux biocage_push2r, 2 windows, by hand). It skips designs that already have
# case_first_fail.log, so the relaunch goes through ops/push2r_lane.sh (h47 + e09 for an interrupted retry). Marker PUSH2 RETRY <gpu> DONE
# in push2_retry.log (shared by both lanes); guard = either script with the exact arguments (foreman 11-21 16:5x)
for a in "0:p075 p093" "1:p039 p064"; do
  IFS=: read -r g ds <<< "$a"; f=$OLD/$A/pilot_push/push2_retry.log
  if [ -f "$f" ] && ! grep -q "PUSH2 RETRY $g DONE" "$f" && ! pgrep -u "$USER" -f "push2_retry.sh $g 4 $ds" >/dev/null && ! pgrep -u "$USER" -f "push2r_lane.sh $g 4 $ds" >/dev/null; then
    cmd="bash '$EVO/ops/push2r_lane.sh' $g 4 $ds >> '$f' 2>&1"
    if tmux has-session -t biocage_push2r 2>/dev/null; then tmux new-window -t biocage_push2r "$cmd"; else tmux new-session -d -s biocage_push2r "$cmd"; fi
  fi
done
# 11-21 14:40 pilot_mu03/drive_mu03rN.sh (tmux biocage_mu03N, by hand) = 2 h51 halves; G half moved 14:46 from GPU 5 (other user 39.7 / 40 GB)
# to GPU 4 via ops/mu03rN_lane.sh G 4 (tmux biocage_mu03NG). Relaunch each half on its own: marker h51 RELG_PL DONE in drive_N_<half>.log
# (not MU03RN DONE, the driver echoes it when fric alone ends). Guards: the driver, the lane script, the half's h51 run (foreman 11-21 14:5x)
for a in "fric:0,3:p014:extension" "G:4:p095:extension"; do
  IFS=: read -r h g w1 w2 <<< "$a"; f=$OLD/$A/pilot_mu03/drive_N_$h.log
  if [ -f "$f" ] && ! grep -q 'RELG_PL DONE' "$f" && ! tmux has-session -t biocage_mu03N$h 2>/dev/null && ! pgrep -u "$USER" -f "ops/mu03rN_lane.sh $h" >/dev/null \
     && ! pgrep -u "$USER" -f "h51_relG_fallback.py run .*$w1:$w2" >/dev/null && { [ "$h" = G ] || ! pgrep -u "$USER" -f "pilot_mu03/drive_mu03rN.sh" >/dev/null; }; then
    tmux new-session -d -s biocage_mu03N$h "bash '$EVO/ops/mu03rN_lane.sh' $h $g >> '$f' 2>&1"
  fi
done
# 11-21 15:20 pilot_mu03/drive_mu03r_e.sh fric 0 / G 1 / G 3 (tmux biocage_mu03e, by hand): h51 build skips valid dirs, run skips done
# windows; relaunch through ops/mu03e_lane.sh (resumes an interrupted h18 insertion first). Marker MU03R_E <kind> lane <gpu> DONE (foreman 11-21 15:5x)
for a in "fric:0:drive_e_fric.log:p036 p066 p067 p094 p124 p146" "G:1:drive_e_G1.log:p039 p050 p064 p068 p071 p082 p084 p088 p097" \
         "G:3:drive_e_G3.log:p101 p109 p116 p121 p127 p130 p140 p149"; do
  IFS=: read -r k g lg ds <<< "$a"; f=$OLD/$A/pilot_mu03/$lg
  if [ -f "$f" ] && ! grep -q "MU03R_E $k lane $g DONE" "$f" && ! pgrep -u "$USER" -f "drive_mu03r_e.sh $k $g " >/dev/null && ! pgrep -u "$USER" -f "mu03e_lane.sh $k $g " >/dev/null; then
    cmd="bash '$EVO/ops/mu03e_lane.sh' $k $g $ds >> '$f' 2>&1"
    if tmux has-session -t =biocage_mu03e 2>/dev/null; then tmux new-window -t =biocage_mu03e "$cmd"; else tmux new-session -d -s biocage_mu03e "$cmd"; fi
  fi
done
# 11-21 15:12 pilot_cyc3vnum/run_one.sh pilot_cyc3vrN p124 then pilot_cyc3vGN p121, GPU 3, 6 cores (tmux biocage_cycN, by hand): same rule as
# cycnum above (done = resources_flexion.json); the not-done ones are chained again in one window (foreman 11-21 15:5x)
cmd=
for a in "pilot_cyc3vrN:p124" "pilot_cyc3vGN:p121"; do
  IFS=: read -r c p <<< "$a"; D=$A/$c/$p
  if [ -d "$OLD/$D" ] && [ ! -f "$OLD/$D/resources_flexion.json" ] && ! pgrep -u "$USER" -f "run_one.sh $c $p " >/dev/null && ! pgrep -u "$USER" -f "h47_restart_pilot.py run $D " >/dev/null; then
    cmd="$cmd${cmd:+; }bash $A/pilot_cyc3vnum/run_one.sh $c $p 3 6 >> $A/pilot_cyc3vnum/lanes.log 2>&1"
  fi
done
[ -n "$cmd" ] && ! tmux has-session -t =biocage_cycN 2>/dev/null && tmux new-session -d -s biocage_cycN "cd '$OLD' && $cmd"
# 11-21 14:57 astm_f2077_mesh/lane.sh (tmux biocage_astmM, by hand): skips tests with resources.json, a killed test re-runs from its deck.
# Marker ASTM MESH LANE DONE in lane.log (foreman 11-21 15:5x)
f=$OLD/$A/astm_f2077_mesh/lane.log
if [ -f "$f" ] && ! grep -q 'ASTM MESH LANE DONE' "$f" && ! tmux has-session -t =biocage_astmM 2>/dev/null && ! pgrep -u "$USER" -f "astm_f2077_mesh/lane.sh" >/dev/null; then
  tmux new-session -d -s biocage_astmM "cd '$OLD' && bash $A/astm_f2077_mesh/lane.sh >> $A/astm_f2077_mesh/lane.log 2>&1"
fi
# 11-21 14:51 pilot_staticR_run.sh 1 5 flexion (tmux biocage_staticR, by hand; extension done 14:54): h47 window re-runs from restart.feb.
# Done = pilot_staticR/p062/resources_flexion.json (foreman 11-21 15:5x)
D=$A/pilot_staticR/p062
if [ -d "$OLD/$D/w_flexion" ] && [ ! -f "$OLD/$D/resources_flexion.json" ] && ! pgrep -u "$USER" -f "pilot_staticR_run.sh" >/dev/null && ! pgrep -u "$USER" -f "h47_restart_pilot.py run $D " >/dev/null; then
  tmux new-session -d -s biocage_staticR "cd '$OLD' && bash $A/pilot_staticR_run.sh 1 5 flexion >> $A/pilot_staticR/run.log 2>&1"
fi
# 11-22 01:05 pilot_cyc8v/lanes8.sh <gpu> 6 <design> (tmux biocage_cyc8, 3 windows, by hand, PI item 14): relaunch through
# ops/cyc8_lane.sh (skips a finished insertion / valid build). Done = the design's 'ended' / 'not normal' line in lanes8.log (foreman 11-22 01:2x)
f=$OLD/$A/pilot_cyc8v/lanes8.log
for a in "4:p124" "2:p036" "0:p140"; do
  IFS=: read -r g p <<< "$a"
  if [ -f "$f" ] && ! grep -qE "$p (process-G 8-cycle run ended|8-cycle window ended|insertion not normal)" "$f" && ! pgrep -u "$USER" -f "lanes8.sh $g 6 $p" >/dev/null \
     && ! pgrep -u "$USER" -f "cyc8_lane.sh $g 6 $p" >/dev/null && ! pgrep -u "$USER" -f "h18_run_gpu_case.py .*pilot_cyc8v[A-Za-z]*/$p " >/dev/null \
     && ! pgrep -u "$USER" -f "h47_restart_pilot.py run .*pilot_cyc8vrN/$p " >/dev/null; then
    cmd="bash '$EVO/ops/cyc8_lane.sh' $g 6 $p >> '$f' 2>&1"
    if tmux has-session -t =biocage_cyc8 2>/dev/null; then tmux new-window -t =biocage_cyc8 "$cmd"; else tmux new-session -d -s biocage_cyc8 "$cmd"; fi
  fi
done
# 11-22 01:05 pilot_mu03/drive_newton_confirm.sh (tmux biocage_newtonC, by hand, PI item 12): 2 h51 halves; relaunch the half whose
# h51 build / run is not live through ops/newtonC_lane.sh (appends the logs). Marker NEWTON_CONFIRM DONE in drive_NC_fric.log (foreman 11-22 01:2x)
f=$OLD/$A/pilot_mu03/drive_NC_fric.log
if [ -f "$f" ] && ! grep -q 'NEWTON_CONFIRM DONE' "$f" && ! pgrep -u "$USER" -f "drive_newton_confirm.sh" >/dev/null && ! pgrep -u "$USER" -f "ops/newtonC_lane.sh" >/dev/null; then
  h=; pgrep -u "$USER" -f "h51_relG_fallback.py (build p105|run 2 1,3 6 p105:flexion)" >/dev/null || h=fric
  pgrep -u "$USER" -f "h51_relG_fallback.py (build p052|run 1 4 6 p052:flexion)" >/dev/null || { [ -n "$h" ] && h=both || h=G; }
  [ -n "$h" ] && tmux new-session -d -s biocage_newtonC "bash '$EVO/ops/newtonC_lane.sh' $h"
fi
# 11-22 06:05 pilot_mu03/fill_newton_e.sh G 2 <4 windows> (tmux biocage_fillN, by hand, PI item 12): h51 build skips valid / started dirs,
# run skips done windows, log appended, so a plain relaunch is safe. Marker FILL_NEWTON_E G ... DONE in fill_N_G.log (foreman 11-22 06:1x)
f=$OLD/$A/pilot_mu03/fill_N_G.log
if [ -f "$f" ] && ! grep -q 'FILL_NEWTON_E G .* DONE' "$f" && ! pgrep -u "$USER" -f "pilot_mu03/fill_newton_e.sh G " >/dev/null \
   && ! pgrep -u "$USER" -f "h51_relG_fallback.py run 1 2 6 p050:extension" >/dev/null && ! tmux has-session -t =biocage_fillN 2>/dev/null; then
  tmux new-session -d -s biocage_fillN "cd '$OLD' && bash $A/pilot_mu03/fill_newton_e.sh G 2 p050:extension p064:extension p116:extension p121:extension >> $A/pilot_mu03/fill_N_G.log 2>&1"
fi
# 11-22 01:08 numconv_hz01/lane16b.sh 1 4 p036 p052 p060 p113 (tmux biocage_16b, by hand, PI item 16(b)): relaunch through
# ops/num16b_lane.sh (skips ended designs, builds only unbuilt ones). Marker LANE16B DONE in lane16b.log (foreman 11-22 02:1x)
f=$OLD/$A/numconv_hz01/lane16b.log
if [ -f "$f" ] && ! grep -q 'LANE16B DONE' "$f" && ! pgrep -u "$USER" -f "(numconv_hz01/lane16b|ops/num16b_lane)\.sh" >/dev/null \
   && ! pgrep -u "$USER" -f "h18_run_gpu_case.py .*numconv_hz01/" >/dev/null && ! tmux has-session -t =biocage_16b 2>/dev/null; then
  tmux new-session -d -s biocage_16b "bash '$EVO/ops/num16b_lane.sh' 1 4 p036 p052 p060 p113 >> '$f' 2>&1"
fi
# 11-22 09:06 numconv_hz01/lane16c.sh 1 4 numconv_hz01/p146 numconv_hz01/inplane/p060 numconv_hz01/inplane/p052 (tmux biocage_16c, by hand,
# PI item 16(b) second pass): relaunch through ops/num16c_lane.sh (skips ended designs). Marker LANE16C DONE in lane16c.log (foreman 11-22 09:1x)
f=$OLD/$A/numconv_hz01/lane16c.log
if [ -f "$f" ] && ! grep -q 'LANE16C DONE' "$f" && ! pgrep -u "$USER" -f "(numconv_hz01/lane16c|ops/num16c_lane)\.sh" >/dev/null \
   && ! pgrep -u "$USER" -f "h18_run_gpu_case.py .*numconv_hz01/" >/dev/null && ! tmux has-session -t =biocage_16c 2>/dev/null; then
  tmux new-session -d -s biocage_16c "bash '$EVO/ops/num16c_lane.sh' 1 4 numconv_hz01/p146 numconv_hz01/inplane/p060 numconv_hz01/inplane/p052 >> '$f' 2>&1"
fi
# 11-21 20:48 pilot_push/push2_finish.sh + pilot_mu03/finish_e.sh (tmux biocage_finish, by hand): waiters, then retry + summary / verdict
# pipeline. Relaunch through ops/finish_lane.sh. Markers PUSH2 FINISH DONE in push2_retry.log, PIPELINE_E DONE in pipeline_e.log (foreman 11-22 01:2x)
for a in "push2:$OLD/$A/pilot_push/push2_retry.log:PUSH2 FINISH DONE:push2_finish.sh" "e:$EVO/results/method/fric/pipeline_e.log:PIPELINE_E DONE:finish_e.sh"; do
  IFS=: read -r k f m s <<< "$a"
  if ! grep -qs "$m" "$f" && ! pgrep -u "$USER" -f "$s" >/dev/null && ! pgrep -u "$USER" -f "ops/finish_lane.sh $k" >/dev/null; then
    cmd="bash '$EVO/ops/finish_lane.sh' $k"
    if tmux has-session -t =biocage_finish 2>/dev/null; then tmux new-window -t =biocage_finish "$cmd"; else tmux new-session -d -s biocage_finish "$cmd"; fi
  fi
done
# FEBio core pinner (foreman 11-10 22:5x): moves each new FEBio run once to disjoint idle cores on its GPU's NUMA node (log work/ops/febio_pin.log)
tmux has-session -t febio_pin 2>/dev/null || pgrep -u "$USER" -f "ops/febio_pin.sh" >/dev/null || tmux new-session -d -s febio_pin "cd '$EVO' && while true; do ops/febio_pin.sh; echo \"\$(date '+%m-%d %H:%M:%S') febio_pin exit \$?, restart in 30 s\" >> work/ops/febio_pin.log; sleep 30; done"
# report real work as Jupyter activity so the idle culler does not stop a computing server (PI-authorised 2026-10-26)
tmux has-session -t evo_keepalive 2>/dev/null || tmux new-session -d -s evo_keepalive "cd '$EVO' && python ops/activity_keepalive.py"
echo "$(date -Is) resume_all" >> "$EVO/work/agents/resume_all.log"
tmux ls
