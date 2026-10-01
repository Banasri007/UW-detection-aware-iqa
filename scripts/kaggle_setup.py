"""One-cell setup for every Kaggle notebook in this project.

First cell of each notebook (never needs editing again):

    !test -d /kaggle/working/repo || git clone -q https://github.com/Banasri007/UW-detection-aware-iqa.git /kaggle/working/repo
    %run /kaggle/working/repo/scripts/kaggle_setup.py            # add "iqa" or "detect" for extras

It updates the code to the latest GitHub version (discarding edits to tracked
files; outputs live outside the repo), installs the package, makes it
importable in the running kernel, and points every *_ROOT variable at the
attached Kaggle inputs. All later steps are one-line `!python scripts/...`
or `%run scripts/...` calls, so new code arrives with a re-run of this cell.
"""
import glob
import os
import subprocess
import sys

REPO = "/kaggle/working/repo"
WORK = "/kaggle/working"
extras = [a for a in sys.argv[1:] if a in {"iqa", "detect", "dev"}]


def sh(cmd):
    subprocess.run(cmd, shell=True, check=True)


sh(f"git -C {REPO} fetch -q origin && git -C {REPO} reset -q --hard origin/main")
print("code @", subprocess.run(["git", "-C", REPO, "log", "-1", "--format=%h %s"],
                               capture_output=True, text=True).stdout.strip())
spec = REPO + (f"[{','.join(extras)}]" if extras else "")
sh(f'{sys.executable} -m pip install -q -e "{spec}"')

os.chdir(REPO)
src = f"{REPO}/src"
if src not in sys.path:
    sys.path.insert(0, src)
for m in [m for m in sys.modules if m == "uwiqa" or m.startswith("uwiqa.")]:
    del sys.modules[m]  # pick up the freshly pulled code on re-runs

os.environ.setdefault("RESULTS_ROOT", f"{WORK}/results")
os.environ.setdefault("DATA_ROOT", f"{WORK}/data")
os.makedirs(os.environ["DATA_ROOT"], exist_ok=True)

found = {}
for name in ("RUOD", "DUO"):
    hits = glob.glob(f"/kaggle/input/**/Underwater/{name}", recursive=True)
    if hits:
        os.environ[f"{name}_ROOT"] = found[name] = hits[0]
uid = glob.glob("/kaggle/input/**/UID2021*", recursive=True)
os.environ["UID2021_ROOT"] = found["UID2021"] = uid[0] if uid else f"{os.environ['DATA_ROOT']}/UID2021"

for k, v in found.items():
    print(f"{k:8s} {v}  {'(ok)' if os.path.exists(v) else '(not present yet)'}")
print("RESULTS ", os.environ["RESULTS_ROOT"])
