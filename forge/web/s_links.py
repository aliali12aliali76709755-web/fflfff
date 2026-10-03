"""صفحة الروابط لبوت الأزرار: كل زر بطاقة، والزر الذي محتواه رابط يفتحه مباشرة."""
from __future__ import annotations

import re

from ..templates.buttons import KEY
from . import kit
from .render import e

_URL = re.compile(r"^(https?://\S+|tg://\S+)$")


async def render(site):
    t, lite = site.t, site.lite()
    tree = await lite.kv(KEY, []) or []
    home = await lite.kv("buttons:home") or ""
    nodes = []
    for n in tree if isinstance(tree, list) else []:
        if not isinstance(n, dict):
            continue
        text = str(n.get("text") or "")
        url = kit.plain(text)
        nodes.append({"id": kit.as_int(n.get("id")), "p": kit.as_int(n.get("p")), "t": str(n.get("t", "")), "html": kit.rich(text), "media": bool(n.get("src")),
                      "url": url if _URL.match(url) and not url.lower().startswith("javascript") else ""})
    body = f'''
<section class="hero" style="padding-top:40px"><div class="avatar lg"><span>{site.tpl.emoji}</span><img src="{site.root}/avatar" alt="" onerror="this.remove()"></div>
<h1>{e(site.title)}</h1><div class="prose rich muted" style="max-width:46ch">{kit.rich(home) if home else e(site.cfg.get("tagline") or t("اختر ما تريد من الأسفل.", "Pick what you need below."))}</div></section>
<div id="crumb" class="row mt" hidden><button class="btn sm" id="up">{e(t("→ رجوع", "← Back"))}</button><h2 id="title" class="grow"></h2></div>
<section class="card mt prose rich" id="content" hidden></section>
<section class="links mt2" id="links"></section>
<div class="empty" id="none" hidden><div class="big">🕊</div>{e(t("لا توجد أزرار بعد.", "No buttons yet."))}</div>
<div class="mt2">{kit.open_bot_btn(site, "", "btn soft block")}</div>
'''
    return await kit.shell(site, body, scripts=("links.js",), data={"nodes": nodes})


API: dict = {}
