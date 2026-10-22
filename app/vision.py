"""Lab 1-5 image operations used by the demo app (FCV Lab, CSE 3176).

Every function takes / returns uint8 RGB (or a single-channel uint8 image) so the
results can be shown directly. The lab each operation comes from is noted.
"""
from __future__ import annotations

import cv2
import numpy as np
from skimage.feature import hog, local_binary_pattern

CLASS_NAMES = ["holothurian", "echinus", "scallop", "starfish", "fish",
               "corals", "diver", "cuttlefish", "turtle", "jellyfish"]
_PALETTE = [(42, 120, 214), (235, 104, 52), (27, 175, 122), (237, 161, 0), (232, 123, 164),
            (0, 131, 0), (74, 58, 167), (227, 73, 72), (82, 81, 78), (25, 158, 112)]


# ------------------------------------------------------------------ Lab 1: OpenCV basics
def to_gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)


def image_info(img: np.ndarray) -> dict:
    h, w = img.shape[:2]
    return {"height": h, "width": w, "channels": img.shape[2] if img.ndim == 3 else 1,
            "mean R": float(img[..., 0].mean()), "mean G": float(img[..., 1].mean()),
            "mean B": float(img[..., 2].mean())}


def pixel_rgb(img: np.ndarray, x: int, y: int) -> tuple:
    r, g, b = img[y, x]
    return int(r), int(g), int(b)


def resize(img: np.ndarray, width: int) -> np.ndarray:
    h, w = img.shape[:2]
    return cv2.resize(img, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)


def draw_boxes(img: np.ndarray, boxes_xyxyn: np.ndarray, cls: np.ndarray, conf=None,
               thickness: int | None = None) -> np.ndarray:
    """Draw normalised xyxy boxes with cv2.rectangle / cv2.putText."""
    out = img.copy()
    h, w = out.shape[:2]
    t = thickness or max(2, round(min(h, w) / 300))
    for i, (b, c) in enumerate(zip(boxes_xyxyn, cls)):
        x1, y1, x2, y2 = (b * [w, h, w, h]).astype(int)
        col = _PALETTE[int(c) % len(_PALETTE)]
        cv2.rectangle(out, (x1, y1), (x2, y2), col, t)
        label = CLASS_NAMES[int(c)] if int(c) < len(CLASS_NAMES) else str(int(c))
        if conf is not None:
            label += f" {conf[i]:.2f}"
        fs = max(0.4, min(h, w) / 1100)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
        cv2.rectangle(out, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1), col, -1)
        cv2.putText(out, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), 1, cv2.LINE_AA)
    return out


# ------------------------------------------------------------------ Lab 2: enhancement & histograms
def channel_histograms(img: np.ndarray) -> np.ndarray:
    """(3, 256) histograms of R, G, B via cv2.calcHist."""
    return np.stack([cv2.calcHist([img], [c], None, [256], [0, 256]).ravel() for c in range(3)])


def gray_histogram(gray: np.ndarray) -> np.ndarray:
    return cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()


def hist_equalize(img: np.ndarray) -> np.ndarray:
    """Global histogram equalisation on the luminance (Y) channel."""
    ycc = cv2.cvtColor(img, cv2.COLOR_RGB2YCrCb)
    ycc[..., 0] = cv2.equalizeHist(ycc[..., 0])
    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB)


def gamma(img: np.ndarray, g: float) -> np.ndarray:
    """Power-law transformation s = 255 * (r/255)^g."""
    return np.uint8(np.clip(np.power(img / 255.0, g) * 255, 0, 255))


def negative(img: np.ndarray) -> np.ndarray:
    return 255 - img


def log_transform(img: np.ndarray) -> np.ndarray:
    c = 255 / np.log1p(max(1, int(img.max())))
    return np.uint8(np.clip(c * np.log1p(img.astype(np.float64)), 0, 255))


def contrast_stretch(img: np.ndarray, low_pct: float = 1, high_pct: float = 99) -> np.ndarray:
    """Piecewise-linear stretch of each channel between two percentiles."""
    out = np.empty_like(img)
    for c in range(3):
        lo, hi = np.percentile(img[..., c], [low_pct, high_pct])
        out[..., c] = np.clip((img[..., c].astype(np.float64) - lo) * 255 / max(hi - lo, 1), 0, 255)
    return out


