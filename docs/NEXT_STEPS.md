# Next Steps & Proposed Improvements

Status date: 2026-10-01. Week 1 of 14.

## Done (handoff §13, steps 1–5)
- [x] Repo scaffold, installable package `uwiqa`, git initialised
- [x] `pyiqa` 0.1.16 installs; registry wraps 13 NR metrics + UIQM/UCIQE (weights not yet downloaded — run `scripts/check_env.py` on Kaggle)
- [x] UIQM: vectorised; tested against a loop port of the reference implementation (exact match)
- [x] UCIQE: `paper` and `legacy_cv2` variants (ports disagree — this is itself reportable)
- [x] Manifest format + UIEB/EUVP builders + generic MOS-table builder
- [x] Correlation harness: SRCC / PLCC (4-param logistic) / KRCC, bootstrap CIs, paired bootstrap test, intra-scene SRCC
- [x] Classical UIE (CLAHE, gray-world, UDCP, fusion) and O2 sweeps (saturation, contrast, red shift, unsharp)
- [x] 41 unit tests passing
- [x] Kaggle notebook `notebooks/01_kaggle_benchmark_uid2021.ipynb`

## Scope decision (2026-10-01): two datasets, Kaggle only
No single dataset has both human quality scores and detection boxes, so the minimum is one of each:
- **UID2021** for O1 + O2 (its 60 raw images also serve the stress test, so UIEB/EUVP are dropped)
- **RUOD** for O3 + O4

Consequences, stated honestly in the write-up:
- O1 becomes a single-dataset benchmark. Gap 4 ("fragmented subjective datasets") is no longer addressed; drop it from the claims or add SAUD later (~1 h of Kaggle inference).
- ~~O5 becomes cross-split only~~ → **restored**: the Kaggle ODverse33 copy ships RUOD *and* DUO in YOLO format, so the cross-dataset check costs no extra download. DUO's 4 classes (echinus, holothurian, starfish, scallop) correspond to RUOD's seaurchin / seacucumber / starfish / scallop.
- RUOD is the **ODverse33 re-split** (test = 1,400, not 4,200). Fine for our purpose; state it in the paper and don't compare mAP against numbers on the original split.

## Immediate next steps (you)
1. Import the notebook into Kaggle (GPU, Internet on), run cells 1–4.
2. From the `inspect_dataset` output, fill the three values in cell 5.
3. Run the rest: `check_env`, scoring, benchmark (prints the **Week-4 gate**: TOPIQ_NR SRCC ≳ 0.7), stress test.
4. Attach Kaggle dataset `skycol/underwater-domain-in-odverse33` and run notebook 02 (CPU) to confirm RUOD/DUO counts, classes, resolution and JPEG quality.

## Detection data — verified on Kaggle (notebook 02, 2026-10-01)
| | images | objects | split (train/val/test) | notes |
|---|---|---|---|---|
| RUOD | 14,000 | 74,904 (paper 74,903) | 11,200 / 1,400 / 1,400 | complete dataset, ODverse33 80/10/10 re-split; 10 classes, 0 unlabeled images |
| DUO | 7,782 | 74,515 (= paper) | 6,225 / 778 / 779 | 65 unlabeled images; classes holothurian, echinus, scallop, starfish |

- **DUO class ids 0–3 = RUOD class ids 0–3** (same names, same order), so a RUOD-trained detector evaluates on DUO directly by restricting to classes 0–3.
- Images are at native resolution (720×405 up to 3840×2160), not resized. JPEG quality: RUOD ≈ q85 (mean luma quant 16.1), DUO ≈ q95 (5.8).
- The uploader's DUO `data.yaml` has a stray line and Windows paths; `train_detector.py` writes its own.

### Near-duplicate check (dHash 256-bit, threshold 20/256)
- 5,905 near-duplicate pairs: **3,158 RUOD↔DUO**, 2,580 within RUOD (**965 cross the official ODverse33 splits**), 167 within DUO.
- Visual check: d=0 pairs are identical frames; even d=20 pairs are adjacent frames of the same video. The threshold is conservative, so notebook 03 widens it to 32 and inspects the 21–32 band.
- 16,843 groups, 4,240 with more than one image, largest 66.
- **Consequence: the official splits leak and DUO is not independent of RUOD.** We re-split RUOD by duplicate group and evaluate DUO only on images sharing no group with RUOD (`make_splits.py`). Say this in the paper; it is a useful finding in its own right.

