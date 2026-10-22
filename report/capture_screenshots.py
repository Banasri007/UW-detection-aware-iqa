"""Capture demo-app screenshots for the report (Chapter 4) with Playwright + installed Edge.

Start the app first:   streamlit run app/app.py --server.headless true
Then:                  python report/capture_screenshots.py [--samples sample_00 sample_04]
Each view is opened by URL parameters, the script waits until Streamlit has finished running,
then saves report/assets/ui_<name>.png.
"""
import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "assets"
URL = "http://localhost:8501/"


def wait_until_idle(page, timeout=240):
    """Streamlit shows a 'Running...' status widget while the script executes."""
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=timeout * 1000)
    t0, quiet = time.time(), 0
    while time.time() - t0 < timeout:
        running = page.locator('[data-testid="stStatusWidget"]').count() > 0
        skeleton = page.locator('[data-testid="stSkeleton"]').count() > 0
        spinner = page.locator('[data-testid="stSpinner"]').count() > 0
        quiet = quiet + 1 if not (running or skeleton or spinner) else 0
        if quiet >= 4:  # ~2 s without activity
            return
        time.sleep(0.5)
    raise TimeoutError("app did not finish rendering")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", nargs="*", default=["sample_00", "sample_04"],
                    help="first: main sample; others: extra detection views")
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()
    s0 = args.samples[0]
    views = [
        ("overview", f"page=overview&sample={s0}", 1250),
        ("enhance", f"page=enhance&sample={s0}", 1350),
        ("quality", f"page=quality&sample={s0}", 1500),
        ("lab", f"page=lab&sample={s0}&variant=raw", 4300),
        ("detect", f"page=detect&sample={s0}", 1500),
    ] + [(f"detect_{k + 2}", f"page=detect&sample={s}", 1500) for k, s in enumerate(args.samples[1:])]
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel, headless=True)
        for name, query, height in views:
            ctx = browser.new_context(viewport={"width": 1440, "height": height}, device_scale_factor=1.5,
                                      color_scheme="light")
            page = ctx.new_page()
            page.goto(URL + "?" + query, wait_until="networkidle")
            wait_until_idle(page)
            time.sleep(1.5)  # let images and charts paint
            f = OUT / f"ui_{name}.png"
            page.screenshot(path=str(f))
            print(f"saved {f.name}")
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
