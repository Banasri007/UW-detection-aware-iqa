"""Download and unpack UID2021 from the authors' Google Drive link.

Licence: non-commercial research use; cite Hou et al., ACM TOMM 2023.
Skips if UID2021_ROOT already exists (e.g. attached as a Kaggle Dataset).

    python scripts/get_uid2021.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from uwiqa.data import dataset_root

URL = "https://drive.google.com/file/d/1cD8a_IsQHkQ_q-mDV6PvRql_gTZPRnk5/view"

root = dataset_root("uid2021")
if root.exists() and any(root.iterdir()):
    print(f"UID2021 already present at {root}")
    sys.exit(0)

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown"], check=True)
archive = root.parent / "uid2021_archive"
root.mkdir(parents=True, exist_ok=True)
subprocess.run(["gdown", "-q", "--fuzzy", URL, "-O", str(archive)], check=True)
kind = subprocess.run(["file", "-b", str(archive)], capture_output=True, text=True).stdout
print("archive type:", kind.strip())
if "Zip" in kind:
    shutil.unpack_archive(str(archive), str(root), "zip")
else:  # RAR / 7z
    subprocess.run(["7z", "x", "-y", f"-o{root}", str(archive)], check=True, stdout=subprocess.DEVNULL)
os.remove(archive)
n = sum(1 for p in Path(root).rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"})
print(f"UID2021 unpacked to {root}: {n} images (expected 960)")
