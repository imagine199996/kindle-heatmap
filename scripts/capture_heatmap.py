#!/usr/bin/env python3
"""
capture_heatmap.py
用 yfinance 拉取 Nasdaq-100 数据，生成适合 Kindle 墨水屏的灰度热力图。
"""

import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

# ── 配置 ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent.parent / "docs"
IMAGE_PATH = OUTPUT_DIR / "heatmap.png"
HTML_PATH  = OUTPUT_DIR / "index.html"

# Nasdaq-100 成分股（按板块分组）
SECTORS = {
    "Technology": [
        "AAPL","MSFT","NVDA","AVGO","AMD","QCOM","TXN","MU","AMAT","LRCX",
        "KLAC","MRVL","ADI","INTC","ASML","CSCO","ANET","CDNS","SNPS","ADBE"
    ],
    "Communication": [
        "GOOGL","GOOG","META","NFLX","TMUS","CMCSA"
    ],
    "Consumer": [
        "AMZN","TSLA","SBUX","BKNG","MAR","ABNB","ORLY","AZO","CPRT","DLTR"
    ],
    "Healthcare": [
        "AMGN","GILD","VRTX","REGN","ISRG","DXCM","ILMN","MRNA","BIIB","IDXX"
    ],
    "Industrials": [
        "HON","PDD","CTAS","FAST","ODFL","VRSK","DDOG","ZS","PANW","CRWD"
    ],
    "Other": [
        "COST","PEP","WBD","KDP","MNST","FANG","CEG","BKR","EXC","XEL"
    ],
}

ALL_TICKERS = [t for tickers in SECTORS.values() for t in tickers]

