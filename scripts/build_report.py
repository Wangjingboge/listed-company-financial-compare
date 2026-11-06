# -*- coding: utf-8 -*-
"""
A股财报分析-望京博格版 —— 单页 HTML 报告渲染器。

用法:
    python build_report.py data.json -o 报告.html
    python build_report.py data.json            # 默认输出 同目录/<标题>.html

输入 data.json 结构见 SKILL.md「三、组装 data.json」。
仅依赖 Python 标准库，输出为单文件 HTML（内联 CSS + 内联 SVG），离线可打开。
"""
import argparse
import json
import os
import sys
import datetime

# ============================ 设计常量 ============================

C_BG = "#F4F5F7"
C_CARD = "#FFFFFF"
C_LINE = "#E3E6EB"
C_TEXT = "#1A1D21"
C_SUB = "#5F6875"
C_MUTED = "#8A929E"

# A 股色彩习惯：涨 / 正增长 = 红，跌 / 负增长 = 绿
C_UP = "#C0392B"
C_DOWN = "#1B7F4B"

# 每家公司一套主色（营收用深色，净利用浅色）
COMPANY_STYLES = [
    {"main": "#1F4E79", "light": "#8FB3D9"},
    {"main": "#A34E1E", "light": "#E5B183"},
    {"main": "#3F5D45", "light": "#A3C0A9"},
    {"main": "#5B3E7A", "light": "#B9A2CD"},
]

SEGMENT_COLORS = ["#1F4E79", "#4A82B8", "#8FB3D9", "#C9D9EA", "#E4EBF4", "#B0B8C4"]

FONT = ('-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", '
        '"Hiragino Sans GB", "Microsoft YaHei", sans-serif')


# ============================ 工具函数 ============================

def esc(v):
    if v is None:
        return ""
    return (str(v).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def fmt_num(v, digits=1):
    v = num(v)
    s = f"{v:,.{digits}f}"
    return s


def fmt_pct(v, digits=1, sign=True):
    v = num(v)
    s = f"{v:+.{digits}f}%" if sign else f"{v:.{digits}f}%"
    return s


def trend_color(v):
    v = num(v)
    if v > 0:
        return C_UP
    if v < 0:
        return C_DOWN
    return C_SUB


def safe_list(seq, n, default=0.0):
    seq = list(seq or [])
    out = []
    for i in range(n):
        out.append(num(seq[i]) if i < len(seq) else default)
    return out


def svg_text(x, y, s, size=12, fill=C_TEXT, anchor="middle", weight="400", opacity=1.0):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" opacity="{opacity}" '
            f'font-family="{FONT}">{esc(s)}</text>')


def norm_pct(v, default=0.0):
    """分位数归一化：数据源可能返回 0-1 小数，也可能返回 0-100 百分数。"""
    v = num(v, default)
    if 0 < v <= 1.0:
        return v * 100.0
    return v


def _pct_label(v, prefix="近三年分位 "):
    """分位数展示：小于 1% 时保留一位小数，避免被取整成 0%。"""
    p = norm_pct(v)
    if p < 1:
        return f"{prefix}{p:.2f}%"
    return f"{prefix}{p:.0f}%"


def _gm_text(c, periods):
    """毛利率副标题：金融类公司无毛利率口径，不能显示 0.0%。"""
    gm = safe_list(c.get("gross_margin"), len(periods))[-1]
    if not gm:
        return "无毛利率口径"
    return f"毛利率 {gm:.1f}%"


def nice_ceiling(v):
    """把最大值抬到一个好看的刻度上。"""
    if v <= 0:
        return 1.0
    import math
    exp = math.floor(math.log10(v))
    base = 10 ** exp
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * base:
            return m * base
    return 10 * base


# ============================ 图表：营收 / 净利规模 ============================

