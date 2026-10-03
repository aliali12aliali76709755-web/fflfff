"""لوحات الويب (للقراءة فقط): لوحة مدير المنصة، ولوحة كل صانع بوتات.

الدخول برابط موقّع قصير العمر يصدره البوت لصاحبه، ثم جلسة في ملف تعريف ارتباط. لا تعرض اللوحات أي توكن.
"""
from __future__ import annotations

import datetime as dt
from urllib.parse import urlparse

from aiohttp import web
from sqlalchemy import func, select

from .. import config, db, errors, templates
from .. import plat as platform
from . import render, sign, site_url
from .render import e

COOKIE = {"admin": "bf_admin", "me": "bf_me"}
LOGIN_TTL, SESSION_TTL = 900, 12 * 3600


def login_link(kind: str, uid: int, fid: int = 0) -> str:
    """رابط دخول يعمل 15 دقيقة، يصدره البوت للمدير أو لصانع البوتات."""
    root = config.PUBLIC_URL or f"http://localhost:{config.WEB_PORT}"
    return f"{root}/{'admin' if kind == 'admin' else 'me'}?t={sign.session(kind, uid, LOGIN_TTL, f=fid)}"


def _session(req: web.Request, kind: str):
    """يعيد (الجلسة، ردّ إعادة توجيه يضبط ملف الارتباط) — أحدهما None."""
    tok = req.query.get("t")
    if tok:
        d = sign.check_session(tok, kind)
        if d is None:
            return None, None
        resp = web.HTTPFound(req.path)
        _set_session(req, resp, kind, d["u"], d.get("f", 0))
        return None, resp
    return sign.check_session(req.cookies.get(COOKIE[kind], ""), kind), None


def _secure(req: web.Request) -> bool:
    """ملف الارتباط Secure حين يصل الزائر عبر https: مباشرة، أو عبر الرابط العام خلف وسيط."""
    if req.scheme == "https":
        return True
    pub = urlparse(config.PUBLIC_URL)
    return pub.scheme == "https" and (req.host or "").split(":")[0].lower() == (pub.hostname or "").lower()


def _set_session(req: web.Request, resp, kind: str, uid: int, fid: int = 0) -> None:
    """جلسة 12 ساعة في ملف ارتباط. مع https نستخدم SameSite=None لتعمل اللوحة أيضاً داخل تيليجرام ويب (إطار)."""
    secure = _secure(req)
    resp.set_cookie(COOKIE[kind], sign.session(kind, uid, SESSION_TTL, f=fid), max_age=SESSION_TTL, httponly=True,
                    samesite="None" if secure else "Lax", secure=secure, path="/")


def _denied(lang: str = "ar") -> web.Response:
    return render.status_page("🔐", "انتهت الجلسة", "افتح اللوحة من جديد من بوت الصانع: زر القائمة بجانب خانة الكتابة، أو «🖥 لوحتي على الويب».", status=403)


# ───────────────────────── الدخول من داخل تيليجرام ─────────────────────────
async def app_entry(req: web.Request) -> web.Response:
    """يفتحها زر القائمة في بوت الصانع: تتحقق من هوية تيليجرام ثم تنتقل إلى «لوحتي»."""
    body = ('<main class="wrap"><div class="empty" style="padding-top:26vh" id="msg"><div class="big">📊</div><p>جارٍ فتح لوحتك…</p></div></main>'
            "<script>(function(){var tg=window.Telegram&&window.Telegram.WebApp,m=document.getElementById('msg');"
            "function fail(t){m.innerHTML='<div class=\"big\">🔐</div><p>'+t+'</p>';}"
            "if(!tg||!tg.initData){fail('افتح هذه الصفحة من داخل تيليجرام: زر القائمة بجانب خانة الكتابة في بوت الصانع.');return;}"
            "try{tg.ready();tg.expand();}catch(e){}"
            "fetch('/auth',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({initData:tg.initData})})"
            ".then(function(r){return r.json();}).then(function(r){if(r.ok){location.replace(r.to);}else{fail('تعذّر التحقق من حسابك. أغلق الصفحة وافتحها من جديد.');}})"
            ".catch(function(){fail('تعذّر الاتصال. حاول مرة أخرى.');});})();</script>")
    return render.page(render.brand("ar"), body, noindex=True, frame_tg=True)


