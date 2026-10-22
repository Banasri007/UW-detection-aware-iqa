"""Pack everything the local demo app needs into /kaggle/working/demo_assets.zip.

Contents (unzip into app/assets/):
  best.pt                      frozen YOLO11-s reference detector (notebook 03)
  third_party/FUnIE-GAN/...    official FUnIE-GAN PyTorch code + generator weights
  samples/images/*.jpg         held-out RUOD pred_test images (never seen by the detector)
  samples/labels/*.txt         their YOLO ground-truth boxes
  samples/samples.csv          per-image AP of raw and every enhancer from the paper's labels

Samples are chosen deliberately: some where an enhancer helps detection by more than
the noise threshold, some where every enhancer hurts, and some mixed, so the demo shows
the per-image variation behind the paper's results.

    python scripts/pack_demo_assets.py --n-help 4 --n-hurt 4 --n-mixed 4
"""
import argparse
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from uwiqa import RESULTS_ROOT
from uwiqa.data import dataset_root
from uwiqa.enhance.deep import THIRD_PARTY

TAU = 0.05  # noise threshold used in the paper (95th pct of |delta| for the null re-encode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-help", type=int, default=4)
    ap.add_argument("--n-hurt", type=int, default=4)
    ap.add_argument("--n-mixed", type=int, default=4)
    ap.add_argument("--max-objects", type=int, default=15)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="/kaggle/working/demo_assets")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "samples" / "images").mkdir(parents=True)
    (out / "samples" / "labels").mkdir(parents=True)

    best = RESULTS_ROOT / "detector" / "raw_yolo11s" / "weights" / "best.pt"
    shutil.copy2(best, out / "best.pt")
    print(f"detector: {best} ({best.stat().st_size / 1e6:.1f} MB)")

    funie = THIRD_PARTY / "FUnIE-GAN" / "PyTorch"
    dst = out / "third_party" / "FUnIE-GAN" / "PyTorch"
    shutil.copytree(funie / "nets", dst / "nets")
    (dst / "models").mkdir(parents=True)
    shutil.copy2(funie / "models" / "funie_generator.pth", dst / "models" / "funie_generator.pth")
    print("FUnIE-GAN code + weights copied")

    sc = pd.read_csv(RESULTS_ROOT / "utility" / "ruod_pred" / "main" / "scores.csv")
    split = pd.read_csv(RESULTS_ROOT / "splits" / "ruod_splits.csv").set_index("image")
    w = sc.pivot_table(index="image", columns="method", values="ap")
    n_gt = sc.groupby("image")["n_gt"].first()
    w = w[(split.reindex(w.index)["split"] == "pred_test").values]
    w = w[(n_gt.reindex(w.index) >= 2) & (n_gt.reindex(w.index) <= args.max_objects)]
    methods = [c for c in w.columns if c not in ("raw", "null_jpeg95")]
    d = w[methods].sub(w["raw"], axis=0)
    best_gain = d.max(axis=1)
    rng = np.random.default_rng(args.seed)
    pick = lambda idx, k: list(rng.choice(np.array(idx), size=min(k, len(idx)), replace=False))
    chosen = (pick(best_gain[best_gain > TAU].index, args.n_help)
              + pick(best_gain[best_gain < -TAU].index, args.n_hurt)
              + pick(best_gain[(best_gain.abs() <= TAU)].index, args.n_mixed))

    root = dataset_root("ruod")
    rows = []
    for k, rel in enumerate(chosen):
        name = f"sample_{k:02d}"
        src = root / rel
        shutil.copy2(src, out / "samples" / "images" / f"{name}{src.suffix.lower()}")
        parts = rel.split("/")
        i = len(parts) - 1 - parts[::-1].index("images")
        parts[i] = "labels"
        shutil.copy2(root.joinpath(*parts).with_suffix(".txt"), out / "samples" / "labels" / f"{name}.txt")
        row = {"sample": name, "file": f"{name}{src.suffix.lower()}", "source": rel,
               "n_objects": int(n_gt[rel]), "ap_raw": w.at[rel, "raw"]}
        row.update({f"ap_{m}": w.at[rel, m] for m in methods})
        row["best"] = "raw" if best_gain[rel] <= 0 else d.loc[rel].idxmax()
        row["kind"] = ("enhancement helps" if best_gain[rel] > TAU else
                       "all enhancers hurt" if best_gain[rel] < -TAU else "within noise")
        rows.append(row)
    pd.DataFrame(rows).to_csv(out / "samples" / "samples.csv", index=False)
    print(pd.DataFrame(rows)[["sample", "n_objects", "ap_raw", "best", "kind"]].round(3).to_string(index=False))

    zpath = out.with_suffix(".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in out.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(out))
    print(f"\nwrote {zpath} ({zpath.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