def chart_scale_and_yoy(companies, periods, key, yoy_key, caption, unit="亿元", color_idx=0):
    W, H = 1080, 400
    L, R, T, B = 76, 28, 34, 56
    pw, ph = W - L - R, H - T - B
    n = len(companies)
    bars_per_group = n * 2

    vals = []
    for c in companies:
        vals += safe_list(c.get(key), len(periods))
    ymax = nice_ceiling(max(vals) * 1.18 if vals else 1)

    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" role="img">']
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{C_CARD}"/>')
    out.append(svg_text(L - 12, T - 14, unit, 11, C_MUTED, "start"))

    # 网格 + y 轴刻度
    steps = 5
    for i in range(steps + 1):
        y = T + ph - ph * i / steps
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" '
                   f'stroke="{C_LINE}" stroke-width="1"/>')
        out.append(svg_text(L - 12, y + 4, fmt_num(ymax * i / steps, 0), 11, C_MUTED, "end"))

    group_w = pw / len(periods)
    bar_area = group_w * 0.74
    bw = bar_area / bars_per_group

    for gi, p in enumerate(periods):
        gx = L + gi * group_w
        out.append(svg_text(gx + group_w / 2, T + ph + 26, p, 13, C_SUB, "middle", "600"))
        for ci, c in enumerate(companies):
            style = COMPANY_STYLES[(color_idx + ci) % len(COMPANY_STYLES)]
            # 营收 / 净利两根柱：营收在主色，净利用本公司的第二色
            for si in range(2):
                v = safe_list(c.get(key), len(periods))[gi] if si == 0 else \
                    safe_list(c.get(key + "_np"), len(periods))[gi]
                color = style["main"] if si == 0 else style["light"]
                idx = ci * 2 + si
                x = gx + (group_w - bar_area) / 2 + idx * bw + bw * 0.12
                w = bw * 0.76
                h = ph * (v / ymax) if ymax else 0
                y = T + ph - h
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{max(h, 0):.1f}" '
                           f'fill="{color}" rx="2"/>')
                if h > 8:
                    out.append(svg_text(x + w / 2, y - 7, fmt_num(v, 1), 11, C_SUB, "middle", "600"))
                yoy = safe_list(c.get(yoy_key), len(periods))[gi] if si == 0 else \
                    safe_list(c.get(yoy_key + "_np"), len(periods))[gi]
                if h > 62:
                    out.append(svg_text(x + w / 2, y + 19, fmt_pct(yoy, 1), 10.5,
                                        "#FFFFFF", "middle", "600", 0.95))
    out.append(f'<line x1="{L}" y1="{T + ph}" x2="{L + pw}" y2="{T + ph}" '
               f'stroke="#B9C0C9" stroke-width="1.4"/>')
    out.append("</svg>")
    return "".join(out)


# ============================ 图表：增速对比 ============================

def chart_growth(companies, periods, rev_yoy_key, np_yoy_key, color_idx=0):
    W, H = 1080, 400
    L, R, T, B = 76, 28, 34, 58
    pw, ph = W - L - R, H - T - B
    n = len(companies)
    bars_per_group = n * 2

    vals = []
    for c in companies:
        vals += safe_list(c.get(rev_yoy_key), len(periods))
        vals += safe_list(c.get(np_yoy_key), len(periods))
    vmax = max([0.0] + vals)
    vmin = min([0.0] + vals)
    span = (vmax - vmin) or 1.0
    vmax = vmax + span * 0.18
    vmin = vmin - span * 0.18

    def ymap(v):
        return T + ph * (vmax - v) / (vmax - vmin)

    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" role="img">']
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{C_CARD}"/>')
    out.append(svg_text(L - 12, T - 14, "%", 11, C_MUTED, "start"))

    steps = 4
    for i in range(steps + 1):
        v = vmax - (vmax - vmin) * i / steps
        y = ymap(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{C_LINE}" stroke-width="1"/>')
        out.append(svg_text(L - 12, y + 4, f"{v:.0f}", 11, C_MUTED, "end"))

    zero_y = ymap(0)
    out.append(f'<line x1="{L}" y1="{zero_y:.1f}" x2="{L + pw}" y2="{zero_y:.1f}" '
               f'stroke="#9AA3AE" stroke-width="1.2"/>')

    group_w = pw / len(periods)
    bar_area = group_w * 0.72
    bw = bar_area / bars_per_group

    for gi, p in enumerate(periods):
        gx = L + gi * group_w
        out.append(svg_text(gx + group_w / 2, T + ph + 30, p, 13, C_SUB, "middle", "600"))
        for ci, c in enumerate(companies):
            style = COMPANY_STYLES[(color_idx + ci) % len(COMPANY_STYLES)]
            for si, (k, color) in enumerate([(rev_yoy_key, style["main"]), (np_yoy_key, style["light"])]):
                v = safe_list(c.get(k), len(periods))[gi]
                idx = ci * 2 + si
                x = gx + (group_w - bar_area) / 2 + idx * bw + bw * 0.12
                w = bw * 0.76
                y0, y1 = ymap(0), ymap(v)
                top = min(y0, y1)
                h = abs(y1 - y0)
                out.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{w:.1f}" height="{max(h, 1):.1f}" '
                           f'fill="{color}" rx="2"/>')
                ly = (top - 8) if v >= 0 else (top + h + 16)
                out.append(svg_text(x + w / 2, ly, fmt_pct(v, 1), 10.5,
                                    trend_color(v), "middle", "700"))
    out.append("</svg>")
    return "".join(out)


# ============================ 图表：收入结构 ============================

