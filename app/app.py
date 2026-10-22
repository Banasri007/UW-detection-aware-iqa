"""Underwater enhancement vs detection: interactive demo (FCV Lab mini project, CSE 3176).

    streamlit run app/app.py

Assets (from Kaggle notebook 07, unzipped into app/assets/):
  best.pt, third_party/FUnIE-GAN/..., samples/{images,labels,samples.csv}
The app still runs without them: it then offers upload only and skips FUnIE-GAN / detection.
URL parameters ?page=...&sample=...&variant=... select a view directly (used for report screenshots).
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
ASSETS = Path(os.environ.get("UWIQA_DEMO_ASSETS", APP_DIR / "assets"))
os.environ.setdefault("THIRD_PARTY", str(ASSETS / "third_party"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(APP_DIR))

import cv2  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

import vision as V  # noqa: E402
from uwiqa.detect.metrics import Dets, image_scores, yolo_labels_to_gt  # noqa: E402
from uwiqa.enhance.classical import CLASSICAL  # noqa: E402
from uwiqa.enhance.registry import resize_long_side  # noqa: E402
from uwiqa.metrics import uciqe, uiqm  # noqa: E402

WORK_SIZE = 1280   # same working resolution as the paper's utility labels
IQA_SIZE = 512     # same resolution used for NR-IQA scores in the paper
LAB_SIZE = 640     # Lab 1-5 operations run on a 640-px copy for speed
NICE = {"raw": "Raw", "clahe": "CLAHE", "gray_world": "Gray-world", "udcp": "UDCP",
        "fusion": "Fusion", "funiegan": "FUnIE-GAN"}
PAGES = {"overview": "Overview", "enhance": "1 · Enhancement", "quality": "2 · Quality scores",
         "lab": "3 · Lab 1–5 operations", "detect": "4 · Detection"}
C_UP, C_DOWN, INK, MUTED = "#1baf7a", "#e34948", "#0b0b0b", "#52514e"

st.set_page_config(page_title="Underwater Detection-Aware IQA", page_icon="🌊", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 2.2rem; max-width: 1400px;}
h1, h2, h3 {letter-spacing: -0.01em;}
.small-note {color: #52514e; font-size: 0.88rem;}
.badge {display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.85rem;
        background:#eef3fb; color:#1d4f91; margin-right:6px;}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ resources
@st.cache_resource(show_spinner="Loading FUnIE-GAN ...")
def load_funiegan():
    w = Path(os.environ["THIRD_PARTY"]) / "FUnIE-GAN" / "PyTorch" / "models" / "funie_generator.pth"
    if not w.exists():
        return None
    from uwiqa.enhance.deep import funiegan
    return funiegan("cpu")


@st.cache_resource(show_spinner="Loading the YOLO11-s detector ...")
def load_detector():
    w = ASSETS / "best.pt"
    if not w.exists():
        return None
    from ultralytics import YOLO
    return YOLO(str(w))


@st.cache_data
def load_samples() -> pd.DataFrame:
    p = ASSETS / "samples" / "samples.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


@st.cache_data
def load_benchmark() -> pd.DataFrame:
    p = ROOT / "results" / "tables" / "o1_uid2021.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


# ------------------------------------------------------------------ cached computations
def decode(data: bytes) -> np.ndarray:
    """Same decode + resize as scripts/build_utility_labels.py."""
    im = Image.open(io.BytesIO(data))
    w, h = im.size
    s = WORK_SIZE / max(w, h)
    if s < 1:
        im.draft("RGB", (int(w * s) + 1, int(h * s) + 1))
    return resize_long_side(np.asarray(im.convert("RGB")), WORK_SIZE)


@st.cache_data(show_spinner="Enhancing ...", max_entries=8)
def enhance_all(key: str, _data: bytes) -> dict:
    x = decode(_data)
    out = {"raw": x}
    for name, f in CLASSICAL.items():
        out[name] = f(x)
    g = load_funiegan()
    if g is not None:
        out["funiegan"] = g(x)
    return out


@st.cache_data(show_spinner="Scoring with UIQM / UCIQE ...", max_entries=8)
def quality_table(key: str, _variants: dict) -> pd.DataFrame:
    rows = []
    for m, img in _variants.items():
        small = resize_long_side(img, IQA_SIZE)
        q = uiqm(small, return_components=True)
        rows.append({"variant": m, "UIQM": q["uiqm"], "UICM (colour)": q["uicm"], "UISM (sharpness)": q["uism"],
                     "UIConM (contrast)": q["uiconm"], "UCIQE": uciqe(small)})
    return pd.DataFrame(rows).set_index("variant")


@st.cache_data(show_spinner="Running the detector on every version ...", max_entries=8)
def detect_all(key: str, _variants: dict) -> dict:
    det = load_detector()
    out = {}
    for m, img in _variants.items():
        r = det.predict(np.ascontiguousarray(img[:, :, ::-1]), imgsz=640, conf=0.001, max_det=300,
                        device="cpu", verbose=False)[0].boxes
        out[m] = Dets(r.xyxyn.numpy(), r.cls.numpy().astype(int), r.conf.numpy())
    return out


@st.cache_data(show_spinner="Computing low-level features ...", max_entries=8)
def features_table(key: str, _variants: dict) -> pd.DataFrame:
    return pd.DataFrame({m: V.feature_summary(resize_long_side(img, LAB_SIZE)) for m, img in _variants.items()}).T


# ------------------------------------------------------------------ helpers
def qp(name, default=None):
    v = st.query_params.get(name)
    return v if v is not None else default


def show_row(images: dict, captions: dict | None = None, cols: int = 3):
    items = list(images.items())
    for i in range(0, len(items), cols):
        cs = st.columns(cols)
        for c, (k, im) in zip(cs, items[i:i + cols]):
            c.image(im, caption=(captions or {}).get(k, NICE.get(k, k)), width="stretch")


def hist_figure(variants: dict, keys: list):
    fig, axs = plt.subplots(1, len(keys), figsize=(3.1 * len(keys), 2.0), sharey=True)
    axs = np.atleast_1d(axs)
    for ax, k in zip(axs, keys):
        h = V.channel_histograms(resize_long_side(variants[k], LAB_SIZE))
        for c, col in enumerate(["#e34948", "#1baf7a", "#2a78d6"]):
            ax.plot(h[c] / h[c].sum(), color=col, lw=1.2)
        ax.set_title(NICE.get(k, k), fontsize=9)
        ax.set_xlim(0, 255)
        ax.tick_params(labelsize=7)
        ax.spines[["top", "right"]].set_visible(False)
    axs[0].set_ylabel("fraction of pixels", fontsize=8)
    fig.tight_layout()
    return fig


def delta_style(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    return f"color: {C_UP if v > 0.05 else C_DOWN if v < -0.05 else MUTED}; font-weight: 600"


def as_text(df: pd.DataFrame, fmt: dict) -> pd.DataFrame:
    """Format numbers as strings (Streamlit renders NaN as 'None' otherwise)."""
    out = df.copy().astype(object)
    for col, f in fmt.items():
        if col in out:
            out[col] = [("–" if pd.isna(v) else (f"{v:+.3f}" if f == "+" else format(v, f))) for v in df[col]]
    return out


# ------------------------------------------------------------------ sidebar: image + page
samples = load_samples()
st.sidebar.title("🌊 Underwater IQA demo")
st.sidebar.caption("FCV Lab mini project · CSE 3176")

sources = (["Sample image (with ground truth)"] if len(samples) else []) + ["Upload your own"]
src = st.sidebar.radio("Image source", sources, index=0)
gt, sample_row, data = None, None, None
if src.startswith("Sample"):
    labels = [f"{r.sample} · {r.kind} · {r.n_objects} objects" for r in samples.itertuples()]
    idx = int(samples.index[samples["sample"] == qp("sample")][0]) if qp("sample") in set(samples["sample"]) else 0
    choice = st.sidebar.selectbox("Sample", labels, index=idx)
    sample_row = samples.iloc[labels.index(choice)]
    data = (ASSETS / "samples" / "images" / sample_row["file"]).read_bytes()
    gt = yolo_labels_to_gt((ASSETS / "samples" / "labels" / f"{sample_row['sample']}.txt").read_text())
else:
    up = st.sidebar.file_uploader("Underwater image", type=["jpg", "jpeg", "png", "bmp"])
    if up is not None:
        data = up.getvalue()

page_keys = list(PAGES)
page = st.sidebar.radio("Page", page_keys, format_func=PAGES.get,
                        index=page_keys.index(qp("page", "overview")) if qp("page") in PAGES else 0)
st.sidebar.markdown("---")
st.sidebar.markdown(
    f"<span class='small-note'>Detector: {'✅ YOLO11-s' if (ASSETS / 'best.pt').exists() else '⚠️ not found'}<br>"
    f"FUnIE-GAN: {'✅' if load_funiegan() is not None else '⚠️ not found'}<br>"
    f"Working size: {WORK_SIZE}px long side (as in the paper)</span>", unsafe_allow_html=True)

# ------------------------------------------------------------------ overview
if page == "overview":
    st.title("Seeing Better Is Not Detecting Better")
    st.markdown("##### Benchmarking no-reference quality metrics and detection-aware enhancement for underwater images")
    st.markdown("<span class='badge'>FCV Lab · CSE 3176</span><span class='badge'>MIT Manipal</span>"
                "<span class='badge'>Javvaji Aditya Banasri · Mansi Sinha · Akshant Beuria</span>",
                unsafe_allow_html=True)
    st.write("")
    c = st.columns(4)
    c[0].metric("Best NR metric vs humans (URanker)", "SRCC 0.62", help="UID2021, 960 images, 77 observers")
    c[1].metric("UIQM / UCIQE vs humans", "0.33 / 0.33")
    c[2].metric("Mean ΔAP of the best enhancer (CLAHE)", "−0.022", help="RUOD held-out, 7,000 images")
    c[3].metric("Per-image oracle headroom", "+0.025 mAP", help="≈10× the label-noise control")
    st.markdown("""
