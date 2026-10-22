"""Demo application server: FastAPI JSON API + static black-and-white web UI.

    python app/server.py            # -> http://127.0.0.1:8000

Assets (Kaggle notebook 07, unzipped into app/assets/): best.pt, third_party/FUnIE-GAN/...,
samples/{images,labels,samples.csv}. Without them the app still runs (upload only, no
FUnIE-GAN, no detection).
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import sys
import threading
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
ASSETS = Path(os.environ.get("UWIQA_DEMO_ASSETS", APP_DIR / "assets"))
os.environ.setdefault("THIRD_PARTY", str(ASSETS / "third_party"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(APP_DIR))

import vision as V  # noqa: E402
from uwiqa.detect.metrics import Dets, image_scores, yolo_labels_to_gt  # noqa: E402
from uwiqa.enhance.classical import CLASSICAL  # noqa: E402
from uwiqa.enhance.registry import resize_long_side  # noqa: E402
from uwiqa.metrics import uciqe, uiqm  # noqa: E402

WORK, IQA, LAB = 1280, 512, 640  # working / NR-IQA / Lab-operation resolutions (as in the study)
TAU = 0.05
NAMES = {"raw": "Raw", "clahe": "CLAHE", "gray_world": "Gray-world", "udcp": "UDCP", "fusion": "Fusion",
         "funiegan": "FUnIE-GAN"}
LOCK = threading.Lock()

app = FastAPI(title="Underwater detection-aware IQA demo")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


# ------------------------------------------------------------------ resources
@lru_cache(maxsize=1)
def funiegan():
    w = Path(os.environ["THIRD_PARTY"]) / "FUnIE-GAN" / "PyTorch" / "models" / "funie_generator.pth"
    if not w.exists():
        return None
    from uwiqa.enhance.deep import funiegan as load
    return load("cpu")


@lru_cache(maxsize=1)
def detector():
    w = ASSETS / "best.pt"
    if not w.exists():
        return None
    from ultralytics import YOLO
    return YOLO(str(w))


@lru_cache(maxsize=1)
def samples() -> pd.DataFrame:
    p = ASSETS / "samples" / "samples.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


UPLOADS: "OrderedDict[str, bytes]" = OrderedDict()


def image_bytes(img_id: str) -> bytes:
    s = samples()
    if len(s) and img_id in set(s["sample"]):
        return (ASSETS / "samples" / "images" / s.set_index("sample").at[img_id, "file"]).read_bytes()
    if img_id in UPLOADS:
        return UPLOADS[img_id]
    raise HTTPException(404, f"unknown image {img_id}")


def ground_truth(img_id: str) -> Dets | None:
    p = ASSETS / "samples" / "labels" / f"{img_id}.txt"
    return yolo_labels_to_gt(p.read_text()) if p.exists() else None


def sample_row(img_id: str):
    s = samples()
    return s.set_index("sample").loc[img_id] if len(s) and img_id in set(s["sample"]) else None


def decode(data: bytes) -> np.ndarray:
    """Same decode + resize as the study's labelling pipeline."""
    im = Image.open(io.BytesIO(data))
    w, h = im.size
    s = WORK / max(w, h)
    if s < 1:
        im.draft("RGB", (int(w * s) + 1, int(h * s) + 1))
    return resize_long_side(np.asarray(im.convert("RGB")), WORK)


@lru_cache(maxsize=6)
def variants(img_id: str) -> dict:
    x = decode(image_bytes(img_id))
    out = {"raw": x}
    for name, f in CLASSICAL.items():
        out[name] = f(x)
    g = funiegan()
    if g is not None:
        with LOCK:
            out["funiegan"] = g(x)
    return out


def jpeg(img: np.ndarray, quality: int = 88) -> bytes:
    if img.ndim == 2:
        img = np.stack([img] * 3, -1)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def b64(img: np.ndarray, width: int | None = None) -> str:
    if width and img.shape[1] > width:
        img = V.resize(img, width)
    return "data:image/jpeg;base64," + base64.b64encode(jpeg(img)).decode()


def study_dap(img_id: str) -> dict:
    r = sample_row(img_id)
    if r is None:
        return {}
    return {m: float(r[f"ap_{m}"] - r["ap_raw"]) for m in NAMES if m != "raw" and f"ap_{m}" in r}


# ------------------------------------------------------------------ pages + status
@app.get("/")
def index():
    return FileResponse(APP_DIR / "static" / "index.html")


