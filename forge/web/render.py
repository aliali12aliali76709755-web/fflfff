"""بناء صفحات HTML: القالب العام، الرأس، صفحات الحالة، ورسوم SVG بسيطة."""
from __future__ import annotations

import html
import json
import math

from aiohttp import web

from .. import config

VERSION = "8"
FONTS = "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap"
FONTS_QURAN = "https://fonts.googleapis.com/css2?family=Amiri+Quran&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap"


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def js(data) -> str:
    """JSON آمن للتضمين داخل <script>."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def page(title: str, body: str, *, lang: str = "ar", accent: str = "", desc: str = "", site: dict | None = None, scripts: tuple = (),
         quran: bool = False, tg: bool = True, noindex: bool = False, status: int = 200, frame_tg: bool = False) -> web.Response:
    rtl = lang == "ar"
    style = f' style="--accent:{e(accent)}"' if accent else ""
    head = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(desc[:200])}">' if desc else "",
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc[:200])}">' if desc else "",
        '<meta name="robots" content="noindex">' if noindex else "",
        f'<meta name="theme-color" content="{e(accent or "#2563eb")}">',
        "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E⚡%3C/text%3E%3C/svg%3E\">",
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        f'<link rel="stylesheet" href="{FONTS_QURAN if quran else FONTS}">',
        f'<link rel="stylesheet" href="/static/app.css?v={VERSION}">',
    ]
    tail = [f"<script>window.SITE={js(site or {})};</script>"]
    if tg:
        tail.append('<script src="https://telegram.org/js/telegram-web-app.js"></script>')
    tail.append(f'<script src="/static/app.js?v={VERSION}"></script>')
    tail += [f'<script src="/static/{s}?v={VERSION}"></script>' for s in scripts]
    doc = (f'<!doctype html><html lang="{lang}" dir="{"rtl" if rtl else "ltr"}"{style}><head>' + "".join(h for h in head if h) +
           f"</head><body>{body}" + "".join(tail) + "</body></html>")
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
    if frame_tg:      # لوحات التحكم: لا تُعرض داخل إطار إلا في تيليجرام ويب
        headers["Content-Security-Policy"] = "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"
    return web.Response(text=doc, content_type="text/html", charset="utf-8", status=status, headers=headers)


def status_page(icon: str, title: str, text: str, *, lang: str = "ar", status: int = 200, action: str = "", accent: str = "") -> web.Response:
    body = (f'<main class="wrap"><div class="empty" style="padding-top:22vh"><div class="big">{icon}</div>'
            f'<h1>{e(title)}</h1><p class="mt">{e(text)}</p>{action}</div></main>')
    return page(title, body, lang=lang, status=status, noindex=True, tg=False, accent=accent)


def brand(lang: str) -> str:
    return config.BRAND if lang == "ar" else config.BRAND_EN


# ───────────────────────── رسوم ─────────────────────────
def line_chart(values: list[float], labels: list[str], *, height: int = 170, bars: bool = False) -> str:
    """رسم خطي أو أعمدة بصيغة SVG يتبع ألوان الصفحة."""
    w, h, pl, pr, pt, pb = 440, height, 30, 8, 10, 22
    n = len(values)
    top = max(max(values, default=0), 1)
    raw = top / 4
    mag = 10 ** math.floor(math.log10(raw)) if raw >= 1 else 1
    step = max(1, int(next(m * mag for m in (1, 2, 5, 10) if raw <= m * mag)))
    top = math.ceil(top / step) * step
    iw, ih = w - pl - pr, h - pt - pb

    def x(i: int) -> float:
        return pl + (iw * (i + 0.5) / n if bars else (iw * i / max(1, n - 1)))

    def y(v: float) -> float:
        return pt + ih * (1 - v / top)

    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="chart">']
    v = 0
    while v <= top:
        out.append(f'<line class="ax" x1="{pl}" x2="{w - pr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/><text x="{pl - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v:g}</text>')
        v += step
    if bars:
        bw = min(34.0, iw / n * 0.62)
        for i, val in enumerate(values):
            out.append(f'<rect class="br" x="{x(i) - bw / 2:.1f}" y="{y(val):.1f}" width="{bw:.1f}" height="{max(0.0, pt + ih - y(val)):.1f}" rx="4"><title>{e(labels[i])}: {val:g}</title></rect>')
    elif n:
        pts = " ".join(f"{x(i):.1f},{y(val):.1f}" for i, val in enumerate(values))
        out.append(f'<polygon class="ar" points="{pl},{pt + ih} {pts} {x(n - 1):.1f},{pt + ih}"/><polyline class="ln" points="{pts}"/>')
        for i, val in enumerate(values):
            out.append(f'<circle cx="{x(i):.1f}" cy="{y(val):.1f}" r="9" fill="transparent"><title>{e(labels[i])}: {val:g}</title></circle>')
    every = max(1, (n + 6) // 7)
    for i, lab in enumerate(labels):
        if i % every == 0 or i == n - 1:
            out.append(f'<text x="{x(i):.1f}" y="{h - 6}" text-anchor="middle">{e(lab)}</text>')
    out.append("</svg>")
    return "".join(out)
