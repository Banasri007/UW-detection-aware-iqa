"""Capture demo-app screenshots for the report (Chapter 4) with Playwright + installed Edge.

Start the app first:   python app/server.py
Then:                  python report/capture_screenshots.py [--samples sample_00 sample_04]
Each view is opened by URL, the script waits until the page sets body[data-ready="1"]
(all data fetched, all images decoded), then saves a full-page report/assets/ui_<name>.png.
The overview keeps the image picker; the other views hide it (and the page footer) so the content fills the shot.
"""
import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "assets"
URL = "http://127.0.0.1:8000/"
HIDE_FOOT = "footer.foot { display: none !important; }"
HIDE_PICKER = HIDE_FOOT + (".picker { display: none !important; } .main { max-width: none !important; }"
                           ".shell { grid-template-columns: 1fr !important; background: var(--bg) !important; }")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", nargs="*", default=["sample_00", "sample_04"],
                    help="first: main sample; others: extra detection views")
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()
    s0 = args.samples[0]
    views = [("overview", f"#/overview?img={s0}"), ("enhance", f"#/enhance?img={s0}"),
             ("quality", f"#/quality?img={s0}")]
    views += [(f"lab{k}", f"#/lab?img={s0}&lab={k}&v=raw") for k in ("1", "2", "3", "4", "5", "S")]
    views += [("detect", f"#/detect?img={s0}")]
    views += [(f"detect_{k + 2}", f"#/detect?img={s}") for k, s in enumerate(args.samples[1:])]
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel, headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5,
                                  color_scheme="light")
        page = ctx.new_page()
        for name, route in views:
            side = name == "overview"
            page.set_viewport_size({"width": 1440 if side else 1180, "height": 900})
            page.goto(URL + route, wait_until="domcontentloaded")
            page.wait_for_function("document.body.dataset.ready === '1'", timeout=300_000)
            page.add_style_tag(content=HIDE_FOOT if side else HIDE_PICKER)
            page.evaluate("document.fonts.ready")
            time.sleep(0.8)
            f = OUT / f"ui_{name}.png"
            page.screenshot(path=str(f), full_page=True)
            print(f"saved {f.name}")
        browser.close()


if __name__ == "__main__":
    main()
