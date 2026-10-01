# Detection-Aware NR-IQA for Enhanced Underwater Images

Do quality metrics for enhanced underwater images (UIQM, UCIQE, modern deep NR-IQA) agree with humans, and can a learned no-reference predictor tell, **from the raw image alone**, whether enhancing it will help object detection?

Full context: [docs/HANDOFF.md](docs/HANDOFF.md). Plan and status: [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md).

## Layout
```
src/uwiqa/metrics   UIQM, UCIQE (2 variants), pyiqa registry (13 deep/classic NR metrics incl. URanker)
src/uwiqa/eval      SRCC / PLCC (4-param logistic) / KRCC, bootstrap CIs, paired tests, intra-scene SRCC
src/uwiqa/enhance   classical UIE (CLAHE, gray-world, UDCP, Ancuti fusion) + over-enhancement sweeps
src/uwiqa/data      standard manifest format + dataset builders
src/uwiqa/detect    (O3, after Week-4 gate)        src/uwiqa/model  (O4)
scripts/            check_env, build_manifests, score_metrics (resumable), benchmark, stress_test
configs/datasets.yaml   tests/   results/   notebooks/
```

## Setup
Local (CPU — hand-crafted metrics, tests, analysis):
```bash
pip install -e ".[dev]"
python -m pytest -q
```
Colab / Kaggle (GPU — deep metrics, detection):
```bash
git clone <your-repo-url> && cd FCV_Project
pip install -e ".[iqa,detect,dev]"
export DATA_ROOT=/content/drive/MyDrive/uwiqa_data RESULTS_ROOT=/content/drive/MyDrive/uwiqa_results
python scripts/check_env.py
```

## Pipeline (O1, O2)
```bash
python scripts/build_manifests.py
python scripts/score_metrics.py --dataset uid2021       # resumable; re-run after a disconnect
python scripts/benchmark.py --dataset uid2021           # prints the Week-4 gate verdict
python scripts/stress_test.py --dataset uieb --n 50
```
