#!/usr/bin/env bash
# Full pipeline, in milestone order.
# WEARABLE_DIR: unzipped wearable SSVEP dataset (S001.mat ... S102.mat, Impedance.mat, Subjects_Information.mat)
# BETA_DIR:     BETA dataset: the original S1.mat ... S70.mat, or the files reduced by scripts/beta_reduce.py
#               (S1.npy, S1.json, ...). Optional: the BETA steps are skipped if the folder is missing.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
WEARABLE_DIR="${WEARABLE_DIR:-data/wearable_ssvep}"
BETA_DIR="${BETA_DIR:-data/beta}"
mkdir -p logs

echo "M0  unit tests on synthetic signals (gate: must pass before the data are used)"
python -m pytest -q -p no:cacheprovider tests

echo "M0  label-free inventory, all 102 subjects"
python scripts/m0_inventory.py --raw "$WEARABLE_DIR" | tee logs/m0_inventory.log
if [ -d "$BETA_DIR" ] && ls "$BETA_DIR"/S1.mat >/dev/null 2>&1; then
  python scripts/check_beta_files.py --raw "$BETA_DIR"
fi

echo "M0  timing, spectra and SNR, development subjects only"
python scripts/m0_signal_checks.py --raw "$WEARABLE_DIR" | tee logs/m0_signal_checks.log

echo "M0  figures and the numbers quoted in the audit"
python scripts/m0_figures.py
python scripts/m0_summary.py | tee logs/m0_summary.log

echo "M1  edge error of the filtering variants on synthetic epochs (no data)"
python scripts/m1_edge_transients.py | tee logs/m1_edge_transients.log

echo "M1  standard decoders, development subjects only (about 8 minutes on two cores)"
python scripts/m1_baselines_wearable.py --raw "$WEARABLE_DIR" | tee logs/m1_baselines_wearable.log
echo "M1  the two post hoc filtering variants (about 5 minutes)"
python scripts/m1_baselines_wearable.py --raw "$WEARABLE_DIR" --diagnostic | tee logs/m1_baselines_wearable_diagnostic.log

echo "M1  second implementation on one person, and the decision-bias diagnostic"
python scripts/m1_crosscheck.py --raw "$WEARABLE_DIR" | tee logs/m1_crosscheck.log
python scripts/m1_decision_bias.py --raw "$WEARABLE_DIR" | tee logs/m1_decision_bias.log

if [ -d "$BETA_DIR" ]; then
  echo "M1  BETA (reference dataset, gate G5): data check, standard decoders (about 25 minutes), gate"
  python scripts/m1_beta_check.py --raw "$BETA_DIR" | tee logs/m1_beta_check.log
  python scripts/m1_baselines_beta.py --raw "$BETA_DIR" | tee logs/m1_baselines_beta.log
  python scripts/m1_beta_summary.py | tee logs/m1_beta_summary.log
fi

echo "M1  the numbers quoted in the report, and the figures"
python scripts/m1_summary.py | tee logs/m1_summary.log
python scripts/m1_figures.py

echo "M2  step 0: choice of the pipeline (development subjects only)"
python scripts/m2_pipeline_choice.py --raw "$WEARABLE_DIR" | tee logs/m2_pipeline_choice.log
echo "M2  baselines with the chosen pipeline (about 3 minutes)"
python scripts/m2_baselines.py --raw "$WEARABLE_DIR" | tee logs/m2_baselines.log
echo "M2  new users, leave-one-subject-out (about 10 minutes; writes about 0.7 GB to a temporary folder)"
python scripts/m2_new_users.py --raw "$WEARABLE_DIR" | tee logs/m2_new_users.log
python scripts/m2_summary.py | tee logs/m2_summary.log
python scripts/m2_figures.py

echo "M3  24 small networks (about 50 minutes on two cores; finished networks are kept and skipped)"
python scripts/m3_train.py --raw "$WEARABLE_DIR" | tee logs/m3_train.log
python scripts/m3_evaluate.py | tee logs/m3_evaluate.log
python scripts/m3_compute.py | tee logs/m3_compute.log
python scripts/m3_summary.py | tee logs/m3_summary.log
python scripts/m3_figures.py

echo "M4  decision of every trial with the frozen decoder (about 4 minutes), summary and figures"
python scripts/m4_decode.py --raw "$WEARABLE_DIR" | tee logs/m4_decode.log
python scripts/m4_summary.py | tee logs/m4_summary.log
python scripts/m4_figures.py

echo "Final  rehearsal of the final evaluation on development people only (6 networks, about 12 minutes; p-values withheld)"
python scripts/final_evaluation.py prepare --set rehearsal --raw "$WEARABLE_DIR" | tee logs/final_rehearsal_prepare.log
python scripts/final_evaluation.py evaluate --set rehearsal --raw "$WEARABLE_DIR" | tee logs/final_rehearsal.log

echo "Final  template and 6 networks for the lockbox people, built from the 68 development people only (about 18 minutes)"
python scripts/final_evaluation.py prepare --set lockbox --raw "$WEARABLE_DIR" | tee logs/final_lockbox_prepare.log
# The opening of the lockbox is not part of this script: it is done once, by hand, from the commit tagged
# pre-lockbox (docs/milestones/final_evaluation_plan.md).
echo "done"
