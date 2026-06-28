#!/usr/bin/env python3
"""
capture_heatmap.py
抓取 FinViz Nasdaq-100 热力图，转换为适合 Kindle 墨水屏显示的灰度图片，
并更新 docs/index.html。
"""

import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from playwright.sync_api import sync_playwright

# ── 配置 ────────────────────────────────────────────────────────────────────
FINVIZ_URL = "https://finviz.com/map.ashx?t=etf&st=&sv=1d&g=sector&v=110&e=&p=&a=&bg=&rg=&co=&bs=&ts=&m=nasdaq100"
OUTPUT_DIR = Path(__file__).parent.parent / "docs"
IMAGE_PATH = OUTPUT_DIR / "heatmap.png"
HTML_PATH  = OUTPUT_DIR / "index.html"

# Kindle 8 屏幕分辨率 (1072 × 1448)，横屏显示时宽度优先
KINDLE_W = 1072
KINDLE_H = 1448

# ── 截图 ─────────────────────────────────────────────────────────────────────
def capture(url: str) -> Image.Image:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=60_000)

        # 等待热力图 canvas/svg 渲染完成
        page.wait_for_selector("#mapCanvas, canvas, svg.map", timeout=30_000)
        time.sleep(3)   # 额外等待 JS 渲染

        # 只截取热力图主体区域，跳过导航栏和侧边栏
        # FinViz 热力图容器 selector
        try:
            elem = page.query_selector("#mapCanvas") or page.query_selector("canvas")
            if elem:
                box = elem.bounding_box()
                clip = {
                    "x": box["x"],
                    "y": box["y"],
                    "width": box["width"],
                    "height": box["height"],
                }
            else:
                raise RuntimeError("未找到热力图元素，退而截全屏")
        except Exception as e:
            print(f"[warn] {e}，截全屏")
            clip = None

        raw_bytes = page.screenshot(clip=clip, type="png")
        browser.close()

    from io import BytesIO
    return Image.open(BytesIO(raw_bytes))


# ── 图像处理：适配墨水屏 ──────────────────────────────────────────────────────
def process_for_eink(img: Image.Image) -> Image.Image:
    # 1. 转灰度
    gray = img.convert("L")

    # 2. FinViz 红绿两色在灰度下非常接近（都约 100-130），
    #    用反转+对比度拉伸把涨跌区分开：
    #    原图：红色(跌) ≈ 深灰，绿色(涨) ≈ 中灰
    #    我们想要：跌→黑，涨→白，平盘→灰
    #    策略：先做自动对比度拉伸，再轻微锐化
    enhanced = ImageOps.autocontrast(gray, cutoff=2)

    # 3. 提升对比度，让深浅差异更明显
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.8)

    # 4. 轻微锐化，让文字更清晰
    enhanced = enhanced.filter(ImageFilter.SHARPEN)

    # 5. 调整到 Kindle 屏幕尺寸（保持比例，居中填充黑色背景）
    enhanced.thumbnail((KINDLE_W, KINDLE_H), Image.LANCZOS)
    canvas = Image.new("L", (KINDLE_W, KINDLE_H), color=0)  # 黑色背景
    offset_x = (KINDLE_W - enhanced.width) // 2
    offset_y = (KINDLE_H - enhanced.height) // 2
    canvas.paste(enhanced, (offset_x, offset_y))

    return canvas


# ── 生成 HTML ────────────────────────────────────────────────────────────────
def write_html(updated_at: str):
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="3600">
<title>Nasdaq 100 热力图</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #000;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: monospace;
  }}
  img {{
    max-width: 100%;
    max-height: 95vh;
    display: block;
  }}
  p {{
    color: #888;
    font-size: 12px;
    margin-top: 6px;
    text-align: center;
  }}
</style>
</head>
<body>
  <img src="heatmap.png?t={int(time.time())}" alt="Nasdaq 100 Heatmap">
  <p>更新时间：{updated_at} ET &nbsp;|&nbsp; 数据来源：FinViz</p>
</body>
</html>
"""
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"[ok] HTML 已写入 {HTML_PATH}")


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/3] 正在截取 FinViz 热力图...")
    raw_img = capture(FINVIZ_URL)

    print("[2/3] 正在转换为墨水屏灰度图...")
    eink_img = process_for_eink(raw_img)
    eink_img.save(IMAGE_PATH, "PNG", optimize=True)
    print(f"[ok] 图片已保存到 {IMAGE_PATH}")

    print("[3/3] 更新 HTML 页面...")
    et = timezone(timedelta(hours=-5))  # EST（非夏令时）
    now_et = datetime.now(et).strftime("%Y-%m-%d %H:%M")
    write_html(now_et)

    print("[done] 全部完成！")


if __name__ == "__main__":
    main()
