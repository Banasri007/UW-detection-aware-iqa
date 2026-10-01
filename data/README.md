# Data

Nothing in this folder is committed. Put datasets under `DATA_ROOT` (defaults to this folder; on Colab set `DATA_ROOT=/content/drive/MyDrive/uwiqa_data`).

| Folder | Dataset | Where to get it | Priority |
|---|---|---|---|
| `UIEB/` | UIEB (raw-890, reference-890, challenging-60) | https://li-chongyi.github.io/proj_benchmark.html | Week 1 |
| `EUVP/` | EUVP (need `test_samples/Inp`, `test_samples/GTr`) | https://irvlab.cs.umn.edu/resources/euvp-dataset | Week 1 |
| `UID2021/` | UID2021 — 60 raw + 900 enhanced, MOS from 52 observers | https://github.com/Hou-Guojia/UID2021 (Drive link in README) | **Week 1, MOS** |
| `SAUD/` | SAUD — 100 raw + 1,000 enhanced | https://github.com/yia-yuese/SAUD-Dataset | **Week 1, MOS** |
| `UWIQA/` | UWIQA — 890 raw, coarse MOS | locate via the paper; verify license | Week 1–2, MOS |
| `RUOD/` | RUOD detection (cite 14,000 imgs / 74,903 objects) | https://github.com/dlut-dimt/RUOD | Week 5–6 |
| `DUO/` | DUO detection | https://github.com/chongweiliu/DUO | Week 10 |
| `Brackish/` | Brackish (video frames — split **by sequence**) | Kaggle / Aalborg Univ. VAP | Week 10 |

After downloading a MOS dataset, open its score file, fill in the `TODO`s in `configs/datasets.yaml`, and run `python scripts/build_manifests.py --only <name>`.

Record the exact image count you got for RUOD (source paper vs. the 13,112 re-hosted copy) in `docs/NEXT_STEPS.md`.
