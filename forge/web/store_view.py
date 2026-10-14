"""صفحة التطبيق المصغّر الجديد (v2): غلاف HTML خفيف، والواجهة كلها في static/store2*.js (Vue محلي بلا CDN)."""
from __future__ import annotations

import time

from aiohttp import web

_VER = str(int(time.time()))

SHELL = """<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>المتجر</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/store2.css?v=__V__">
</head><body>
<div id="app"></div>
<script src="/static/vue.min.js"></script>
<script src="/static/store2.js?v=__V__"></script>
<script src="/static/store2_dash.js?v=__V__"></script>
</body></html>""".replace("__V__", _VER)


async def render(req: web.Request) -> web.Response:
    return web.Response(text=SHELL, headers={
        "Content-Type": "text/html; charset=utf-8", "X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-eval' https://telegram.org; "
                                   "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com data:; "
                                   "img-src 'self' https: data: blob:; connect-src 'self'; frame-ancestors *;",
    })