## O3 protocol
1. **Leakage-safe RUOD re-split by duplicate group** (`make_splits.py`, fractions in `uwiqa/data/splits.py`):
   `det_train` 45% / `det_val` 5% train the frozen reference detector (YOLO11-s); `pred_train` 30% / `pred_val` 10% / `pred_test` 10% are never seen by the detector.
2. **Utility labels on pred_\*** (≈ 7,000 images). The predictor trains on pred_train, is tuned on pred_val, and is reported on pred_test. DUO-clean is the cross-dataset test (O5).
3. **Enhance on the fly, never store enhanced images.** The predictor only sees the raw image, so we only need Δ: enhance → detect → score → discard. Cache per-image detections instead (a few MB). This keeps us under Kaggle's 20 GB `/kaggle/working` limit (storing 7,000 × 5 enhanced 4K PNGs would not fit).
4. Enhanced outputs stay in memory, so no extra JPEG generation. Enhancers will amplify RUOD's q≈85 block artefacts; that is part of the real effect, so leave the inputs as they are.
5. Null-enhancement noise floor: also score a JPEG-q95 re-encode of each raw image to estimate label noise (improvement #4 below).

## Reference detector — trained (notebook 03 commit, 2026-10-01)
YOLO11-s, 640 px, 100 epochs on `det_train` (6,300 images), 1.97 h on 2×T4; converged (val flat over the last epochs).

| set | images | mAP50 | mAP50-95 |
|---|---|---|---|
| det_val | 700 | 0.811 | 0.569 |
| RUOD pred_test (held out) | 1,400 | 0.798 | 0.556 |
| DUO clean (cross-dataset, classes 0–3) | 4,539 | 0.639 | 0.387 |

- Held-out ≈ val, so no overfitting through the split. Weakest RUOD classes: corals (0.56 mAP50) and jellyfish (0.59).
- DUO drop is mostly echinus recall (0.54; ~9 small urchins per image). Precision stays high (0.96).

## O3 labelling — implemented (notebook 04)
- `scripts/build_utility_labels.py`: per image, enhancers applied in memory at 1280 px, then the frozen detector; per-image AP / AP50 / F1 for `raw`, `null_jpeg95`, clahe, gray_world, udcp, fusion and FUnIE-GAN. All detections are saved for offline policy evaluation.
- `uwiqa.detect.metrics`: COCO-style per-image AP and dataset mAP. Verified against Ultralytics on identical predictions (Δ ≤ 0.005 mAP; the residual is the interpolation scheme).
- Deep enhancers: FUnIE-GAN uses the official repo code and weights. U-shape Transformer and PUIE-Net (PyTorch, Google Drive weights) are possible additions. Water-Net and Ucolor are TF1-only, so they were dropped as infeasible.

### Smoke test (40 RUOD pred_test images, 2026-10-02)
- 0.50 s/image on T4 → ~1 h for ruod_pred (7,000) + ~40 min for duo_clean (4,539).
- Raw dataset mAP at 1280 px work size: 0.794 / 0.563 (native-resolution Ultralytics eval: 0.798 / 0.556), so the resizing protocol does not change the detector's behaviour.
- **Noise floor is small:** null_jpeg95 Δap = −0.001 ± 0.033.
- **Every enhancer hurts on average** (mean Δap: clahe −0.05, udcp −0.07, funiegan −0.10, fusion −0.13, gray_world −0.14), **but each helps on 12–22% of images.** The per-image signal is non-degenerate (the Week-8 pivot rule is not triggered), and blanket enhancement is worse than none. This matches Wang et al. 2024 and Saleem et al. 2025.
- Caveat for the write-up: the detector was trained on raw images, so enhanced inputs are slightly out-of-distribution for it (protocol (a) in the handoff). Protocol (b), a detector trained with enhancement augmentation, is the sensitivity check.

## Kaggle workflow
Imported notebooks are frozen copies, so all logic lives in the repo. The first cell of every notebook is
`%run /kaggle/working/repo/scripts/kaggle_setup.py`, which resets the clone to `origin/main`, reinstalls, and
sets every `*_ROOT`. Re-running it picks up new code; the notebook never needs re-importing. Session-specific
values go in the untracked `configs/local.yaml` via `set_local_config()`. Notebooks are generated by
`scripts/make_notebooks.py`.

## Then (Weeks 5–8)
- `enhance/deep.py`: wrappers for pretrained Water-Net, FUnIE-GAN, Ucolor, U-shape Transformer (inference only).
- `detect/per_image_utility.py`: YOLO11-s on raw RUOD → per-image AP on raw vs. each enhanced variant → Δ labels.
- `model/features.py`: cache frozen CLIP + DINOv2 embeddings to disk; `model/head.py`: MLP heads.

## Proposed improvements over the handoff plan (for discussion)

| # | Improvement | Why | Cost |
|---|---|---|---|
| 1 | **Intra-scene SRCC** next to global SRCC (implemented) | UID2021/SAUD contain K enhanced versions of each raw image. A metric is used to *rank enhancements of the same image*; global SRCC can be inflated by content differences between scenes. Likely a key finding. | none |
| 2 | **Paired significance tests** between metrics (implemented) | "TOPIQ beats UIQM" needs a p-value, not overlapping CIs | none |
| 3 | **Add URanker** (underwater-specific, in pyiqa) + ARNIQA, QualiCLIP | Without an underwater-trained baseline, reviewers will ask why it's missing | minutes |
| 4 | **Null-enhancement noise floor for Δ** | Run the detector on raw vs. a near-identical copy (JPEG q95 / 1-px shift). The spread of that Δ is label noise. Use it to define a 3-class label (help / neutral / hurt) instead of sign(Δ), which otherwise flips on noise. Directly addresses the biggest risk (§8). | ~1 extra detection pass |
| 5 | **Smoother per-image utility**: AP@[.5:.95] *and* a confidence-weighted matched-recall score; report both | Per-image AP is very jumpy on images with 1–2 objects | none |
| 6 | **Predict the best of K options, not just yes/no** | Condition on the enhancer → choose argmax over {raw, method₁..ₖ}. Stronger headline: "NR-selected enhancer vs. oracle selection vs. best single enhancer" | small |
| 7 | **Leakage-safe splits for RUOD** via DINOv2 near-duplicate clustering | RUOD has no scene IDs and contains near-duplicate frames; random splits leak | minutes (features are cached anyway) |
| 8 | **Replace O6 (MOS study) with a small 2AFC study on the O2 sweep images** | O2 claims "metric rises while human judgement falls" — that needs *some* human data. ~10 raters × 60 pairs is far cheaper than BT.500 and directly supports O2 | ~1 day |
| 9 | Report **both UCIQE variants** | Shows published UCIQE numbers are not comparable across papers | none |
| 10 | Detector-retrained protocol (b): use **enhancement-augmented** training rather than per-enhancer retraining | One extra training run instead of K | 1 run |

## Caveats found so far
- UCIQE (`paper` variant) *drops* after colour correction on a synthetic test image, because a strong cast gives high, uniform chroma. In other words, UCIQE can reward colour casts. Check this on real data.
- UIQM rises with red over-compensation (synthetic test: 2.04 → 2.34, above the clean image at 2.32). This is the O2 hypothesis in miniature.
- Classical fusion port is untuned (gamma = 2 output is somewhat dark). Acceptable as a baseline; deep enhancers matter more.
- `pip install pyiqa` upgraded protobuf to 7.x, which conflicts with streamlit/proto-plus in the global env. Use a venv locally if you need those.

## Citation checks still pending (from handoff)
Li & Cavallaro = ICIP 2022 (pages); Dumic et al. 2026 metadata; U-shape Transformer vol/pages; SAUD/RUIE/RUOD details.
