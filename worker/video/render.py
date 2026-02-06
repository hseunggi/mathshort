from __future__ import annotations
import os
from pathlib import Path
from typing import Dict
from playwright.sync_api import sync_playwright

def fill_template(html: str, ctx: Dict[str, str]) -> str:
    for k, v in ctx.items():
        html = html.replace("{{" + k + "}}", v or "")
    return html

def render_scene_png(template_path: Path, out_png: Path, ctx: Dict[str, str]) -> None:
    html = template_path.read_text(encoding="utf-8")
    html = fill_template(html, ctx)

    tmp_html = out_png.with_suffix(".html")
    tmp_html.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(tmp_html.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(200)  # MathJax 렌더 안정화
        page.screenshot(path=str(out_png), full_page=True)
        browser.close()

    tmp_html.unlink(missing_ok=True)