@app.get("/api/status")
def status():
    s = samples()
    bm = ROOT / "results" / "tables" / "o1_uid2021.csv"
    bench = pd.read_csv(bm)[["metric", "srcc", "srcc_lo", "srcc_hi", "intra_scene_srcc"]] if bm.exists() else None
    return {
        "detector": (ASSETS / "best.pt").exists(),
        "funiegan": funiegan() is not None,
        "samples": [] if s.empty else [
            {"id": r.sample, "kind": r.kind, "n_objects": int(r.n_objects), "best": NAMES.get(r.best, r.best)}
            for r in s.itertuples()],
        "benchmark": [] if bench is None else bench.round(3).to_dict("records"),
        "names": NAMES,
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(400, "not an image")
    img_id = "up_" + hashlib.md5(data).hexdigest()[:12]
    UPLOADS[img_id] = data
    while len(UPLOADS) > 10:
        UPLOADS.popitem(last=False)
    return {"id": img_id}


@app.get("/api/thumb/{img_id}.jpg")
def thumb(img_id: str):
    im = Image.open(io.BytesIO(image_bytes(img_id)))
    im.draft("RGB", (480, 480))
    im = im.convert("RGB")
    im.thumbnail((480, 480))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return Response(buf.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/img/{img_id}/{variant}.jpg")
def variant_image(img_id: str, variant: str, w: int = Query(1100, ge=64, le=1280)):
    v = variants(img_id)
    if variant not in v:
        raise HTTPException(404, "unknown variant")
    img = v[variant]
    return Response(jpeg(V.resize(img, w) if img.shape[1] > w else img), media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=3600"})


# ------------------------------------------------------------------ analysis endpoints
@app.get("/api/enhance/{img_id}")
def enhance(img_id: str):
    v = variants(img_id)
    hist = {}
    for k, img in v.items():
        h = V.channel_histograms(resize_long_side(img, LAB))
        h = h.reshape(3, 64, 4).sum(-1)
        hist[k] = (h / h.sum(axis=1, keepdims=True)).round(5).tolist()
    h0, w0 = v["raw"].shape[:2]
    return {"variants": [{"key": k, "name": NAMES[k]} for k in v], "hist": hist, "size": [w0, h0]}


@lru_cache(maxsize=12)
def _quality(img_id: str):
    rows, dap = [], study_dap(img_id)
    for k, img in variants(img_id).items():
        small = resize_long_side(img, IQA)
        q = uiqm(small, return_components=True)
        rows.append({"key": k, "name": NAMES[k], "uiqm": q["uiqm"], "uicm": q["uicm"], "uism": q["uism"],
                     "uiconm": q["uiconm"], "uciqe": uciqe(small), "study_dap": dap.get(k)})
    return rows


@app.get("/api/quality/{img_id}")
def quality(img_id: str):
    return {"rows": _quality(img_id), "has_study": bool(study_dap(img_id)), "tau": TAU}


@lru_cache(maxsize=12)
def _detect(img_id: str):
    det = detector()
    if det is None:
        return None
    gt = ground_truth(img_id)
    out, base = {}, None
    for k, img in variants(img_id).items():
        with LOCK:
            r = det.predict(np.ascontiguousarray(img[:, :, ::-1]), imgsz=640, conf=0.001, max_det=300,
                            device="cpu", verbose=False)[0].boxes
        d = Dets(r.xyxyn.numpy(), r.cls.numpy().astype(int), r.conf.numpy())
        keep = d.conf >= 0.05
        rec = {"key": k, "name": NAMES[k],
               "boxes": np.c_[d.boxes[keep], d.conf[keep], d.cls[keep]].round(4).tolist()}
        if gt is not None:
            s = image_scores(d, gt)
            rec.update({"ap": s["ap"], "ap50": s["ap50"], "f1": s["f1"]})
            if k == "raw":
                base = s["ap"]
        out[k] = rec
    if gt is not None:
        for k, rec in out.items():
            rec["dap"] = None if k == "raw" else rec["ap"] - base
    return out


@app.get("/api/detect/{img_id}")
def detect(img_id: str):
    res = _detect(img_id)
    if res is None:
        raise HTTPException(503, "detector weights not found (app/assets/best.pt)")
    gt = ground_truth(img_id)
    return {"variants": list(res.values()), "classes": V.CLASS_NAMES, "tau": TAU,
            "gt": None if gt is None else np.c_[gt.boxes, gt.cls].round(4).tolist(),
            "study_dap": study_dap(img_id)}


@lru_cache(maxsize=12)
def _features(img_id: str):
    return [{"key": k, "name": NAMES[k], **V.feature_summary(resize_long_side(img, LAB))}
            for k, img in variants(img_id).items()]


@app.get("/api/features/{img_id}")
def features(img_id: str):
    return {"rows": _features(img_id)}


@app.get("/api/lab/{img_id}/{lab}")
def lab(img_id: str, lab: int, variant: str = "raw", gamma: float = 0.6, angle: float = 15,
        lo: int = 50, hi: int = 150, k: int = 4):
    v = variants(img_id)
    if variant not in v:
        raise HTTPException(404, "unknown variant")
    img = resize_long_side(v[variant], LAB)
    g = V.to_gray(img)
    items, extra = [], {}
    W = 560

    def add(title, fn, im, stat=None):
        items.append({"title": title, "fn": fn, "img": b64(im, W), "stat": stat})

    if lab == 1:
        info = V.image_info(v[variant])
        extra = {"info": {kk: round(vv, 1) if isinstance(vv, float) else vv for kk, vv in info.items()}}
        add("Original (640 px copy)", "cv2.resize(img, (w, h), INTER_AREA)", img, f"{img.shape[1]} × {img.shape[0]}")
        add("Grayscale", "cv2.cvtColor(img, COLOR_RGB2GRAY)", g)
        add(f"Rotated {angle:+.0f}°", "cv2.getRotationMatrix2D + cv2.warpAffine", V.rotate(img, angle))
        add("Half size", "cv2.resize(img, (w/2, h/2))", V.resize(img, img.shape[1] // 2),
            f"{img.shape[1] // 2} px wide")
    elif lab == 2:
        eq = V.hist_equalize(img)
        add("Negative", "255 − r", V.negative(img))
        add("Log transform", "c · log(1 + r)", V.log_transform(img))
        add(f"Gamma γ = {gamma:.1f}", "255 · (r/255)^γ", V.gamma(img, gamma))
        add("Contrast stretching", "piecewise linear, 1–99th pct", V.contrast_stretch(img))
        add("Histogram equalisation", "cv2.equalizeHist (Y channel)", eq,
            f"contrast {V.michelson_contrast(g):.2f} → {V.michelson_contrast(V.to_gray(eq)):.2f}")
        add("CLAHE", "cv2.createCLAHE(2.0, (8, 8))", CLASSICAL["clahe"](img))
        h0, h1 = V.gray_histogram(g), V.gray_histogram(V.to_gray(eq))
        extra = {"hist": {"original": (h0.reshape(64, 4).sum(1) / h0.sum()).round(5).tolist(),
                          "equalised": (h1.reshape(64, 4).sum(1) / h1.sum()).round(5).tolist()}}
    elif lab == 3:
        edges = V.canny(g, lo, hi)
        add("Box filter 9×9", "cv2.blur", V.box_blur(img, 9))
        add("Gaussian 9×9", "cv2.GaussianBlur", V.gaussian_blur(img, 9))
        add("Median 9×9", "cv2.medianBlur", V.median_blur(img, 9))
        add("Sobel magnitude", "√(Gx² + Gy²), cv2.Sobel", V.sobel_magnitude(g))
        add("Laplacian", "cv2.Laplacian", V.laplacian(g))
        add(f"Canny {lo}/{hi}", "cv2.Canny", edges, f"edge density {V.edge_density(edges):.3f}")
        add("Unsharp masking", "img + α(img − blur)", V.unsharp_mask(img))
    elif lab == 4:
        mask, t = V.otsu(g)
        seg, centers = V.kmeans_segment(img, k)
        add("Otsu threshold", "cv2.threshold(THRESH_OTSU)", mask, f"T = {t:.0f}")
        add("Adaptive threshold", "cv2.adaptiveThreshold (Gaussian)", V.adaptive_threshold(g))
        add(f"k-means, K = {k}", "cv2.kmeans on RGB pixels", seg, f"{k} clusters")
        extra = {"centers": centers.tolist()}
    elif lab == 5:
        sift, fast = V.sift_keypoints(g), V.fast_keypoints(g)
        harris = img.copy()
        harris[V.harris_corners(g)] = (255, 255, 255)
        _, hog_vis = V.hog_image(g)
        lbp_img, lbp_hist = V.lbp(g)
        add("SIFT keypoints", "cv2.SIFT_create().detect", V.draw_keypoints(img, sift, (255, 255, 255)),
            f"{len(sift)} keypoints")
        add("FAST corners", "cv2.FastFeatureDetector_create", V.draw_keypoints(img, fast, (255, 255, 255)),
            f"{len(fast)} corners")
        add("Harris corners", "cv2.cornerHarris", harris)
        add("HOG", "skimage.feature.hog (9 bins, 16 px cells)", hog_vis)
        add("LBP (uniform, P = 8, R = 1)", "skimage.feature.local_binary_pattern", lbp_img)
        extra = {"lbp_hist": lbp_hist.round(4).tolist()}
    else:
        raise HTTPException(404, "lab must be 1-5")
    return {"lab": lab, "variant": variant, "items": items, **extra}


def main():
    import uvicorn
    host, port = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8000"))
    print(f"\n  Underwater IQA demo  ->  http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