def michelson_contrast(gray: np.ndarray) -> float:
    """Contrast = (Imax - Imin) / (Imax + Imin), using robust 1st/99th percentiles."""
    lo, hi = np.percentile(gray, [1, 99])
    return float((hi - lo) / (hi + lo + 1e-6))


# ------------------------------------------------------------------ Lab 3: filtering
def box_blur(img, k=5):
    return cv2.blur(img, (k, k))


def gaussian_blur(img, k=5):
    return cv2.GaussianBlur(img, (k, k), 0)


def median_blur(img, k=5):
    return cv2.medianBlur(img, k)


def sobel_magnitude(gray: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return cv2.convertScaleAbs(np.sqrt(gx ** 2 + gy ** 2))


def laplacian(gray: np.ndarray) -> np.ndarray:
    return cv2.convertScaleAbs(cv2.Laplacian(gray, cv2.CV_64F))


def unsharp_mask(img: np.ndarray, alpha: float = 1.5, k: int = 21) -> np.ndarray:
    blur = cv2.GaussianBlur(img, (k, k), 0)
    return cv2.addWeighted(img, 1 + alpha, blur, -alpha, 0)


def canny(gray: np.ndarray, lo: int = 50, hi: int = 150) -> np.ndarray:
    return cv2.Canny(gray, lo, hi)


def edge_density(edges: np.ndarray) -> float:
    return float((edges > 0).mean())


# ------------------------------------------------------------------ Lab 4: segmentation
def otsu(gray: np.ndarray) -> tuple[np.ndarray, float]:
    t, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return mask, float(t)


def adaptive_threshold(gray: np.ndarray, block: int = 31, c: int = 5) -> np.ndarray:
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, c)


def kmeans_segment(img: np.ndarray, k: int = 4, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Colour segmentation with cv2.kmeans; returns (segmented image, cluster centres)."""
    cv2.setRNGSeed(seed)
    data = np.float32(img.reshape(-1, 3))
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    _, labels, centers = cv2.kmeans(data, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    centers = np.uint8(centers)
    return centers[labels.ravel()].reshape(img.shape), centers


# ------------------------------------------------------------------ Lab 5: feature extraction
def sift_keypoints(gray: np.ndarray, max_kp: int = 2000):
    kp = cv2.SIFT_create(nfeatures=max_kp).detect(gray, None)
    return kp


def fast_keypoints(gray: np.ndarray, threshold: int = 25):
    return cv2.FastFeatureDetector_create(threshold=threshold).detect(gray, None)


def harris_corners(gray: np.ndarray, rel_thresh: float = 0.01) -> np.ndarray:
    r = cv2.cornerHarris(np.float32(gray), 2, 3, 0.04)
    return r > rel_thresh * r.max()


def draw_keypoints(img: np.ndarray, kp, color=(255, 64, 64)) -> np.ndarray:
    return cv2.drawKeypoints(img, kp, None, color=color, flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)


def hog_image(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    feats, vis = hog(gray, orientations=9, pixels_per_cell=(16, 16), cells_per_block=(2, 2),
                     visualize=True, feature_vector=True)
    vis = np.uint8(255 * vis / (vis.max() + 1e-9))
    return feats, vis


def lbp(gray: np.ndarray, p: int = 8, r: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Uniform LBP code image and its normalised histogram."""
    codes = local_binary_pattern(gray, p, r, method="uniform")
    hist, _ = np.histogram(codes, bins=np.arange(p + 3), density=True)
    return np.uint8(255 * codes / (p + 1)), hist


def feature_summary(img: np.ndarray) -> dict:
    """Low-level statistics used to compare raw vs enhanced images (Labs 2-5)."""
    g = to_gray(img)
    _, t = otsu(g)
    mask, _ = otsu(g)
    _, h = lbp(g)
    return {
        "Michelson contrast": michelson_contrast(g),
        "Canny edge density": edge_density(canny(g)),
        "SIFT keypoints": len(sift_keypoints(g)),
        "FAST corners": len(fast_keypoints(g)),
        "Otsu threshold": t,
        "Otsu foreground %": float((mask > 0).mean() * 100),
        "LBP entropy": float(-(h[h > 0] * np.log2(h[h > 0])).sum()),
    }
