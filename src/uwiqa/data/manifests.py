"""Standard manifest format used by every downstream script.

A manifest is a CSV with columns:
    image   path relative to the dataset root
    mos     subjective score (float) or empty
    scene   id of the underlying raw image (groups enhanced variants;
            used for intra-scene SRCC and leakage-free splits)
    method  'raw', 'reference', or the enhancement algorithm name

Builders below turn each dataset's native layout into this format. For MOS
datasets whose release format we have not verified (UID2021, SAUD, UWIQA,
LUIQD) use ``from_table`` driven by configs/datasets.yaml — inspect the
download first and fill in the column names / regexes.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
COLUMNS = ["image", "mos", "scene", "method"]


def _images(d: Path):
    return sorted(p for p in d.rglob("*") if p.suffix.lower() in IMG_EXTS)


def build_uieb(root: str | Path) -> pd.DataFrame:
    """UIEB: raw-890/, reference-890/, challenging-60/ (no per-image MOS)."""
    root = Path(root)
    rows = []
    for sub, method in [("raw-890", "raw"), ("reference-890", "reference"),
                        ("challenging-60", "raw_challenging")]:
        d = root / sub
        if not d.exists():
            continue
        for p in _images(d):
            rows.append({"image": p.relative_to(root).as_posix(), "mos": None,
                         "scene": p.stem, "method": method})
    if not rows:
        raise FileNotFoundError(f"no UIEB folders under {root}")
    return pd.DataFrame(rows, columns=COLUMNS)


def build_euvp_test(root: str | Path) -> pd.DataFrame:
    """EUVP paired test set: test_samples/Inp and test_samples/GTr."""
    root = Path(root)
    base = root / "test_samples"
    rows = []
    for sub, method in [("Inp", "raw"), ("GTr", "reference")]:
        for p in _images(base / sub):
            rows.append({"image": p.relative_to(root).as_posix(), "mos": None,
                         "scene": p.stem, "method": method})
    if not rows:
        raise FileNotFoundError(f"no EUVP test_samples under {root}")
    return pd.DataFrame(rows, columns=COLUMNS)


def from_table(root: str | Path, table: str, image_col: str, mos_col: str,
               image_dir: str = "", scene_regex: str | None = None,
               method_regex: str | None = None, sheet: str | int = 0,
               image_suffix: str = "") -> pd.DataFrame:
    """Generic MOS-table → manifest.

    ``scene_regex`` / ``method_regex`` are applied to the image filename and
    must contain one capture group, e.g. scene_regex=r"^(\\d+)_" for
    "12_fusion.png". Missing image files are reported, not silently dropped.
    """
    root = Path(root)
    tp = root / table
    df = pd.read_excel(tp, sheet_name=sheet) if tp.suffix in {".xls", ".xlsx"} else pd.read_csv(tp)
    out = pd.DataFrame({
        "image": [Path(image_dir, f"{x}{image_suffix}").as_posix() for x in df[image_col]],
        "mos": pd.to_numeric(df[mos_col], errors="coerce"),
    })
    names = out["image"].map(lambda s: Path(s).name)
    out["scene"] = names.map(lambda n: _extract(scene_regex, n, Path(n).stem))
    out["method"] = names.map(lambda n: _extract(method_regex, n, "unknown"))
    missing = [p for p in out["image"] if not (root / p).exists()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} images in {table} not found, e.g. {missing[:3]}")
    return out[COLUMNS]


def _extract(regex, s, default):
    if not regex:
        return default
    m = re.search(regex, s)
    return m.group(1) if m else default


def dataset_root(name: str) -> Path:
    """DATA_ROOT / <root from configs/datasets.yaml>."""
    import yaml
    from uwiqa import DATA_ROOT, PROJECT_ROOT
    cfg = yaml.safe_load(open(PROJECT_ROOT / "configs" / "datasets.yaml"))
    return DATA_ROOT / cfg[name]["root"]


def load_manifest(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"manifest {path} missing columns {missing}")
    return df
