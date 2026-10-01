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
- O5 cross-*dataset* generalisation becomes cross-*split* generalisation within RUOD (leakage-safe clusters). Add DUO only if time allows.

## Immediate next steps (you)
1. Import the notebook into Kaggle (GPU, Internet on), run cells 1–4.
2. From the `inspect_dataset` output, fill the three values in cell 5.
3. Run the rest: `check_env`, scoring, benchmark (prints the **Week-4 gate**: TOPIQ_NR SRCC ≳ 0.7), stress test.
4. Meanwhile, get RUOD onto Kaggle (search Kaggle Datasets for a mirror, or upload it) for Week 5.

## Then (Weeks 5–8, built after the gate)
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
