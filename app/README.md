# Demo application

A local web app for the FCV Lab mini project: a FastAPI back end (`server.py`) around the project code and a
hand-written black-and-white front end (`static/`: HTML, CSS, JavaScript, no framework).

Pages: **Overview**, **Enhancement** (five enhancers + colour histograms), **Quality** (live UIQM / UCIQE next to the
true detection change), **Lab 1–5** (OpenCV operations from the lab manual on any version, with live sliders) and
**Detection** (frozen YOLO11-s on every version, per-image AP and ΔAP for the bundled samples).

## 1. Get the assets (once)
Run Kaggle notebook `notebooks/07_kaggle_demo_assets.ipynb` (CPU, ~5 min; inputs: the ODverse33 dataset and your
notebook 05 output). Download `demo_assets.zip` from its Output panel and unzip it here:

```
app/assets/best.pt
app/assets/third_party/FUnIE-GAN/PyTorch/{nets, models/funie_generator.pth}
app/assets/samples/{images, labels, samples.csv}
```
The assets are git-ignored (dataset licences). Without them the app still runs: upload only, no FUnIE-GAN, no
detection.

## 2. Run
```bash
pip install -e ".[app]"
python app/server.py
```
Open http://127.0.0.1:8000.

## 3. Report screenshots
With the app running: `python report/capture_screenshots.py --samples sample_00 sample_04`, then
`python report/build_report.py` rebuilds `report/FCV_MiniProject_Report.docx` and `.pdf`.