# ── 拉取数据 ─────────────────────────────────────────────────────────────────
def fetch_data():
    print("正在从 Yahoo Finance 拉取数据...")
    raw = yf.download(
        ALL_TICKERS,
        period="2d",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    results = {}
    for ticker in ALL_TICKERS:
        try:
            if ticker in raw.columns.get_level_values(0):
                closes = raw[ticker]["Close"].dropna()
            else:
                closes = raw["Close"][ticker].dropna()
            if len(closes) >= 2:
                pct = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100
                results[ticker] = float(pct)
            elif len(closes) == 1:
                results[ticker] = 0.0
        except Exception as e:
            print(f"  [warn] {ticker}: {e}")
            results[ticker] = 0.0

    print(f"  获取到 {len(results)} 只股票数据")
    return results

# ── 生成热力图 ────────────────────────────────────────────────────────────────
def make_heatmap(data: dict) -> str:
    # Kindle 8 横屏：1448×1072，留边距
    fig_w, fig_h = 14.48, 10.72
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor="black")
    ax.set_facecolor("black")
    ax.axis("off")

    n_sectors = len(SECTORS)
    cols = 3
    rows = (n_sectors + cols - 1) // cols

    sector_list = list(SECTORS.items())
    cell_w = 1.0 / cols
    cell_h = 0.92 / rows  # 留顶部空间给标题

    for idx, (sector_name, tickers) in enumerate(sector_list):
        row = idx // cols
        col = idx % cols

        x0 = col * cell_w + 0.01
        y0 = 0.96 - (row + 1) * cell_h + 0.005
        w  = cell_w - 0.015
        h  = cell_h - 0.01

        # 板块标题
        ax.text(
            x0 + w / 2, y0 + h + 0.003,
            sector_name.upper(),
            transform=ax.transAxes,
            fontsize=6, color="#aaaaaa",
            ha="center", va="bottom",
            fontweight="bold",
        )

        # 在板块内均匀排列股票方块
        valid = [t for t in tickers if t in data]
        if not valid:
            continue

        n = len(valid)
        sub_cols = min(n, int(np.ceil(np.sqrt(n * w / h))))
        sub_rows = int(np.ceil(n / sub_cols))

        sw = w / sub_cols
        sh = h / sub_rows

        for i, ticker in enumerate(valid):
            sc = i % sub_cols
            sr = i // sub_cols

            pct = data[ticker]
            # 灰度映射：跌→深灰/黑，平→中灰，涨→浅灰/白
            # 范围约 -5% ~ +5%
            norm = np.clip(pct / 5.0, -1, 1)
            # -1→0.05(黑), 0→0.45(中灰), +1→0.92(白)
            gray = 0.45 + norm * 0.45
            gray = float(np.clip(gray, 0.05, 0.95))

            bx = x0 + sc * sw
            by = y0 + (sub_rows - 1 - sr) * sh

            rect = FancyBboxPatch(
                (bx + 0.002, by + 0.002),
                sw - 0.004, sh - 0.004,
                boxstyle="round,pad=0.001",
                linewidth=0.3,
                edgecolor="#333333",
                facecolor=(gray, gray, gray),
                transform=ax.transAxes,
            )
            ax.add_patch(rect)

            # 文字：大方块显示 ticker + 涨跌幅，小方块只显示 ticker
            font_size = min(sw * fig_w * 6, sh * fig_h * 6, 9)
            text_color = "black" if gray > 0.55 else "white"

            cx = bx + sw / 2
            cy = by + sh / 2

            if font_size >= 5:
                ax.text(
                    cx, cy + sh * 0.08,
                    ticker,
                    transform=ax.transAxes,
                    fontsize=max(font_size, 4.5),
                    color=text_color,
                    ha="center", va="center",
                    fontweight="bold",
                )
                if font_size >= 6:
                    ax.text(
                        cx, cy - sh * 0.18,
                        f"{pct:+.1f}%",
                        transform=ax.transAxes,
                        fontsize=max(font_size * 0.75, 3.5),
                        color=text_color,
                        ha="center", va="center",
                    )

    # 标题
    et = timezone(timedelta(hours=-5))
    now_str = datetime.now(et).strftime("%Y-%m-%d %H:%M ET")
    ax.text(
        0.5, 0.985,
        f"Nasdaq-100  |  {now_str}",
        transform=ax.transAxes,
        fontsize=9, color="#cccccc",
        ha="center", va="top",
    )

    # 图例
    legend_items = [
        (-4, "跌>4%"), (-2, "-2%"), (0, "平盘"), (2, "+2%"), (4, "涨>4%")
    ]
    for li, (pct_val, label) in enumerate(legend_items):
        norm = np.clip(pct_val / 5.0, -1, 1)
        gray = float(np.clip(0.45 + norm * 0.45, 0.05, 0.95))
        lx = 0.02 + li * 0.07
        rect = FancyBboxPatch(
            (lx, 0.002), 0.055, 0.018,
            boxstyle="round,pad=0.001",
            linewidth=0.3,
            edgecolor="#555",
            facecolor=(gray, gray, gray),
            transform=ax.transAxes,
        )
        ax.add_patch(rect)
        tc = "black" if gray > 0.55 else "white"
        ax.text(lx + 0.0275, 0.011, label,
                transform=ax.transAxes,
                fontsize=4.5, color=tc, ha="center", va="center")

    plt.tight_layout(pad=0)
    tmp = str(IMAGE_PATH).replace(".png", "_raw.png")
    plt.savefig(tmp, dpi=100, bbox_inches="tight",
                facecolor="black", pad_inches=0.05)
    plt.close()
    return tmp

# ── 墨水屏后处理 ─────────────────────────────────────────────────────────────
def process_for_eink(src: str):
    img = Image.open(src).convert("L")
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(1.4)
    img = img.filter(ImageFilter.SHARPEN)
    img.save(IMAGE_PATH, "PNG", optimize=True)
    print(f"[ok] 图片已保存: {IMAGE_PATH}")

# ── HTML ──────────────────────────────────────────────────────────────────────
def write_html():
    et = timezone(timedelta(hours=-5))
    now_str = datetime.now(et).strftime("%Y-%m-%d %H:%M")
    ts = int(time.time())
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="refresh" content="3600">
<title>Nasdaq 100 热力图</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#000;display:flex;flex-direction:column;
        align-items:center;justify-content:center;min-height:100vh}}
  img{{max-width:100%;max-height:96vh;display:block}}
  p{{color:#666;font-size:11px;margin-top:4px;font-family:monospace}}
</style>
</head>
<body>
  <img src="heatmap.png?t={ts}" alt="Nasdaq 100 Heatmap">
  <p>更新：{now_str} ET &nbsp;·&nbsp; 数据来源：Yahoo Finance</p>
</body>
</html>"""
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"[ok] HTML 已写入: {HTML_PATH}")

# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/3] 拉取股票数据...")
    data = fetch_data()
    print("[2/3] 生成热力图...")
    tmp = make_heatmap(data)
    process_for_eink(tmp)
    Path(tmp).unlink(missing_ok=True)
    print("[3/3] 更新 HTML...")
    write_html()
    print("[done] 完成！")

if __name__ == "__main__":
    main()