def chart_segments(company, periods, idx=0):
    W = 1080
    row_h = 46
    legend_h = 44
    blocks = 1
    H = 34 + blocks * (26 + len(periods) * row_h) + legend_h
    L, R = 96, 132
    bar_w = W - L - R
    style = COMPANY_STYLES[idx % len(COMPANY_STYLES)]

    seg = company.get("segments") or {}
    items = seg.get("items") or []
    dim = seg.get("dimension") or "收入构成"

    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" role="img">']
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{C_CARD}"/>')
    out.append(svg_text(L - 84, 22, "口径：" + dim, 11, C_MUTED, "start"))

    y = 44
    for pi, p in enumerate(periods):
        out.append(svg_text(L - 14, y + 20, p, 12.5, C_SUB, "end", "600"))
        # 先取当年各项占比，再按合计归一化，避免“其他业务”另计导致条形溢出画布
        raw_shares = []
        for item in items:
            sr = item.get("shares") or []
            raw_shares.append(num(sr[pi]) if pi < len(sr) else 0.0)
        total_share = sum(raw_shares) or 100.0
        x = L
        for si, item in enumerate(items):
            share = raw_shares[si]
            if share <= 0:
                continue
            w = bar_w * share / total_share
            color = SEGMENT_COLORS[si % len(SEGMENT_COLORS)]
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="32" fill="{color}"/>')
            label = f"{item.get('name','')} {share:.1f}%"
            if w > 108:
                out.append(svg_text(x + 10, y + 21, label, 11.5,
                                    "#FFFFFF" if si < 3 else C_TEXT, "start", "600"))
            elif w > 46:
                out.append(svg_text(x + w / 2, y + 21, f"{share:.0f}%", 11,
                                    "#FFFFFF" if si < 3 else C_TEXT, "middle", "600"))
            x += w
        total = safe_list(company.get("revenue"), len(periods))[pi]
        out.append(svg_text(L + bar_w + 12, y + 21, f"营收 {fmt_num(total, 1)} 亿", 11.5, C_SUB, "start"))
        y += row_h

    # 图例
    ly = y + 8
    lx = L
    for si, item in enumerate(items):
        color = SEGMENT_COLORS[si % len(SEGMENT_COLORS)]
        out.append(f'<rect x="{lx:.1f}" y="{ly}" width="10" height="10" rx="2" fill="{color}"/>')
        out.append(svg_text(lx + 16, ly + 9, item.get("name", ""), 11.5, C_SUB, "start"))
        lx += 22 + len(str(item.get("name", ""))) * 13
    out.append("</svg>")
    return "".join(out)


# ============================ 图表：估值折线 + 分位数 ============================

def chart_valuation_line(company, periods, series_key, label, unit="倍", idx=0):
    W, H = 420, 380
    L, R, T, B = 52, 26, 30, 46
    pw, ph = W - L - R, H - T - B
    style = COMPANY_STYLES[idx % len(COMPANY_STYLES)]
    val = company.get("valuation") or {}
    raw = list(val.get(series_key) or [])
    series = []
    for i in range(len(periods)):
        v = raw[i] if i < len(raw) else None
        series.append(None if v is None else num(v))
    now_key = series_key + "_now"
    now = None if val.get(now_key) is None else num(val.get(now_key))
    labels = list(periods) + ["当前"]
    values = series + [now]

    valid = [v for v in values if v is not None]
    if not valid:
        return ""
    vmax = nice_ceiling(max(valid) * 1.12)
    vmin = min(valid) * 0.82
    if vmax - vmin <= 0:
        vmax = vmin + 1

    def ymap(v):
        return T + ph * (vmax - v) / (vmax - vmin)

    def xmap(i):
        return L + pw * i / max(len(values) - 1, 1)

    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" role="img">']
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{C_CARD}"/>')
    out.append(svg_text(L, 18, label, 12.5, C_TEXT, "start", "700"))
    out.append(svg_text(W - R, 18, unit, 10.5, C_MUTED, "end"))

    for i in range(4):
        v = vmax - (vmax - vmin) * i / 3
        y = ymap(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{C_LINE}" stroke-width="1"/>')
        out.append(svg_text(L - 8, y + 4, f"{v:.0f}", 10, C_MUTED, "end"))

    pts = " ".join(f"{xmap(i):.1f},{ymap(v):.1f}" for i, v in enumerate(values) if v is not None)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{style["main"]}" stroke-width="2.2"/>')
    for i, v in enumerate(values):
        cx = xmap(i)
        out.append(svg_text(cx, H - 22, labels[i], 10.5, C_MUTED, "middle"))
        if v is None:
            out.append(svg_text(cx, ymap(vmin) - 10, "—", 11, C_MUTED, "middle"))
            continue
        cy = ymap(v)
        is_now = i == len(values) - 1
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{4.6 if is_now else 3.6}" '
                   f'fill="{C_UP if is_now else C_CARD}" stroke="{style["main"]}" stroke-width="2"/>')
        anchor = "start" if i == 0 else ("end" if i == len(values) - 1 else "middle")
        dx = 5 if i == 0 else (-5 if i == len(values) - 1 else 0)
        out.append(svg_text(cx + dx, cy - 11, f"{v:.1f}", 10.5, C_TEXT, anchor, "600"))
    out.append("</svg>")
    return "".join(out)


