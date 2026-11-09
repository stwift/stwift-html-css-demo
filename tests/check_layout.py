"""Test actual local files over HTTP, including intentional Before defects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from collections.abc import Generator
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from threading import Thread
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (320, 375, 390, 480, 481, 768, 850, 851, 1024, 1280, 1440, 1920)
METRICS = (Path(__file__).parent / "layout_metrics.js").read_text(encoding="utf-8")
CONTRAST = (Path(__file__).parent / "contrast.js").read_text(encoding="utf-8")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve(root: Path) -> Generator[str, None, None]:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(root))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def fixed_failures(data: dict, width: int) -> list[str]:
    failures = []
    if data["scrollWidth"] > data["clientWidth"] + 1:
        failures.append("Horizontal overflow")
    if data["shellOverflow"] in ("clip", "hidden"):
        failures.append("Page shell masks overflow")
    for key in ("outside", "clippedText", "obscuredText", "invalidLinks", "collisions"):
        if data[key]:
            failures.append(f"{key}: {data[key]}")
    if not data["navVisible"]:
        failures.append("Navigation hidden")
    if any(not link["visible"] or link["height"] < 44 for link in data["links"]):
        failures.append("A link is hidden or its target is shorter than 44px")
    cards = data["cards"]
    if width > 850:
        if max(c["width"] for c in cards) - min(c["width"] for c in cards) > 1:
            failures.append("Unequal desktop cards")
        if max(c["y"] for c in cards) - min(c["y"] for c in cards) > 1:
            failures.append("Staggered desktop cards")
    elif any(cards[i]["bottom"] > cards[i + 1]["y"] + 1 for i in range(2)):
        failures.append("Cards are not stacked on narrow screens")
    if any(not item["loaded"] for item in data["images"]):
        failures.append("Image did not load")
    return failures


def keyboard_check(page: Page) -> list[str]:
    failures = []
    page.goto(page.url.split("#")[0])
    for link in page.locator("a").all():
        page.keyboard.press("Tab")
        if not link.evaluate("(e) => e === document.activeElement"):
            failures.append("Unexpected keyboard focus order")
            break
        focus = link.evaluate("""e => {
          const r=e.getBoundingClientRect(),s=getComputedStyle(e);
          return {visible:r.left>=0 && r.right<=innerWidth+1 && r.top>=0 && r.bottom<=innerHeight+1,
            outlined:s.outlineStyle!=='none' && parseFloat(s.outlineWidth)>=2};
        }""")
        if not focus["visible"] or not focus["outlined"]:
            failures.append(f"Focus not visible: {link.inner_text()}")
    page.goto(page.url.split("#")[0])
    page.keyboard.press("Tab")
    if page.locator(":focus").get_attribute("href") != "#main":
        failures.append("Skip link missing from keyboard navigation")
        return failures
    page.keyboard.press("Enter")
    if page.evaluate("document.activeElement.id") != "main":
        failures.append("Skip link does not focus main")
    return failures


def capture(page: Page, folder: Path, state: str, width: int, manifest: dict) -> None:
    device = "mobile" if width == 390 else "desktop"
    folder.mkdir(parents=True, exist_ok=True)
    for full_page, suffix in ((False, "_viewport"), (True, "")):
        path = folder / f"{state}_{device}{suffix}.png"
        page.screenshot(path=str(path), full_page=full_page)
        manifest[path.name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "viewport": page.viewport_size,
            "full_page": full_page,
            "state": state,
            "path": "/index.html?broken=1" if state == "before" else "/index.html",
        }


def check_page(
    browser: Browser,
    base: str,
    width: int,
    broken: bool,
    screenshots: Path | None,
    manifest: dict,
) -> dict:
    height = 844 if width <= 850 else 800
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        reduced_motion="reduce",
    )
    page = context.new_page()
    page.set_default_timeout(5000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            errors.append(message.text) if message.type == "error" else None
        ),
    )
    page.on(
        "requestfailed", lambda request: errors.append(f"Request failed: {request.url}")
    )
    page.on(
        "response",
        lambda response: (
            errors.append(f"HTTP {response.status}: {response.url}")
            if response.status >= 400
            else None
        ),
    )
    external: list[str] = []

    def route_request(route):
        if route.request.url.startswith(base + "/"):
            route.continue_()
        else:
            external.append(route.request.url)
            route.abort()

    page.route("**/*", route_request)
    try:
        response = page.goto(
            base + "/index.html" + ("?broken=1" if broken else ""), wait_until="load"
        )
        page.locator("#hero-title").wait_for()
        data = page.evaluate(METRICS)
        failures = []
        if response is None or response.status != 200:
            failures.append("Document did not load with HTTP 200")
        if data["broken"] != broken:
            failures.append("URL mode switch failed")
        if data["headingCount"] != 1 or not data["hasViewport"] or not data["hasLang"]:
            failures.append("Missing structural HTML metadata")
        if broken:
            if width <= 850:
                if (
                    data["scrollWidth"] <= data["clientWidth"] + 1
                    or not data["outside"]
                ):
                    failures.append(
                        "Intentional narrow-screen overflow no longer reproduced"
                    )
            else:
                cards = data["cards"]
                if (
                    cards[1]["y"] <= cards[0]["y"] + 1
                    or abs(cards[0]["width"] - cards[1]["width"]) <= 1
                ):
                    failures.append(
                        "Intentional desktop card defects no longer reproduced"
                    )
                if "hero actions" not in data["collisions"]:
                    failures.append(
                        "Intentional displaced CTA overlap no longer reproduced"
                    )
        else:
            failures.extend(fixed_failures(data, width))
            total = page.evaluate("document.documentElement.scrollHeight")
            for y in range(height // 2, total, height // 2):
                page.evaluate("(y) => window.scrollTo(0,y)", y)
                hidden = page.evaluate(METRICS)["obscuredText"]
                if hidden:
                    failures.append(f"Text obscured after scroll: {hidden}")
            page.evaluate("window.scrollTo(0,0)")
            data["contrast"] = page.evaluate(CONTRAST)
            if data["contrast"]["failures"]:
                failures.append(f"Text contrast: {data['contrast']['failures']}")
            if width in (320, 390, 768, 1280):
                failures.extend(keyboard_check(page))
                for href in ("#services", "#approach", "#demo-info"):
                    target = page.locator(f'.nav a[href="{href}"]')
                    if target.count() and target.is_visible():
                        target.click()
                        if page.evaluate("location.hash") != href:
                            failures.append(f"Navigation failed for {href}")
                    else:
                        failures.append(f"Navigation unavailable for {href}")
                page.goto(base + "/index.html")
        if screenshots and width in (390, 1280):
            capture(page, screenshots, "before" if broken else "after", width, manifest)
        failures.extend(errors + [f"External request: {url}" for url in external])
        return {
            "width": width,
            "height": height,
            "state": "before" if broken else "after",
            "failures": failures,
            "measurements": data,
        }
    finally:
        context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "test-results")
    parser.add_argument(
        "--browsers",
        nargs="+",
        choices=("chromium", "firefox", "webkit"),
        default=["chromium"],
    )
    parser.add_argument(
        "--screenshots",
        action="store_true",
        help="Update Chromium screenshots and hash manifest",
    )
    args = parser.parse_args()
    if args.screenshots and "chromium" not in args.browsers:
        parser.error("--screenshots requires chromium in --browsers")
    args.output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.system(),
        "playwright": version("playwright"),
        "results": [],
        "browsers": {},
    }
    manifest: dict = {}
    with serve(args.root.resolve()) as base, sync_playwright() as pw:
        for name in args.browsers:
            browser_type = getattr(pw, name)
            options: dict[str, Any] = {"headless": True, "timeout": 15000}
            if name == "chromium" and os.getenv("CHROME_PATH"):
                options["executable_path"] = os.environ["CHROME_PATH"]
            try:
                browser = browser_type.launch(**options)
            except PlaywrightError as error:
                report["browsers"][name] = {"error": str(error)}
                continue
            try:
                report["browsers"][name] = {"version": browser.version}
                for width in WIDTHS:
                    for broken in (False, True):
                        result = check_page(
                            browser,
                            base,
                            width,
                            broken,
                            args.root / "screenshots"
                            if args.screenshots and name == "chromium"
                            else None,
                            manifest,
                        )
                        result["browser"] = name
                        report["results"].append(result)
                        status = "FAIL" if result["failures"] else "PASS"
                        line = (
                            f"{status} {name} {width}px {result['state']}: "
                            + "; ".join(result["failures"])
                        )
                        print(
                            line.encode("ascii", errors="backslashreplace").decode(
                                "ascii"
                            ),
                            flush=True,
                        )
                context = browser.new_context(
                    java_script_enabled=False, viewport={"width": 390, "height": 844}
                )
                page = context.new_page()
                page.goto(base + "/index.html")
                if (
                    not page.get_by_role("heading", level=1).is_visible()
                    or not page.get_by_role("navigation").is_visible()
                ):
                    report["browsers"][name]["no_js_error"] = (
                        "Main content or navigation unavailable"
                    )
                context.close()
                page = browser.new_page()
                page.goto(base + "/index.html?broken=0")
                if page.locator("html").get_attribute("class") == "broken":
                    report["browsers"][name]["query_error"] = (
                        "?broken=0 must show After"
                    )
                page.close()
            finally:
                browser.close()
    failed = any(r["failures"] for r in report["results"]) or any(
        any(k.endswith("error") for k in value) for value in report["browsers"].values()
    )
    report["passed"] = not failed
    (args.output / "results.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    if args.screenshots and not failed:
        manifest["_sources"] = {
            name: hashlib.sha256((args.root / name).read_bytes()).hexdigest()
            for name in ("index.html", "assets/style.css", "assets/broken.css")
        }
        manifest["_environment"] = {
            "platform": platform.system(),
            "playwright": version("playwright"),
            "browser": report["browsers"].get("chromium"),
            "device_scale_factor": 1,
        }
        (args.root / "screenshots" / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    print(
        f"{len(report['results'])} layout cases; overall {'FAIL' if failed else 'PASS'}"
    )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
