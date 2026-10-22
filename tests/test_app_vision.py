import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import vision as V  # noqa: E402


@pytest.fixture(scope="module")
def img(underwater):
    return underwater


def test_lab1(img):
    assert V.image_info(img)["channels"] == 3
    assert V.pixel_rgb(img, 0, 0) == tuple(int(v) for v in img[0, 0])
    assert V.resize(img, 200).shape[1] == 200
    assert V.rotate(img, 30).shape == img.shape
    boxed = V.draw_boxes(img, np.array([[0.1, 0.1, 0.5, 0.5]]), np.array([1]), conf=np.array([0.9]))
    assert boxed.shape == img.shape and not np.array_equal(boxed, img)


def test_lab2(img):
    h = V.channel_histograms(img)
    assert h.shape == (3, 256) and h.sum(axis=1)[0] == img.shape[0] * img.shape[1]
    eq = V.hist_equalize(img)
    assert V.michelson_contrast(V.to_gray(eq)) >= V.michelson_contrast(V.to_gray(img))
    assert V.gamma(img, 1.0).dtype == np.uint8
    assert np.array_equal(V.negative(V.negative(img)), img)
    assert V.contrast_stretch(img).max() == 255


def test_lab3(img):
    g = V.to_gray(img)
    for f in (V.box_blur, V.gaussian_blur, V.median_blur):
        assert f(img).shape == img.shape
    assert V.sobel_magnitude(g).dtype == np.uint8
    assert 0 < V.edge_density(V.canny(g)) < 1
    assert V.unsharp_mask(img).shape == img.shape


def test_lab4(img):
    g = V.to_gray(img)
    mask, t = V.otsu(g)
    assert set(np.unique(mask)) <= {0, 255} and 0 < t < 255
    seg, centers = V.kmeans_segment(img, 3)
    assert seg.shape == img.shape and len(centers) == 3


def test_lab5_and_summary(img):
    g = V.to_gray(img)
    assert len(V.sift_keypoints(g)) > 0 and len(V.fast_keypoints(g)) > 0
    feats, vis = V.hog_image(g)
    assert feats.ndim == 1 and vis.shape == g.shape
    codes, hist = V.lbp(g)
    assert hist.sum() == pytest.approx(1.0)
    s = V.feature_summary(img)
    assert s["SIFT keypoints"] > 0 and 0 <= s["Otsu foreground %"] <= 100