async def auth(req: web.Request) -> web.Response:
    try:
        data = await req.json()
    except Exception:  # noqa: BLE001
        data = None
    user = sign.check_init_data(str(data.get("initData", "")), config.MAKER_TOKEN) if isinstance(data, dict) else None
    if not user:
        return web.json_response({"ok": False}, status=403)
    uid = int(user["id"])
    resp = web.json_response({"ok": True, "to": "/me"})
    _set_session(req, resp, "me", uid, 0)
    if config.ADMIN_ID and uid == config.ADMIN_ID:
        _set_session(req, resp, "admin", uid, 0)
    return resp


async def _series(ids: list[int], days: int) -> tuple[list[str], dict[str, list[int]]]:
    """عدادات يومية مجمّعة لعدة بوتات، الأقدم أولاً."""
    today = db.now().date()
    labels = [(today - dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    out = {k: [0] * days for k in ("new", "msgs", "web", "starts", "promo")}
    if ids:
        async with db.Session() as s:
            rows = (await s.execute(select(db.Daily).where(db.Daily.bot_id.in_(ids), db.Daily.day >= labels[0]))).scalars().all()
        pos = {d: i for i, d in enumerate(labels)}
        for r in rows:
            i = pos.get(r.day)
            if i is None:
                continue
            for k in out:
                out[k][i] += int((r.data or {}).get(k, 0))
    return [d[5:] for d in labels], out


async def _created(model, col, cond: list, days: int) -> list[int]:
    start = dt.datetime.combine(db.now().date() - dt.timedelta(days=days - 1), dt.time())
    async with db.Session() as s:
        rows = (await s.execute(select(col).where(*cond, col >= start))).scalars().all()
    out = [0] * days
    for c in rows:
        i = (c.date() - start.date()).days
        if 0 <= i < days:
            out[i] += 1
    return out


def _kpi(value, label: str, delta: str = "") -> str:
    v = f"{value:,}" if isinstance(value, int) else e(value)
    return f'<div class="kpi"><div class="v">{v}</div><div class="l">{e(label)}</div>' + (f'<div class="d">{e(delta)}</div>' if delta else "") + "</div>"


def _chart(title: str, values: list, labels: list, total: str = "", bars: bool = False) -> str:
    return (f'<section class="card"><div class="row between"><h3>{e(title)}</h3><span class="muted small">{e(total)}</span></div>'
            f'<div class="mt">{render.line_chart(values, labels, bars=bars)}</div></section>')


def _status(b: db.Bot) -> str:
    lk = platform.lock_of(platform.peek(b.id))
    if lk is not None:
        return '<span class="badge warn">' + {"closed": "🔒 مغلق", "temp": "⏳ مغلق مؤقتاً", "maint": "🛠 صيانة"}.get(lk["mode"], "🔒") + "</span>"
    return {"active": '<span class="badge ok">يعمل</span>', "disabled": '<span class="badge off">متوقف</span>'}.get(b.status, '<span class="badge warn">يحتاج انتباه</span>')


def _shell(title: str, body: str, brand: str, actions: str = "") -> web.Response:
    html = (f'<header class="top"><div class="in wide"><div class="avatar"><span>📊</span></div><div class="grow"><div class="brand">{e(title)}</div>'
            f'<div class="small muted">{e(brand)}</div></div>{actions}<a class="btn sm only-web" href="/logout">خروج</a></div></header><main class="wrap wide">{body}</main>'
            f'<footer class="footer">لوحة للقراءة فقط · الإجراءات تتم من البوت</footer>')
    return render.page(title, html, noindex=True, frame_tg=True)


async def _users_by_bot(ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    async with db.Session() as s:
        return dict((await s.execute(select(db.BUser.bot_id, func.count()).where(db.BUser.bot_id.in_(ids)).group_by(db.BUser.bot_id))).all())


async def _today_new(ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    async with db.Session() as s:
        rows = (await s.execute(select(db.Daily).where(db.Daily.bot_id.in_(ids), db.Daily.day == db.today()))).scalars().all()
    return {r.bot_id: int((r.data or {}).get("new", 0)) for r in rows}


def _bots_table(bots: list[db.Bot], users: dict, new: dict, owners: dict | None, maker: str, admin: bool) -> str:
    head = "<tr><th>البوت</th><th>النوع</th>" + ("<th>الصانع</th>" if owners is not None else "") + "<th>الأعضاء</th><th>جدد اليوم</th><th>الحالة</th><th></th></tr>"
    rows = []
    for b in bots:
        tpl = templates.get(b.template)
        link = f"https://t.me/{maker}?start={'adm' if admin else 'bot'}_{b.id}" if maker else "#"
        own = ""
        if owners is not None:
            o = owners.get(b.owner_id)
            own = f"<td>{e(o.name if o else b.owner_id)}</td>"
        rows.append(f'<tr><td><a href="{e(site_url(b.username))}" target="_blank" rel="noopener" dir="ltr">@{e(b.username)}</a>' + (" ✔" if platform.peek(b.id).get("verified") else "")
                    + f"</td><td>{tpl.emoji} {e(tpl.ar)}</td>{own}<td>{users.get(b.id, 0):,}</td><td>+{new.get(b.id, 0)}</td><td>{_status(b)}</td>"
                    f'<td><a class="btn sm" href="{e(link)}" target="_blank" rel="noopener">إدارة</a></td></tr>')
    if not rows:
        return '<div class="empty">لا توجد بوتات بعد.</div>'
    return f'<div class="scroll-x"><table><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


# ───────────────────────── لوحة المدير ─────────────────────────
async def admin(req: web.Request) -> web.Response:
    sess, redirect = _session(req, "admin")
    if redirect is not None:
        raise redirect
    if sess is None or not config.ADMIN_ID or sess["u"] != config.ADMIN_ID:
        return _denied()
    from .server import MGR
    mgr = req.app[MGR]
    day0 = dt.datetime.combine(db.now().date(), dt.time())
    async with db.Session() as s:
        async def cnt(model, *cond):
            return int((await s.execute(select(func.count()).select_from(model).where(*cond))).scalar() or 0)
        users, users_today = await cnt(db.MUser, db.MUser.factory_id == 0), await cnt(db.MUser, db.MUser.factory_id == 0, db.MUser.created >= day0)
        bots = list((await s.execute(select(db.Bot).order_by(db.Bot.created.desc()))).scalars().all())
        members, members_today = await cnt(db.BUser), await cnt(db.BUser, db.BUser.joined >= day0)
        reports = await cnt(db.Report, db.Report.factory_id == 0)
        owners = {u.user_id: u for u in (await s.execute(select(db.MUser).where(db.MUser.factory_id == 0))).scalars().all()}
    ids = [b.id for b in bots]
    labels, ser = await _series(ids, 30)
    u_ser = await _created(db.MUser, db.MUser.created, [db.MUser.factory_id == 0], 30)
    b_ser = await _created(db.Bot, db.Bot.created, [], 30)
    bots_today = b_ser[-1]
    locked = sum(1 for i in ids if platform.lock_of(platform.peek(i)) is not None)
    running = sum(1 for i in ids if mgr.running(i))
    by_users = await _users_by_bot(ids)
    new = await _today_new(ids)
    top = sorted(bots, key=lambda b: -by_users.get(b.id, 0))[:15]
    usage: dict[str, int] = {}
    for b in bots:
        usage[b.template] = usage.get(b.template, 0) + 1
    types = "".join(f"<tr><td>{templates.get(k).emoji} {e(templates.get(k).ar)}</td><td>{v}</td><td>{sum(by_users.get(b.id, 0) for b in bots if b.template == k):,}</td></tr>"
                    for k, v in sorted(usage.items(), key=lambda x: -x[1])[:12])
    log = (await db.kv_get(0, "sys:audit", []) or [])[::-1][:10]
    from ..admin import ACTS
    audit = "".join(f"<tr><td dir='ltr'>{e(_when(x['at']))}</td><td>{e(ACTS.get(x['act'], x['act']))}</td><td dir='ltr'>{e(x.get('bot', ''))}</td><td>{e(x.get('info', ''))}</td></tr>" for x in log)
    errs = "".join(f"<tr><td dir='ltr'>{e(x['at'])}</td><td>{e(x['where'])}</td><td dir='ltr'>{e(x['err'][:90])}</td></tr>" for x in list(errors.RECENT)[:6])
    maker = mgr.maker.bot.username if mgr.maker is not None else ""
    body = (
        '<section class="kpis mt">' + _kpi(users, "مستخدمو الصانع", f"+{users_today} اليوم") + _kpi(len(bots), "البوتات", f"+{bots_today} اليوم") +
        _kpi(members, "أعضاء كل البوتات", f"+{members_today} اليوم") + _kpi(ser["msgs"][-1], "رسائل اليوم") + _kpi(running, "تعمل الآن") +
        _kpi(locked, "مغلقة من الإدارة") + _kpi(ser["web"][-1], "زيارات المواقع اليوم") + _kpi(reports, "البلاغات") + "</section>"
        '<div class="grid two mt" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">' +
        _chart("مستخدمون جدد للصانع — 30 يوماً", u_ser, labels, f"المجموع {sum(u_ser):,}") + _chart("بوتات جديدة — 30 يوماً", b_ser, labels, f"المجموع {sum(b_ser):,}", bars=True) +
        _chart("أعضاء جدد في كل البوتات", ser["new"], labels, f"المجموع {sum(ser['new']):,}") + _chart("الرسائل اليومية", ser["msgs"], labels, f"المجموع {sum(ser['msgs']):,}") +
        _chart("زيارات مواقع البوتات", ser["web"], labels, f"المجموع {sum(ser['web']):,}", bars=True) + _chart("رسائل الترويج المرسلة", ser["promo"], labels, f"المجموع {sum(ser['promo']):,}", bars=True) + "</div>"
        '<div class="sec-title"><h2>أكبر البوتات</h2><span class="muted small">زر «إدارة» يفتح بطاقة البوت في لوحة الإدارة داخل تيليجرام</span></div><section class="card pad0">' +
        _bots_table(top, by_users, new, owners, maker, True) + "</section>"
        '<div class="grid two mt2" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">'
        f'<section class="card pad0"><div style="padding:14px 16px 0"><h3>الأنواع الأكثر استخداماً</h3></div><div class="scroll-x"><table><thead><tr><th>النوع</th><th>البوتات</th><th>الأعضاء</th></tr></thead><tbody>{types}</tbody></table></div></section>'
        f'<section class="card pad0"><div style="padding:14px 16px 0"><h3>آخر إجراءات الإدارة</h3></div>' +
        (f'<div class="scroll-x"><table><tbody>{audit}</tbody></table></div>' if audit else '<div class="empty">لا توجد إجراءات مسجلة بعد.</div>') + "</section></div>" +
        (f'<div class="sec-title"><h2>آخر الأخطاء التقنية</h2></div><section class="card pad0"><div class="scroll-x"><table><tbody>{errs}</tbody></table></div></section>' if errs else ""))
    return _shell("لوحة الإدارة", body, render.brand("ar"), '<a class="btn sm" href="/me">📊 لوحتي</a>')


def _when(ts) -> str:
    from .. import ui
    return ui.when(ts, "%m-%d %H:%M")


# ───────────────────────── لوحة صانع البوتات ─────────────────────────
async def me(req: web.Request) -> web.Response:
    sess, redirect = _session(req, "me")
    if redirect is not None:
        raise redirect
    if sess is None:
        return _denied()
    from .server import MGR
    mgr = req.app[MGR]
    uid, fid = int(sess["u"]), int(sess.get("f", 0))
    async with db.Session() as s:
        bots = list((await s.execute(select(db.Bot).where(db.Bot.factory_id == fid, db.Bot.owner_id == uid).order_by(db.Bot.created.desc()))).scalars().all())
        user = await s.get(db.MUser, (fid, uid))
    ids = [b.id for b in bots]
    labels, ser = await _series(ids, 30)
    by_users = await _users_by_bot(ids)
    new = await _today_new(ids)
    pending = {}
    for b in bots:
        tpl = templates.get(b.template)
        if tpl.key in ("store", "qrmenu"):
            pending[b.id] = ("طلبات جديدة", await db.rec_count(b.id, f"{tpl.key}:order", status="new"))
        elif tpl.key == "booking":
            pending[b.id] = ("حجوزات تنتظر", await db.rec_count(b.id, "book", status="new"))
    app = mgr.maker if fid == 0 else mgr.apps.get(fid)
    maker = app.bot.username if app is not None else ""
    waiting = "".join(f'<div class="item"><span class="grow"><b dir="ltr">@{e(b.username)}</b><span class="muted small" style="display:block">{e(pending[b.id][0])}</span></span>'
                      f'<span class="badge warn">{pending[b.id][1]}</span><a class="btn sm" href="https://t.me/{e(b.username)}?start=panel" target="_blank" rel="noopener">افتح</a></div>'
                      for b in bots if pending.get(b.id, ("", 0))[1])
    body = (
        '<section class="kpis mt">' + _kpi(len(bots), "بوتاتك") + _kpi(sum(by_users.values()), "كل الأعضاء", f"+{ser['new'][-1]} اليوم") +
        _kpi(ser["msgs"][-1], "رسائل اليوم") + _kpi(ser["web"][-1], "زيارات مواقعك اليوم") + "</section>" +
        (f'<div class="sec-title"><h2>بانتظارك الآن</h2></div><section class="card pad0"><div class="list">{waiting}</div></section>' if waiting else "") +
        '<div class="grid two mt2" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">' +
        _chart("أعضاء جدد — 30 يوماً", ser["new"], labels, f"المجموع {sum(ser['new']):,}") + _chart("الرسائل اليومية", ser["msgs"], labels, f"المجموع {sum(ser['msgs']):,}") +
        _chart("زيارات مواقع بوتاتك", ser["web"], labels, f"المجموع {sum(ser['web']):,}", bars=True) + _chart("مرات تشغيل البوتات", ser["starts"], labels, f"المجموع {sum(ser['starts']):,}", bars=True) + "</div>"
        '<div class="sec-title"><h2>بوتاتك</h2><span class="muted small">اسم البوت يفتح موقعه، و«إدارة» تفتح بطاقته في الصانع</span></div><section class="card pad0">' +
        _bots_table(bots, by_users, new, None, maker, False) + "</section>")
    is_admin = bool(config.ADMIN_ID) and uid == config.ADMIN_ID and fid == 0 and sign.check_session(req.cookies.get(COOKIE["admin"], ""), "admin") is not None
    return _shell("لوحتي", body, (user.name if user else "") or render.brand("ar"), '<a class="btn sm primary" href="/admin">👑 الإدارة</a>' if is_admin else "")


async def logout(_req: web.Request) -> web.Response:
    resp = web.HTTPFound("/")
    for c in COOKIE.values():
        resp.del_cookie(c, path="/")
    raise resp


def routes(app: web.Application) -> None:
    app.router.add_get("/admin", admin)
    app.router.add_get("/me", me)
    app.router.add_get("/logout", logout)
    app.router.add_get("/app", app_entry)
    app.router.add_post("/auth", auth)
