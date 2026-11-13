# Data

Raw data are **not** in this repository. Download them from their publishers and keep their citations.

## Main dataset: wearable SSVEP (Zhu et al. 2021)

- F. Zhu, L. Jiang, G. Dong, X. Gao, Y. Wang, "An Open Dataset for Wearable SSVEP-Based Brain-Computer
  Interfaces", *Sensors* 21(4):1256, 2021. doi: 10.3390/s21041256
- Download: figshare, doi [10.6084/m9.figshare.13560281](https://doi.org/10.6084/m9.figshare.13560281)
  (about 974 MB), also listed at http://bci.med.tsinghua.edu.cn/download.html
- Licence shown by figshare: **CC BY 4.0** (checked 12 Nov 2026). Cite the paper when you use the data.
- Content: `S001.mat` ... `S102.mat`, `Impedance.mat`, `Subjects_Information.mat`, `Readme.pdf`,
  `stimulation_information.pdf`.

## Reference dataset: BETA (Liu et al. 2020)

- B. Liu, X. Huang, Y. Wang, X. Chen, X. Gao, "BETA: A Large Benchmark Database Toward SSVEP-BCI Application",
  *Frontiers in Neuroscience* 14:627, 2020. doi: 10.3389/fnins.2020.00627
- Download: figshare, doi [10.6084/m9.figshare.12264401](https://doi.org/10.6084/m9.figshare.12264401)
  (about 5.3 GB).
- Licence shown by figshare: **CC BY 4.0** (checked 12 Nov 2026).
- Content: `S1.mat` ... `S70.mat`, `Description.pdf`, `note.txt`.
- The project uses nine of the 64 channels. `scripts/beta_reduce.py` (numpy only) writes them in single
  precision as `S<n>.npy` with a small `S<n>.json` (tables, channel names, MD5 of the source file): 0.4 GB
  instead of 5.3 GB. `ssvep.beta.load_subject` reads the original or the reduced files and returns the same
  numbers (unit test). The results in this repository were computed from the reduced files, made from
  originals whose MD5 equals figshare's for all 70 files.
- The phase table stored in the files differs from the paper by a constant; the authors published a
  correction on 15 June 2022 (`Description.pdf`). The decoders of M1 do not use the phase table.

## Expected layout

Unzip each archive anywhere and pass the folders to the scripts (defaults shown):

```
data/wearable_ssvep/S001.mat ... S102.mat, Impedance.mat, Subjects_Information.mat
data/beta/S1.mat ... S70.mat          (or the reduced S1.npy, S1.json, ...)
```

```bash
WEARABLE_DIR=/path/to/13560281 BETA_DIR=/path/to/12264401 ./run_all.sh
```

## Check your copy

`data_manifest.csv` lists the size, MD5 and SHA-256 of every raw file used here. `scripts/m0_inventory.py`
recomputes them and stops if a file differs. For the wearable dataset the MD5 values are also the ones
published by figshare.
