"""Build data/manifests/<name>.csv for every dataset in configs/datasets.yaml.

    python scripts/build_manifests.py            # all datasets that exist
    python scripts/build_manifests.py --only uieb
"""
import argparse
import sys

import yaml

from uwiqa import DATA_ROOT, PROJECT_ROOT
from uwiqa.data import build_euvp_test, build_uieb, from_table

BUILDERS = {"uieb": build_uieb, "euvp_test": build_euvp_test}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=PROJECT_ROOT / "configs" / "datasets.yaml")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    out_dir = DATA_ROOT / "manifests"
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, c in cfg.items():
        if args.only and name not in args.only:
            continue
        root = DATA_ROOT / c["root"]
        if not root.exists():
            print(f"[skip] {name}: {root} not found")
            continue
        try:
            if c["builder"] == "table":
                kw = {k: v for k, v in c.items() if k not in {"root", "builder"} and v is not None}
                if any(v == "TODO" or str(v).startswith("TODO") for v in kw.values()):
                    print(f"[skip] {name}: fill in the TODOs in datasets.yaml first")
                    continue
                df = from_table(root, **kw)
            else:
                df = BUILDERS[c["builder"]](root)
        except Exception as e:  # report and continue with other datasets
            print(f"[fail] {name}: {e}")
            ok = False
            continue
        dest = out_dir / f"{name}.csv"
        df.to_csv(dest, index=False)
        n_mos = df["mos"].notna().sum()
        print(f"[ok]   {name}: {len(df)} images ({n_mos} with MOS, "
              f"{df['scene'].nunique()} scenes, {df['method'].nunique()} methods) -> {dest}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
