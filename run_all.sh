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
echo "done"