**What this app shows.** Underwater images are usually *enhanced* before analysis, and the enhancement is judged
by no-reference quality metrics such as **UIQM** and **UCIQE**. Our study found that a better-*looking* image is often
a *worse* image for an object detector. This app lets you see that on one image at a time:

1. **Enhancement**: five enhancers (CLAHE, gray-world, UDCP, fusion, FUnIE-GAN) applied exactly as in the study.
2. **Quality scores**: UIQM and UCIQE of every version, with the study's evidence of how far each metric can be trusted.
3. **Lab 1–5 operations**: histograms, equalisation, filtering, edges, thresholding, k-means, SIFT/FAST/HOG/LBP on
   the raw and enhanced images.
4. **Detection**: our trained YOLO11-s detector on every version. For sample images (with ground truth) it computes the
   true per-image AP and how much each enhancer helps or hurts.

Pick a **sample image** in the sidebar (they were chosen to include cases where enhancement helps, hurts, or makes no
difference) or **upload** your own.
""")
    if data is not None:
        st.image(decode(data), caption="Selected image (raw)", width=520)
    st.stop()

if data is None:
    st.info("Upload an underwater image in the sidebar to begin.")
    st.stop()

key = hashlib.md5(data).hexdigest()
variants = enhance_all(key, data)

# ------------------------------------------------------------------ 1. enhancement
if page == "enhance":
    st.header("1 · Enhancement")
    st.markdown("The raw image and five enhanced versions, produced in memory at the study's working resolution. "
                "CLAHE, gray-world, UDCP and fusion are our implementations; FUnIE-GAN uses the official weights.")
    show_row(variants)
    st.subheader("Colour histograms (Lab 2: `cv2.calcHist`)")
    st.pyplot(hist_figure(variants, list(variants)), width="stretch")
    st.markdown("<span class='small-note'>Raw underwater images have a weak red channel and a strong blue-green "
                "one; enhancers redistribute the channels in very different ways.</span>", unsafe_allow_html=True)

# ------------------------------------------------------------------ 2. quality
elif page == "quality":
    st.header("2 · No-reference quality scores")
    q = quality_table(key, variants)
    q.index = [NICE.get(i, i) for i in q.index]
    if sample_row is not None:
        q["ΔAP (detection, from study labels)"] = [
            np.nan if i == "Raw" else sample_row.get(f"ap_{k}", np.nan) - sample_row["ap_raw"]
            for i, k in zip(q.index, variants)]
    st.markdown("UIQM and UCIQE are computed live with our implementations (same code as the study), at 512 px. "
                "**Higher means 'better quality' to the metric.**")
    dcol = "ΔAP (detection, from study labels)"
    qt = as_text(q, {c: ("+" if c == dcol else ".3f") for c in q.columns})
    sty = qt.style
    if dcol in q:
        sty = sty.map(delta_style, subset=[dcol])
    st.dataframe(sty, width="stretch")
    c1, c2 = st.columns(2)
    for c, col in ((c1, "UIQM"), (c2, "UCIQE")):
        fig, ax = plt.subplots(figsize=(5, 2.4))
        ax.bar(q.index, q[col], color=["#52514e"] + ["#2a78d6"] * (len(q) - 1))
        ax.set_title(col, fontsize=10)
        ax.tick_params(labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        c.pyplot(fig, width="stretch")
    if sample_row is not None:
        st.info("Compare the quality scores with the **ΔAP** column: an enhancer can raise UIQM/UCIQE while lowering "
                "detection accuracy on the same image. In the study, the quality gain of an enhancement had no positive "
                "correlation with its detection gain for any metric.")
    bm = load_benchmark()
    if len(bm):
        st.subheader("How far can each metric be trusted? (study result, UID2021)")
        b = bm[["metric", "srcc", "srcc_lo", "srcc_hi", "intra_scene_srcc"]].rename(columns={
            "srcc": "SRCC vs human MOS", "srcc_lo": "95% CI low", "srcc_hi": "95% CI high",
            "intra_scene_srcc": "intra-scene SRCC"})
        st.dataframe(as_text(b, {c: ".3f" for c in b.columns if c != "metric"}), width="stretch", hide_index=True)

# ------------------------------------------------------------------ 3. lab operations
elif page == "lab":
    st.header("3 · Lab 1–5 operations on the raw and enhanced images")
    opts = list(variants)
    v = st.selectbox("Image version", opts, format_func=lambda k: NICE.get(k, k),
                     index=opts.index(qp("variant", "raw")) if qp("variant", "raw") in opts else 0)
    img = resize_long_side(variants[v], LAB_SIZE)
    g = V.to_gray(img)
    st.caption(f"Operations run on a {img.shape[1]}×{img.shape[0]} copy for speed.")

    st.subheader("Lab 1 · OpenCV basics")
    c1, c2, c3 = st.columns([1.2, 1, 1])
    info = V.image_info(variants[v])
    c1.dataframe(as_text(pd.DataFrame(info, index=["value"]).T, {"value": ".1f"}), width="stretch")
    x = c2.slider("Pixel x", 0, img.shape[1] - 1, img.shape[1] // 2)
    y = c2.slider("Pixel y", 0, img.shape[0] - 1, img.shape[0] // 2)
    r, gg, b = V.pixel_rgb(img, x, y)
    c2.markdown(f"RGB at ({x}, {y}): **({r}, {gg}, {b})** "
                f"<span style='display:inline-block;width:18px;height:18px;background:rgb({r},{gg},{b});"
                f"border:1px solid #999;vertical-align:middle'></span>", unsafe_allow_html=True)
    ang = c3.slider("Rotate (°)", -45, 45, 15)
    c3.image(V.rotate(V.resize(img, 320), ang), caption="cv2.resize + cv2.warpAffine", width="stretch")

    st.subheader("Lab 2 · Image enhancement")
    gm = st.slider("Gamma (power-law)", 0.2, 3.0, 0.6, 0.1)
    show_row({"neg": V.negative(img), "log": V.log_transform(img), "gam": V.gamma(img, gm),
              "str": V.contrast_stretch(img), "heq": V.hist_equalize(img), "clahe": CLASSICAL["clahe"](img)},
             {"neg": "Negative 255−r", "log": "Log c·log(1+r)", "gam": f"Gamma r^{gm}",
              "str": "Contrast stretching (piecewise)", "heq": "Histogram equalisation", "clahe": "CLAHE"}, cols=3)
    fig, ax = plt.subplots(figsize=(8, 2.2))
    for im, lab_, col in ((g, "original", "#52514e"), (V.to_gray(V.hist_equalize(img)), "equalised", "#2a78d6")):
        h = V.gray_histogram(im)
        ax.plot(h / h.sum(), label=lab_, color=col, lw=1.3)
    ax.legend(fontsize=8, frameon=False)
    ax.set_xlim(0, 255)
    ax.set_title(f"Grey-level histogram · Michelson contrast {V.michelson_contrast(g):.2f} → "
                 f"{V.michelson_contrast(V.to_gray(V.hist_equalize(img))):.2f}", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    st.pyplot(fig, width="stretch")

    st.subheader("Lab 3 · Filtering and edges")
    lo, hi = st.slider("Canny thresholds", 0, 300, (50, 150))
    edges = V.canny(g, lo, hi)
    show_row({"box": V.box_blur(img, 9), "gau": V.gaussian_blur(img, 9), "med": V.median_blur(img, 9),
              "sob": V.sobel_magnitude(g), "lap": V.laplacian(g), "can": edges, "uns": V.unsharp_mask(img)},
             {"box": "Box filter 9×9", "gau": "Gaussian 9×9", "med": "Median 9×9", "sob": "Sobel gradient magnitude",
              "lap": "Laplacian", "can": f"Canny · edge density {V.edge_density(edges):.3f}",
              "uns": "Unsharp masking"}, cols=4)

    st.subheader("Lab 4 · Segmentation")
    k = st.slider("k-means clusters (K)", 2, 8, 4)
    mask, t = V.otsu(g)
    seg, centers = V.kmeans_segment(img, k)
    show_row({"ots": mask, "ada": V.adaptive_threshold(g), "km": seg},
             {"ots": f"Otsu threshold T = {t:.0f}", "ada": "Adaptive (Gaussian) threshold",
              "km": f"k-means colour segmentation, K = {k}"}, cols=3)

    st.subheader("Lab 5 · Feature extraction")
    sift = V.sift_keypoints(g)
    fast = V.fast_keypoints(g)
    harris = img.copy()
    harris[V.harris_corners(g)] = (255, 0, 0)
    _, hog_vis = V.hog_image(g)
    lbp_img, lbp_hist = V.lbp(g)
    show_row({"sift": V.draw_keypoints(img, sift), "fast": V.draw_keypoints(img, fast, (255, 210, 0)),
              "har": harris, "hog": hog_vis, "lbp": lbp_img},
             {"sift": f"SIFT keypoints: {len(sift)}", "fast": f"FAST corners: {len(fast)}",
              "har": "Harris corners (red)", "hog": "HOG visualisation", "lbp": "LBP (uniform, P=8, R=1)"}, cols=3)

    st.subheader("Raw vs enhanced: low-level features")
    ft = features_table(key, variants)
    ft.index = [NICE.get(i, i) for i in ft.index]
    st.dataframe(as_text(ft, {"Michelson contrast": ".3f", "Canny edge density": ".3f", "LBP entropy": ".3f",
                              "SIFT keypoints": ".0f", "FAST corners": ".0f", "Otsu threshold": ".0f",
                              "Otsu foreground %": ".1f"}), width="stretch")
    st.markdown("<span class='small-note'>Enhancement usually increases contrast, edges and keypoints, but the "
                "Detection page shows that this does not translate into better detection.</span>",
                unsafe_allow_html=True)

# ------------------------------------------------------------------ 4. detection
elif page == "detect":
    st.header("4 · Detection with the frozen YOLO11-s detector")
    if load_detector() is None:
        st.warning("Detector weights not found: put `best.pt` from Kaggle notebook 07 into `app/assets/`.")
        st.stop()
    dets = detect_all(key, variants)
    thr = st.slider("Confidence threshold for drawing / counting", 0.05, 0.9, 0.25, 0.05)
    show_gt = gt is not None and st.checkbox("Overlay ground-truth boxes (white)", value=False)
    shown, rows = {}, []
    base = image_scores(dets["raw"], gt) if gt is not None else None
    for m, d in dets.items():
        keep = d.conf >= thr
        im = V.draw_boxes(variants[m], d.boxes[keep], d.cls[keep], d.conf[keep])
        if show_gt:
            for bx in gt.boxes:
                h_, w_ = im.shape[:2]
                x1, y1, x2, y2 = (bx * [w_, h_, w_, h_]).astype(int)
                cv2.rectangle(im, (x1, y1), (x2, y2), (255, 255, 255), 2)
        shown[m] = im
        row = {"version": NICE.get(m, m), f"detections (conf ≥ {thr:.2f})": int(keep.sum()),
               "mean confidence": float(d.conf[keep].mean()) if keep.any() else np.nan}
        if gt is not None:
            s = image_scores(d, gt)
            row.update({"AP50:95": s["ap"], "AP50": s["ap50"], "F1@0.25": s["f1"],
                        "ΔAP vs raw": np.nan if m == "raw" else s["ap"] - base["ap"]})
            if sample_row is not None and m != "raw" and f"ap_{m}" in sample_row:
                row["ΔAP in study labels"] = sample_row[f"ap_{m}"] - sample_row["ap_raw"]
        rows.append(row)
    show_row(shown)
    tab = pd.DataFrame(rows).set_index("version")
    fmt = {c: ("+" if c.startswith("ΔAP") else ".3f") for c in tab.columns if not c.startswith("detections")}
    sty = as_text(tab, fmt).style
    for c in ("ΔAP vs raw", "ΔAP in study labels"):
        if c in tab:
            sty = sty.map(delta_style, subset=[c])
    st.dataframe(sty, width="stretch")
    if gt is not None:
        best = tab["AP50:95"].idxmax()
        st.success(f"Ground truth: {len(gt)} objects. Best version for the detector on this image: **{best}** "
                   f"(AP {tab.loc[best, 'AP50:95']:.3f} vs raw {tab.loc['Raw', 'AP50:95']:.3f}). "
                   "Green ΔAP = helps by more than the noise threshold 0.05; red = hurts by more than 0.05.")
    else:
        st.info("Uploaded images have no ground-truth boxes, so AP and ΔAP cannot be computed; "
                "only detection counts and confidences are shown.")
    st.markdown("<span class='small-note'>Across the 7,000 held-out RUOD images of the study, every enhancer lowered "
                "mean AP (CLAHE −0.022 … fusion −0.083), yet each helped about 11% of images by more than the "
                "noise threshold. Choosing the enhancer by UIQM/UCIQE gain cost 0.05–0.09 mAP.</span>",
                unsafe_allow_html=True)