def gauge(pct, label, sub=""):
    import math
    W, H = 250, 158
    cx, cy, r = W / 2, 112, 82
    pct = max(0.0, min(100.0, norm_pct(pct)))
    color = "#2F6B4F" if pct < 30 else ("#B0821F" if pct < 70 else "#A33A2E")
    a0, a1 = math.pi, math.pi * (1 - pct / 100.0)

    def pt(ang):
        return cx + r * math.cos(ang), cy - r * math.sin(ang)

    x0, y0 = pt(a0)
    x1, y1 = pt(a1)
    large = 1 if pct > 50 else 0
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" role="img">']
    out.append(f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {cx + r:.1f} {cy:.1f}" '
               f'fill="none" stroke="{C_LINE}" stroke-width="14" stroke-linecap="round"/>')
    if pct > 0.4:
        out.append(f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 {large} 1 {x1:.1f} {y1:.1f}" '
                   f'fill="none" stroke="{color}" stroke-width="14" stroke-linecap="round"/>')
    out.append(svg_text(cx, cy - 18, f"{pct:.2f}%" if pct < 1 else f"{pct:.1f}%", 26, color, "middle", "700"))
    out.append(svg_text(cx, cy + 8, label, 11.5, C_SUB, "middle"))
    if sub:
        out.append(svg_text(cx, cy + 26, sub, 10.5, C_MUTED, "middle"))
    out.append("</svg>")
    return "".join(out)


# ============================ 表格 ============================

def compare_table(companies, periods):
    metrics = [
        ("营业收入", "revenue", "亿元", "num"),
        ("营收同比", "revenue_yoy", "%", "pct"),
        ("归母净利润", "net_profit", "亿元", "num"),
        ("净利同比", "net_profit_yoy", "%", "pct"),
        ("ROE", "roe", "%", "pct0"),
        ("销售毛利率", "gross_margin", "%", "pct0"),
    ]
    n = len(companies)
    head = "<tr><th class='th-l'>指标</th>" + "".join(
        f"<th>{esc(c.get('name',''))}<span class='th-sub'>{esc(c.get('code',''))}</span></th>"
        for c in companies) + "</tr>"

    rows = []
    for label, key, unit, kind in metrics:
        cells = []
        vals = []
        for c in companies:
            v = safe_list(c.get(key), len(periods))[-1]
            vals.append(v)
        for i, c in enumerate(companies):
            v = vals[i]
            if kind == "num":
                txt, cls = fmt_num(v, 1), "cell-num"
            elif kind == "pct":
                txt, cls = fmt_pct(v, 1), ""
            else:
                txt, cls = f"{v:.1f}%", "cell-num"
            color = trend_color(v) if kind == "pct" else C_TEXT
            cells.append(f"<td class='{cls}' style='color:{color}'>{txt}</td>")
        delta = ""
        if n >= 2:
            diff = vals[0] - vals[1]
            if kind == "pct":
                delta = fmt_pct(diff, 1)
            else:
                delta = ("+" if diff > 0 else "") + fmt_num(diff, 1)
            cells.append(f"<td class='cell-delta' style='color:{trend_color(diff)}'>{delta}</td>")
        rows.append(f"<tr><td class='td-l'>{label}<span class='unit'>{unit}</span></td>" + "".join(cells) + "</tr>")

    head_extra = "<th>差值</th>" if n >= 2 else ""
    return (f"<table class='dtable'><thead><tr><th class='th-l'>指标</th>" +
            "".join(f"<th>{esc(c.get('name',''))}</th>" for c in companies) +
            f"{head_extra}</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def scorecard(companies):
    dims = [("growth", "成长性"), ("profitability", "盈利能力"),
            ("segment", "收入结构质量"), ("valuation", "估值性价比")]
    head = "<tr><th class='th-l'>维度</th>" + "".join(
        f"<th>{esc(c.get('name',''))}</th>" for c in companies) + "</tr>"
    rows = []
    for key, label in dims:
        cells = []
        for ci, c in enumerate(companies):
            sc = c.get("scorecard") or {}
            v = max(0.0, min(5.0, num(sc.get(key))))
            style = COMPANY_STYLES[ci % len(COMPANY_STYLES)]
            cells.append(
                f"<td><div class='bar-wrap'><div class='bar-bg'>"
                f"<div class='bar-fg' style='width:{v / 5 * 100:.0f}%;background:{style['main']}'></div>"
                f"</div><span class='bar-num'>{v:.1f}</span></div></td>")
        rows.append(f"<tr><td class='td-l'>{label}</td>" + "".join(cells) + "</tr>")
    return (f"<table class='dtable score'><thead>{head}</thead><tbody>" +
            "".join(rows) + "</tbody></table>")


# ============================ 页面组装 ============================

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #F4F5F7; color: #1A1D21; font-family: __FONT__;
       -webkit-font-smoothing: antialiased; padding: 32px 20px 64px; }
