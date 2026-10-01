# Data

Nothing in this folder is committed. The project uses **two** datasets:

| Dataset | Role | Where | Notes |
|---|---|---|---|
| **UID2021** | O1 benchmark + O2 stress test (human MOS) | https://github.com/Hou-Guojia/UID2021 → Google Drive link | 60 raw + 900 enhanced (15 methods), MOS from 77 observers. Non-commercial use; cite Hou et al., ACM TOMM 2023. The Kaggle notebook downloads it automatically. |
| **RUOD** | O3 utility labels + O4 predictor (detection boxes) | https://github.com/dlut-dimt/RUOD | Cite 14,000 imgs / 74,903 objects (source paper); record which copy you used. Needed from Week 5. |

Optional, only if time allows: a second MOS dataset (SAUD, https://github.com/yia-yuese/SAUD-Dataset) to show the O1 finding is not dataset-specific, and DUO (https://github.com/chongweiliu/DUO) for cross-dataset detection generalisation.

Locally, put datasets under `data/<Name>/`. On Kaggle, either let the notebook download them into `/kaggle/working/data`, or attach a Kaggle Dataset and set `UID2021_ROOT` / `RUOD_ROOT` to its `/kaggle/input/...` path.
