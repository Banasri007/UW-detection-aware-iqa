# Demo application

Interactive Streamlit app for the FCV Lab mini project: enhancers, UIQM/UCIQE, Lab 1–5 operations and
YOLO11-s detections on individual underwater images.

## 1. Get the assets (once)
Run Kaggle notebook `notebooks/07_kaggle_demo_assets.ipynb` (CPU, ~5 min; inputs: the ODverse33 dataset and
your notebook 05 output). Download `demo_assets.zip` from its Output panel and unzip it here, so that you have:

```
app/assets/best.pt
app/assets/third_party/FUnIE-GAN/PyTorch/{nets, models/funie_generator.pth}
app/assets/samples/{images, labels, samples.csv}
```
The assets are git-ignored (dataset licences).

## 2. Run
```bash
pip install -e ".[app]"
streamlit run app/app.py
```
Open http://localhost:8501. Pages: Overview, Enhancement, Quality scores, Lab 1–5 operations, Detection.
Without assets the app still runs (upload only, no FUnIE-GAN or detection).

## 3. Report screenshots
With the app running: `python report/capture_screenshots.py --samples sample_00 sample_04`, then
`python report/build_report.py` rebuilds the report (`report/FCV_MiniProject_Report.docx` and `.pdf`).