.wrap { max-width: 1180px; margin: 0 auto; }
.header { background: #fff; border-radius: 16px; padding: 34px 38px 30px;
          border: 1px solid #E3E6EB; position: relative; overflow: hidden; }
.header::before { content: ""; position: absolute; left: 0; top: 0; width: 6px; height: 100%;
                  background: linear-gradient(180deg, #1F4E79, #A34E1E); }
.kicker { font-size: 12px; letter-spacing: 2px; color: #8A929E; text-transform: uppercase;
          font-weight: 600; margin-bottom: 12px; }
h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.4px; line-height: 1.3; }
h1 .vs { color: #B9C0C9; font-weight: 400; padding: 0 10px; }
.meta { margin-top: 14px; font-size: 13px; color: #5F6875; display: flex; flex-wrap: wrap; gap: 8px 22px; }
.meta span b { color: #1A1D21; font-weight: 600; }
.tags { margin-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; }
.tag { font-size: 12px; padding: 4px 11px; border-radius: 20px; background: #EDF1F6; color: #1F4E79; font-weight: 500; }
.tag.warn { background: #FBEFEC; color: #A33A2E; }

.section { background: #fff; border-radius: 16px; border: 1px solid #E3E6EB;
           padding: 26px 30px; margin-top: 18px; }
.section h2 { font-size: 17px; font-weight: 700; margin-bottom: 4px; display: flex; align-items: center; gap: 10px; }
.section h2 .idx { display: inline-flex; align-items: center; justify-content: center;
                   width: 22px; height: 22px; border-radius: 6px; background: #1F4E79; color: #fff;
                   font-size: 12px; font-weight: 700; }
.section .desc { font-size: 13px; color: #5F6875; margin: 6px 0 18px; line-height: 1.7; }

.verdict { background: linear-gradient(180deg,#FBFCFD,#F6F8FA); border: 1px solid #E3E6EB;
           border-left: 4px solid #1F4E79; border-radius: 12px; padding: 20px 24px; margin-top: 18px; }
.verdict .vtitle { font-size: 17px; font-weight: 700; line-height: 1.55; margin-bottom: 10px; }
.verdict p { font-size: 14px; line-height: 1.9; color: #3A4250; margin-top: 8px; }

.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }
.kpi { border: 1px solid #E3E6EB; border-radius: 12px; padding: 14px 16px; background: #FCFCFD; }
.kpi .k { font-size: 12px; color: #8A929E; }
.kpi .v { font-size: 21px; font-weight: 700; margin-top: 6px; letter-spacing: -0.3px; }
.kpi .s { font-size: 11.5px; color: #5F6875; margin-top: 4px; }

.chart { margin-top: 14px; border: 1px solid #EDEFF3; border-radius: 12px; overflow: hidden; background: #fff; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 20px; margin-top: 12px; font-size: 12.5px; color: #5F6875; }
.legend i { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.valgrid { display: grid; grid-template-columns: 1fr 1fr 0.85fr; gap: 12px; align-items: start; }
.gaugebox { border: 1px solid #EDEFF3; border-radius: 12px; padding: 6px 8px 0; }

.dtable { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.dtable th { background: #F6F7F9; color: #5F6875; font-weight: 600; font-size: 12.5px;
             padding: 11px 12px; text-align: right; border-bottom: 1px solid #E3E6EB; }
.dtable th.th-l { text-align: left; }
.dtable th .th-sub { display: block; font-weight: 400; color: #A2AAB5; font-size: 11px; margin-top: 2px; }
.dtable td { padding: 11px 12px; text-align: right; border-bottom: 1px solid #F0F2F5; font-variant-numeric: tabular-nums; }
.dtable td.td-l { text-align: left; color: #3A4250; font-weight: 500; }
.dtable td.td-l .unit { color: #A2AAB5; font-size: 11px; margin-left: 6px; font-weight: 400; }
.dtable tbody tr:last-child td { border-bottom: none; }
.dtable tbody tr:hover td { background: #FAFBFC; }
.cell-num { font-weight: 600; }
.cell-delta { color: #8A929E; background: #FAFBFC; font-weight: 600; }
.score td { vertical-align: middle; }
.bar-wrap { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.bar-bg { width: 100%; max-width: 210px; height: 8px; background: #EDEFF3; border-radius: 4px; overflow: hidden; }
.bar-fg { height: 100%; border-radius: 4px; }
.bar-num { width: 30px; text-align: right; font-weight: 700; color: #3A4250; }

.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.co-box { border: 1px solid #E3E6EB; border-radius: 12px; padding: 18px 20px; }
.co-box .co-name { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.co-box .co-name .dot { width: 9px; height: 9px; border-radius: 50%; }
.co-box h4 { font-size: 12.5px; color: #8A929E; font-weight: 600; margin: 16px 0 8px; letter-spacing: .5px; }
.co-box ul { list-style: none; }
.co-box li { font-size: 13px; line-height: 1.85; color: #3A4250; padding-left: 14px; position: relative; }
.co-box li::before { content: ""; position: absolute; left: 2px; top: 9px; width: 5px; height: 5px;
                     border-radius: 50%; background: #B9C0C9; }
.co-box li.risk::before { background: #C0392B; opacity: .55; }
.co-box p { font-size: 13px; line-height: 1.9; color: #3A4250; }

.scena { width: 100%; border-collapse: collapse; font-size: 13.5px; margin-top: 12px; }
.scena th { text-align: left; font-size: 12.5px; color: #5F6875; background: #F6F7F9; padding: 10px 12px; }
.scena td { padding: 11px 12px; border-bottom: 1px solid #F0F2F5; color: #3A4250; line-height: 1.7; }
.scena td:first-child { font-weight: 600; width: 26%; }

.footer { text-align: left; margin-top: 20px; padding: 20px 24px; background: #fff;
          border: 1px solid #E3E6EB; border-radius: 14px; font-size: 11.5px; color: #8A929E; line-height: 1.9; }
@media (max-width: 900px) {
  .kpis { grid-template-columns: repeat(2, 1fr); }
  .grid2, .cols, .valgrid { grid-template-columns: 1fr; }
  h1 { font-size: 23px; }
}
@media print {
  body { background: #fff; padding: 0; }
  .section, .header, .footer { break-inside: avoid; border-radius: 0; border-color: #ddd; }
}
""".replace("__FONT__", FONT)


def build(data, out_path):
    companies = data.get("companies") or []
    if not companies:
        raise SystemExit("data.json 缺少 companies")
    periods = [str(p) for p in (data.get("periods") or [])]
    if not periods:
        raise SystemExit("data.json 缺少 periods")
    n = len(companies)

    # 章节编号：收入结构 / 横向对比可能整体省略，编号需随之收缩
    has_seg = any((c.get("segments") or {}).get("items") for c in companies)
    has_cmp = n >= 2
    s_kpi, s_growth = 1, 2
    s_seg = 3 if has_seg else 0
    s_val = 4 if has_seg else 3
    s_cmp = (s_val + 1) if has_cmp else 0
    s_eval = (s_cmp + 1) if has_cmp else (s_val + 1)

    for c in companies:
        # 兼容：净利用 net_profit，图表里按 key+"_np" 取
        c["revenue_np"] = c.get("net_profit")
        c["revenue_yoy_np"] = c.get("net_profit_yoy")

    title_companies = "  vs  ".join(esc(c.get("name", "")) for c in companies)
    mode = "单公司财报分析" if n == 1 else f"{n} 家公司财报对比"
    gen = data.get("report_date") or datetime.date.today().strftime("%Y-%m-%d")
    period_txt = f"{periods[0]}–{periods[-1]} 会计年度"

    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_companies} · 财报分析</title>
<style>{CSS}</style></head><body><div class="wrap">""")

    # ---------- Header ----------
    tags = []
    for c in companies:
        if c.get("industry"):
            tags.append(f"<span class='tag'>{esc(c['industry'])}</span>")
    if data.get("data_note"):
        tags.append(f"<span class='tag warn'>{esc(data['data_note'])}</span>")

    meta_bits = "".join(
        f"<span>{esc(c.get('name',''))} <b>{esc(c.get('code',''))}</b></span>" for c in companies)
    parts.append(f"""
<div class="header">
  <div class="kicker">{esc(mode)}</div>
  <h1>{title_companies}</h1>
  <div class="meta">
    {meta_bits}
    <span>数据区间 <b>{esc(period_txt)}</b></span>
    <span>生成日期 <b>{esc(gen)}</b></span>
  </div>
  <div class="tags">{''.join(tags)}</div>
</div>""")

    # ---------- 结论先行 ----------
    verdict = data.get("verdict") or {}
    if verdict.get("title") or verdict.get("paragraphs"):
        paras = "".join(f"<p>{esc(p)}</p>" for p in (verdict.get("paragraphs") or []))
        parts.append(f"""
<div class="verdict">
  <div class="vtitle">{esc(verdict.get('title',''))}</div>
  {paras}
</div>""")

    # ---------- 核心指标 ----------
    kpi_cards = []
    for ci, c in enumerate(companies):
        val = c.get("valuation") or {}
        kpis = [
            ("营业收入", f"{fmt_num(safe_list(c.get('revenue'), len(periods))[-1], 1)} 亿",
             f"同比 {fmt_pct(safe_list(c.get('revenue_yoy'), len(periods))[-1], 1)}",
             trend_color(safe_list(c.get("revenue_yoy"), len(periods))[-1])),
            ("归母净利润", f"{fmt_num(safe_list(c.get('net_profit'), len(periods))[-1], 1)} 亿",
             f"同比 {fmt_pct(safe_list(c.get('net_profit_yoy'), len(periods))[-1], 1)}",
             trend_color(safe_list(c.get("net_profit_yoy"), len(periods))[-1])),
            ("ROE", f"{safe_list(c.get('roe'), len(periods))[-1]:.1f}%",
             _gm_text(c, periods), C_TEXT),
            ("PE(TTM)", f"{num(val.get('pe_now')):.1f} 倍",
             _pct_label(val.get('pe_pct')), C_TEXT),
        ]
        block = "".join(
            f"<div class='kpi'><div class='k'>{k}</div><div class='v'>{v}</div>"
            f"<div class='s' style='color:{sc}'>{s}</div></div>"
            for k, v, s, sc in kpis)
        style = COMPANY_STYLES[ci % len(COMPANY_STYLES)]
        head = (f"<div style='font-size:13px;font-weight:700;color:{style['main']};"
                f"margin-bottom:10px;display:flex;align-items:center;gap:8px'>"
                f"<span style='width:3px;height:13px;background:{style['main']};border-radius:2px'></span>"
                f"{esc(c.get('name',''))} · {esc(periods[-1])}</div>")
        kpi_cards.append(f"<div>{head}<div class='kpis'>{block}</div></div>")

    parts.append(f"""
<div class="section">
  <h2><span class="idx">{s_kpi}</span>核心指标速览</h2>
  <div class="desc">取最近一个完整会计年度的年报口径；PE 为 TTM 口径，分位数区间为最近三年日频数据。</div>
  {''.join(kpi_cards)}
</div>""")

    # ---------- 增长 ----------
    growth_charts = []
    for ci, c in enumerate(companies):
        style = COMPANY_STYLES[ci % len(COMPANY_STYLES)]
        growth_charts.append(f"""
        <div style="margin-bottom:6px">
          <div style="font-size:13px;font-weight:700;color:{style['main']};margin-bottom:6px">{esc(c.get('name',''))}</div>
          <div class="chart">{chart_growth([c], periods, 'revenue_yoy', 'net_profit_yoy', ci)}</div>
        </div>""")

    rev_charts = []
    for ci, c in enumerate(companies):
        style = COMPANY_STYLES[ci % len(COMPANY_STYLES)]
        rev_charts.append(f"""
        <div>
          <div style="font-size:13px;font-weight:700;color:{style['main']};margin-bottom:6px">{esc(c.get('name',''))}</div>
          <div class="chart">{chart_scale_and_yoy([c], periods, 'revenue', 'revenue_yoy', '', '亿元', ci)}</div>
        </div>""")

    parts.append(f"""
<div class="section">
  <h2><span class="idx">{s_growth}</span>营收与盈利增速</h2>
  <div class="desc">上排为营业收入与归母净利润的规模变化（柱内百分比为同比增速），下排为增速本身的对比；红色为正增长、绿色为负增长。</div>
  <div class="grid2">{''.join(rev_charts)}</div>
  <div class="grid2" style="margin-top:18px">{''.join(growth_charts)}</div>
  <div class="legend">
    <span><i style="background:#1F4E79"></i>营业收入 / 营收同比</span>
    <span><i style="background:#8FB3D9"></i>归母净利润 / 净利同比</span>
  </div>
</div>""")

    # ---------- 收入结构 ----------
    seg_blocks = []
    for ci, c in enumerate(companies):
        style = COMPANY_STYLES[ci % len(COMPANY_STYLES)]
        seg_blocks.append(f"""
        <div style="margin-bottom:14px">
          <div style="font-size:13px;font-weight:700;color:{style['main']};margin:2px 0 2px">{esc(c.get('name',''))}</div>
          <div class="chart">{chart_segments(c, periods, ci)}</div>
        </div>""")
    if has_seg:
        parts.append(f"""
<div class="section">
  <h2><span class="idx">{s_seg}</span>收入来源结构（近三年）</h2>
  <div class="desc">按年报主营业务构成口径拆分，标签为该项目占主营收入的比重；占比合计可能超过 100%，因“其他业务”另行计入。</div>
  {''.join(seg_blocks)}
</div>""")

    # ---------- 估值 ----------
    val_blocks = []
    for ci, c in enumerate(companies):
        style = COMPANY_STYLES[ci % len(COMPANY_STYLES)]
        val = c.get("valuation") or {}
        val_blocks.append(f"""
        <div style="border:1px solid #EDEFF3;border-radius:12px;padding:14px 14px 6px;margin-bottom:14px">
          <div style="font-size:13px;font-weight:700;color:{style['main']};margin-bottom:6px">{esc(c.get('name',''))}</div>
          <div class="valgrid">
            <div class="chart" style="margin-top:0">{chart_valuation_line(c, periods, 'pe', 'PE(TTM)', '倍', ci)}</div>
            <div class="chart" style="margin-top:0">{chart_valuation_line(c, periods, 'pb', 'PB', '倍', ci)}</div>
            <div class="gaugebox">
              {gauge(val.get('pe_pct'), 'PE 近三年分位', '当前 ' + f"{num(val.get('pe_now')):.1f} 倍")}
              {gauge(val.get('pb_pct'), 'PB 近三年分位', '当前 ' + f"{num(val.get('pb_now')):.1f} 倍")}
            </div>
          </div>
        </div>""")
    parts.append(f"""
<div class="section">
  <h2><span class="idx">{s_val}</span>估值水平（近三年）</h2>
  <div class="desc">折线为各年末 PE(TTM) / PB 点位，末点为最新交易日；右侧仪表为当前估值在最近三年日频序列中所处的分位，分位越低代表相对自身历史越便宜。</div>
  {''.join(val_blocks)}
</div>""")

    # ---------- 对比表 ----------
    table_html = ""
    if n >= 2:
        table_html = f"""
<div class="section">
  <h2><span class="idx">{s_cmp}</span>关键指标横向对比（{esc(periods[-1])}）</h2>
  <div class="desc">“差值”为首家减后一家的绝对差，正值说明前者更高。</div>
  {compare_table(companies, periods)}
</div>"""
        parts.append(table_html)

    # ---------- 评价 ----------
    boxes = []
    for ci, c in enumerate(companies):
        style = COMPANY_STYLES[ci % len(COMPANY_STYLES)]
        hl = "".join(f"<li>{esc(x)}</li>" for x in (c.get("highlights") or []))
        rk = "".join(f"<li class='risk'>{esc(x)}</li>" for x in (c.get("risks") or []))
        comment = esc(c.get("comment") or "")
        boxes.append(f"""
        <div class="co-box">
          <div class="co-name"><span class="dot" style="background:{style['main']}"></span>{esc(c.get('name',''))}</div>
          <p style="margin-top:10px">{comment}</p>
          <h4>亮点</h4><ul>{hl}</ul>
          <h4>风险与瑕疵</h4><ul>{rk}</ul>
        </div>""")

    scena = ""
    sc = verdict.get("scenarios") or []
    if sc:
        rows = "".join(
            f"<tr><td>{esc(s.get('condition',''))}</td><td>{esc(s.get('pick',''))}</td>"
            f"<td>{esc(s.get('why',''))}</td></tr>" for s in sc)
        scena = (f"<table class='scena'><thead><tr><th>若你的关注点是</th>"
                 f"<th>更优选择</th><th>理由</th></tr></thead><tbody>{rows}</tbody></table>")

    parts.append(f"""
<div class="section">
  <h2><span class="idx">{s_eval}</span>经营质量与投资视角评价</h2>
  <div class="desc">评分口径：0–5 分，成长性看增速水平与稳定性，盈利能力看 ROE 与毛利率绝对值和趋势，收入结构质量看来源集中度与结构优化方向，估值性价比看增速与估值分位的匹配度。</div>
  {scorecard(companies)}
  <div class="cols" style="margin-top:18px;grid-template-columns:{'1fr' if n == 1 else '1fr 1fr'}">{''.join(boxes)}</div>
  {scena}
</div>""")

    # ---------- 免责 ----------
    disc = data.get("disclaimer") or (
        "本报告由 AI 基于公开财务数据自动生成，数据来源为 Wind 金融终端，仅供研究参考，"
        "不构成任何投资建议或买卖要约。财务数据以公司正式披露的定期报告为准，"
        "历史业绩不代表未来表现，估值分位仅为统计描述，不预示股价走势。投资有风险，决策请独立判断。")
    parts.append(f"""<div class="footer">
  <b style="color:#5F6875">数据说明与免责声明</b><br>{esc(disc)}
</div>""")

    parts.append("</div></body></html>")
    html_out = "".join(parts)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", help="data.json 路径")
    ap.add_argument("-o", "--out", default="", help="输出 html 路径")
    args = ap.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = args.out
    if not out:
        base = os.path.splitext(os.path.basename(args.data))[0]
        out = os.path.join(os.path.dirname(os.path.abspath(args.data)), f"{base}.html")
    build(data, out)
    print(f"OK -> {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
