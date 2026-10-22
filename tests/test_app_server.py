import importlib
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("fastapi")
import asyncio  # noqa: E402

import httpx  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


class SyncASGIClient:
    """Minimal sync wrapper over httpx.AsyncClient + ASGITransport (works across Starlette/httpx versions)."""

    def __init__(self, app):
        self.app = app

    def _call(self, method, url, **kw):
        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://t") as c:
                return await c.request(method, url, **kw)
        return asyncio.run(go())

    def get(self, url, **kw):
        return self._call("GET", url, **kw)

    def post(self, url, **kw):
        return self._call("POST", url, **kw)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """Server without demo assets: upload-only, no FUnIE-GAN, no detector."""
    import os
    assets = tmp_path_factory.mktemp("assets")
    os.environ["UWIQA_DEMO_ASSETS"] = str(assets)
    os.environ["THIRD_PARTY"] = str(assets / "third_party")
    import server
    server = importlib.reload(server)
    return SyncASGIClient(server.app)


@pytest.fixture(scope="module")
def img_id(client, underwater):
    buf = io.BytesIO()
    Image.fromarray(underwater).save(buf, "JPEG")
    r = client.post("/api/upload", files={"file": ("u.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 200
    return r.json()["id"]


def test_index_and_status(client):
    assert client.get("/").status_code == 200
    s = client.get("/api/status").json()
    assert s["detector"] is False and s["samples"] == []


def test_upload_rejects_non_image(client):
    r = client.post("/api/upload", files={"file": ("x.txt", b"not an image", "text/plain")})
    assert r.status_code == 400


def test_enhance_and_images(client, img_id):
    d = client.get(f"/api/enhance/{img_id}").json()
    keys = [v["key"] for v in d["variants"]]
    assert keys[0] == "raw" and {"clahe", "gray_world", "udcp", "fusion"} <= set(keys)
    assert len(d["hist"]["raw"]) == 3 and len(d["hist"]["raw"][0]) == 64
    r = client.get(f"/api/img/{img_id}/clahe.jpg?w=300")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/thumb/{img_id}.jpg").status_code == 200


def test_quality_features(client, img_id):
    q = client.get(f"/api/quality/{img_id}").json()
    assert q["has_study"] is False and all(r["uiqm"] > 0 for r in q["rows"])
    f = client.get(f"/api/features/{img_id}").json()
    assert f["rows"][0]["SIFT keypoints"] > 0


@pytest.mark.parametrize("lab", [1, 2, 3, 4, 5])
def test_lab(client, img_id, lab):
    d = client.get(f"/api/lab/{img_id}/{lab}?variant=clahe&gamma=1.2&k=3").json()
    assert d["items"] and all(it["img"].startswith("data:image/jpeg;base64,") for it in d["items"])


def test_detect_without_weights_and_unknown(client, img_id):
    assert client.get(f"/api/detect/{img_id}").status_code == 503
    assert client.get("/api/enhance/nope").status_code == 404
    assert client.get(f"/api/lab/{img_id}/9").status_code == 404
