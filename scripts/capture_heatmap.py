#!/usr/bin/env python3
"""
capture_heatmap.py
Nasdaq-100 热力图，适配 Kindle 墨水屏：
- 涨：白底黑字 / 跌：黑底白字 / 平：灰底白字
- 方块大小按市值权重（treemap squarified）
- 字体放大，清晰易读
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

OUTPUT_DIR = Path(__file__).parent.parent / "docs"
IMAGE_PATH = OUTPUT_DIR / "heatmap.png"
HTML_PATH  = OUTPUT_DIR / "index.html"

# Nasdaq-100 成分股，附带近似市值权重（越大方块越大）
# 格式: (ticker, 相对权重)
STOCKS = [
    # Technology
    ("AAPL",  13.0), ("MSFT", 12.5), ("NVDA", 11.0), ("AVGO",  4.0),
    ("ASML",   2.0), ("AMD",   2.0), ("QCOM",  1.8), ("TXN",   1.5),
    ("MU",     1.5), ("AMAT",  1.4), ("LRCX",  1.2), ("KLAC",  1.1),
    ("ADI",    1.1), ("INTC",  0.9), ("MRVL",  0.9), ("CDNS",  0.9),
    ("SNPS",   0.9), ("ADBE",  1.8), ("CSCO",  1.8), ("ANET",  1.2),
    # Communication
    ("GOOGL",  5.0), ("GOOG",  2.5), ("META",  5.5), ("NFLX",  2.8),
    ("TMUS",   1.5), ("CMCSA", 1.2),
    # Consumer
    ("AMZN",   8.0), ("TSLA",  4.5), ("BKNG",  1.5), ("MAR",   0.8),
    ("SBUX",   0.8), ("ABNB",  0.8), ("ORLY",  0.9), ("AZO",   0.8),
    ("CPRT",   0.7), ("DLTR",  0.5),
    # Healthcare
    ("AMGN",   1.5), ("GILD",  1.0), ("VRTX",  1.2), ("REGN",  1.0),
    ("ISRG",   1.3), ("DXCM",  0.6), ("ILMN",  0.4), ("MRNA",  0.5),
    ("BIIB",   0.5), ("IDXX",  0.5),
    # Industrials / Others
    ("HON",    1.2), ("CTAS",  0.8), ("FAST",  0.7), ("ODFL",  0.6),
    ("VRSK",   0.7), ("DDOG",  0.9), ("ZS",    0.7), ("PANW",  1.2),
    ("CRWD",   1.1), ("PDD",   1.5),
    # More
    ("COST",   2.5), ("PEP",   1.5), ("WBD",   0.5), ("KDP",   0.5),
    ("MNST",   0.6), ("FANG",  0.5), ("CEG",   0.6), ("BKR",   0.5),
    ("EXC",    0.5), ("XEL",   0.4),
]

ALL_TICKERS = [s[0] for s in STOCKS]

# ── 拉取数据 ──────────────────────────────────────────────────────────────────
def fetch_data():
    print("正在从 Yahoo Finance 拉取数据...")
    raw = yf.download(
        ALL_TICKERS, period="2d", interval="1d",
        group_by="ticker", auto_adjust=True,
        progress=False, threads=True,
    )
    results = {}
    for ticker in ALL_TICKERS:
        try:
            try:
                closes = raw[ticker]["Close"].dropna()
            except Exception:
                closes = raw["Close"][ticker].dropna()
            if len(closes) >= 2:
                pct = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100
                results[ticker] = float(pct)
            else:
                results[ticker] = 0.0
        except Exception as e:
            print(f"  [warn] {ticker}: {e}")
            results[ticker] = 0.0
    print(f"  获取到 {len(results)} 只股票数据")
    return results

# ── Squarified Treemap ────────────────────────────────────────────────────────
def squarify(sizes, x, y, w, h):
    """返回 [(x, y, w, h), ...] 列表，按 squarified treemap 算法排列。"""
    sizes = np.array(sizes, dtype=float)
    total = sizes.sum()
    if total == 0 or len(sizes) == 0:
        return []
    sizes = sizes / total * (w * h)

    rects = []
    _squarify(list(sizes), x, y, w, h, rects)
    return rects

def _worst(row, w):
    s = sum(row)
    if s == 0:
        return float('inf')
    return max(max(r for r in row) * w * w / s / s,
               s * s / min(r for r in row) / w / w)

def _squarify(sizes, x, y, w, h, rects):
    if not sizes:
        return
    if len(sizes) == 1:
        rects.append((x, y, w, h))
        return

    total = sum(sizes)
    short = min(w, h)
    row = []
    remaining = list(sizes)

    while remaining:
        candidate = row + [remaining[0]]
        if row and _worst(candidate, short) > _worst(row, short):
            break
        row = candidate
        remaining.pop(0)

    row_sum = sum(row)
    if w >= h:
        row_w = row_sum / total * w
        cy = y
        for r in row:
            ch = r / row_sum * h
            rects.append((x, cy, row_w, ch))
            cy += ch
        _squarify(remaining, x + row_w, y, w - row_w, h, rects)
    else:
        row_h = row_sum / total * h
        cx = x
        for r in row:
            cw = r / row_sum * w
            rects.append((cx, y, cw, row_h))
            cx += cw
        _squarify(remaining, x, y + row_h, w, h - row_h, rects)

# ── 生成热力图 ────────────────────────────────────────────────────────────────
def make_heatmap(data: dict) -> str:
    # 1448×1072 Kindle，dpi=100 → 14.48×10.72 inches
    fig_w, fig_h = 14.48, 10.72
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor="black")

    # 留顶部给标题
    TITLE_H = 0.06
    PAD = 0.01

    ax = fig.add_axes([PAD, PAD, 1 - 2*PAD, 1 - TITLE_H - PAD])
    ax.set_facecolor("black")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # 按权重排列（大→小）
    stock_weights = []
    for ticker, weight in STOCKS:
        stock_weights.append((ticker, weight))
    stock_weights.sort(key=lambda x: -x[1])

    tickers_sorted = [t for t, _ in stock_weights]
    weights_sorted = [w for _, w in stock_weights]

    rects = squarify(weights_sorted, 0, 0, 1, 1)

    for i, (ticker, (rx, ry, rw, rh)) in enumerate(zip(tickers_sorted, rects)):
        pct = data.get(ticker, 0.0)

        # 颜色逻辑
        THRESH = 0.15
        if pct > THRESH:
            face_color = "white"
            text_color = "black"
        elif pct < -THRESH:
            face_color = "black"
            text_color = "white"
        else:
            face_color = "#555555"
            text_color = "white"

        GAP = 0.002
        rect = FancyBboxPatch(
            (rx + GAP, ry + GAP),
            rw - 2*GAP, rh - 2*GAP,
            boxstyle="round,pad=0.001",
            linewidth=0.4,
            edgecolor="#222222",
            facecolor=face_color,
            transform=ax.transAxes,
        )
        ax.add_patch(rect)

        # 字体大小：根据方块面积动态计算
        area = rw * rh
        base = np.sqrt(area) * 90
        fs_ticker = np.clip(base, 5, 26)
        fs_pct    = np.clip(base * 0.65, 4, 18)

        cx = rx + rw / 2
        cy = ry + rh / 2

        if fs_ticker >= 5:
            ax.text(cx, cy + rh * 0.1,
                    ticker,
                    transform=ax.transAxes,
                    fontsize=fs_ticker,
                    color=text_color,
                    ha="center", va="center",
                    fontweight="bold")
            if fs_pct >= 4.5:
                ax.text(cx, cy - rh * 0.15,
                        f"{pct:+.2f}%",
                        transform=ax.transAxes,
                        fontsize=fs_pct,
                        color=text_color,
                        ha="center", va="center")

    # 标题
    et = timezone(timedelta(hours=-5))
    now_str = datetime.now(et).strftime("%Y-%m-%d %H:%M ET")
    fig.text(0.5, 1 - TITLE_H/2,
             f"Nasdaq-100  ·  {now_str}",
             fontsize=16, color="white",
             ha="center", va="center",
             fontweight="bold")



    tmp = str(IMAGE_PATH).replace(".png", "_raw.png")
    plt.savefig(tmp, dpi=100, bbox_inches="tight",
                facecolor="black", pad_inches=0)
    plt.close()
    return tmp

# ── 墨水屏后处理 ──────────────────────────────────────────────────────────────
def process_for_eink(src: str):
    img = Image.open(src).convert("L")
    img = ImageOps.autocontrast(img, cutoff=0)
    img = ImageEnhance.Contrast(img).enhance(1.3)
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
  <p>更新：{now_str} ET · 数据来源：Yahoo Finance</p>
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
