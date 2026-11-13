#!/usr/bin/env bash
# Full pipeline, in milestone order.
# WEARABLE_DIR: unzipped wearable SSVEP dataset (S001.mat ... S102.mat, Impedance.mat, Subjects_Information.mat)
# BETA_DIR:     unzipped BETA dataset (S1.mat ... S70.mat); optional for M0
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
if [ -d "$BETA_DIR" ]; then
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

echo "M1  the numbers quoted in the report, and the figures"
python scripts/m1_summary.py | tee logs/m1_summary.log
python scripts/m1_figures.py
echo "done"
