"""اختبارات شاملة للتحقق من واجهات برمجة التطبيقات والأمان لـ Telegram Mini Apps."""
import asyncio
import datetime as dt
import hashlib
import hmac
import io
import json
import time
from urllib.parse import urlencode
import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, TestClient, TestServer
from PIL import Image

from forge import config, crypto, db
from forge.modules import currency, ledger
from forge.web import media_pipe, miniapp_api, miniapp_auth, server


def make_init_data(token: str, user: dict, auth_date: int = None) -> str:
    if auth_date is None:
        auth_date = int(time.time())
    pairs = {
        "auth_date": str(auth_date),
        "query_id": "AAHd_test",
        "user": json.dumps(user, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


@pytest.mark.anyio
async def test_theme_validation_and_sanitization():
    """التحقق من أن محرر التصميم يمنع كود XSS وأي حقول غير مصرح بها."""
    malicious = {
        "store_name": "<script>alert(1)</script>متجر الأبطال",
        "primary_color": "javascript:eval()",
        "font_family": "EvilFont",
        "border_radius": "rounded-9999",
        "layout_density": "super_dense",
        "extra_field": "hacked",
        "banners": ["https://banner1.jpg"],
        "show_reviews": True,
    }
    clean = miniapp_api.validate_theme_config(malicious)

    assert "<script" not in clean.get("store_name", "")
    assert "javascript:" not in clean.get("primary_color", "")
    assert clean.get("font_family") == "Cairo"  # Fallback to allowed
    assert clean.get("border_radius") == "rounded-xl"  # Fallback to allowed
    assert clean.get("layout_density") == "comfortable"  # Fallback to allowed
    assert "extra_field" not in clean  # Strict schema enforcement


@pytest.mark.anyio
async def test_media_pipeline_security():
    """التحقق من فحص Magic Bytes ورفض الملفات غير الصالحة وضغط الصور إلى WebP."""
    # 1. رفض ملف نصي خبيث
    fake_txt = b"Hello, I am a malicious file pretending to be image"
    with pytest.raises(ValueError, match="غير مدعوم"):
        media_pipe.handle_uploaded_file(fake_txt, "evil.png")

    # 2. صورة حقيقية صالحة PNG مع EXIF
    img = Image.new("RGB", (200, 200), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_png = buf.getvalue()

    result = media_pipe.handle_uploaded_file(raw_png, "avatar.png")
    assert result["type"] == "image"
    assert result["ext"] == "webp"
    assert "/media/" in result["url"]
    assert "/media/" in result["thumb_url"]


@pytest.mark.anyio
async def test_miniapp_full_api_cycle():
    """دورة كاملة للمصادقة، الكتالوج، الطلبات، ومنع التكرار، والتقييمات."""
    await db.init()

    # 1. إنشاء تطبيق aiohttp ومسارات Mini App
    app = web.Application()
    miniapp_api.setup_routes(app)

    # 2. إنشاء بيانات البوت التجاري والمستخدمين في قاعدة البيانات
    test_seed = int(time.time() * 1000) % 800000 + 200000
    seller_uid = test_seed + 1
    buyer_uid = test_seed + 2
    raw_token = f"{test_seed}:AAHkL_test_token_secret_123"
    enc_token = crypto.enc(raw_token)
    bot_username = f"bot_shop_{test_seed}"

    async with db.Session() as s:
        test_bot = db.Bot(
            id=test_seed,
            owner_id=seller_uid,
            username=bot_username,
            name="متجر الاختبار الرقمي",
            token=enc_token,
            template="digital",
            status="active",
        )
        s.add(test_bot)
        await s.commit()

    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        # إعداد initData
        buyer_init = make_init_data(raw_token, {"id": buyer_uid, "first_name": "Sami Buyer", "username": "sami"})
        seller_init = make_init_data(raw_token, {"id": seller_uid, "first_name": "Abu Seller", "username": "seller"})
        fake_init = make_init_data("wrong_token", {"id": buyer_uid, "first_name": "Hacker"})
        expired_init = make_init_data(raw_token, {"id": buyer_uid, "first_name": "Expired"}, auth_date=int(time.time()) - 100000)

        # 3. اختبار المصادقة: توقيع غير صالح أو منتهي
        r_fail1 = await client.get(f"/api/miniapp/{bot_username}/bootstrap", headers={"X-Telegram-Init-Data": fake_init})
        assert r_fail1.status == 401

        r_fail2 = await client.get(f"/api/miniapp/{bot_username}/bootstrap", headers={"X-Telegram-Init-Data": expired_init})
        assert r_fail2.status == 401

        # 4. اختبار البوت غير الموجود
        r_notfound = await client.get("/api/miniapp/non_existent_bot/bootstrap", headers={"X-Telegram-Init-Data": buyer_init})
        assert r_notfound.status == 404

        # 5. اختبار Bootstrap لمشتري صحيح
        r_boot = await client.get(f"/api/miniapp/{bot_username}/bootstrap", headers={"X-Telegram-Init-Data": buyer_init})
        assert r_boot.status == 200
        boot_data = await r_boot.json()
        assert boot_data["ok"] is True
        assert boot_data["bot"]["template"] == "digital"
        assert boot_data["user"]["role"] == "buyer"
        assert boot_data["user"]["balance_usd"] == 0.0

        # 6. اختبار فصل الصلاحيات: المشتري لا يمكنه دخول لوحة البائع
        r_forbid = await client.get(f"/api/miniapp/{bot_username}/seller/stats", headers={"X-Telegram-Init-Data": buyer_init})
        assert r_forbid.status == 403

        # بينما البائع يستطيع الدخول
        r_seller_stats = await client.get(f"/api/miniapp/{bot_username}/seller/stats", headers={"X-Telegram-Init-Data": seller_init})
        assert r_seller_stats.status == 200
        stats_data = await r_seller_stats.json()
        assert stats_data["ok"] is True
        assert "total_orders" in stats_data

        # 7. اختبار جلب الكتالوج
        r_cat = await client.get(f"/api/miniapp/{bot_username}/catalog", headers={"X-Telegram-Init-Data": buyer_init})
        assert r_cat.status == 200
        cat_data = await r_cat.json()
        assert cat_data["ok"] is True
        assert len(cat_data["products"]) > 0
        product_item = cat_data["products"][0]
        prod_id = product_item["id"]

        # 8. اختبار إنشاء طلب برصيد صفر (يجب أن يفشل بـ 402 Insufficient Balance)
        r_ord_nobal = await client.post(
            f"/api/miniapp/{bot_username}/order",
            headers={"X-Telegram-Init-Data": buyer_init},
            json={"product_id": prod_id, "target": "999888"},
        )
        assert r_ord_nobal.status == 402
        err_nobal = await r_ord_nobal.json()
        assert err_nobal["error"] == "insufficient_balance"

        # 9. شحن رصيد للمشتري ($50) وإعادة المحاولة
        await ledger.credit_user(test_seed, buyer_uid, 50.0, "test_deposit")
        cur_bal = await ledger.get_user_balance_usd(test_seed, buyer_uid)
        assert cur_bal == 50.0

        idemp_key = f"ord_idemp_{test_seed}"
        r_ord_ok = await client.post(
            f"/api/miniapp/{bot_username}/order",
            headers={"X-Telegram-Init-Data": buyer_init},
            json={"product_id": prod_id, "target": "999888", "idempotency_key": idemp_key},
        )
        assert r_ord_ok.status == 200
        ord_res = await r_ord_ok.json()
        assert ord_res["ok"] is True
        assert ord_res["order_id"] == idemp_key
        bal_after_ord = ord_res["new_balance_usd"]
        assert bal_after_ord < 50.0

        # 10. اختبار منع التكرار (Idempotency Key): الضغط مرتين على الشراء
        r_ord_dup = await client.post(
            f"/api/miniapp/{bot_username}/order",
            headers={"X-Telegram-Init-Data": buyer_init},
            json={"product_id": prod_id, "target": "999888", "idempotency_key": idemp_key},
        )
        assert r_ord_dup.status == 200
        dup_res = await r_ord_dup.json()
        assert dup_res.get("is_duplicate") is True
        # التأكد من عدم الخصم المزدوج
        bal_check = await ledger.get_user_balance_usd(test_seed, buyer_uid)
        assert bal_check == bal_after_ord

        # 11. اختبار التقييمات الموثقة: لا يمكن تقييم طلب معلق (queued)
        r_rev_early = await client.post(
            f"/api/miniapp/{bot_username}/reviews",
            headers={"X-Telegram-Init-Data": buyer_init},
            json={"order_id": idemp_key, "rating": 5, "comment": "ممتاز وسريع جداً"},
        )
        assert r_rev_early.status == 400
        assert (await r_rev_early.json())["error"] == "order_not_completed"

        # تغيير حالة الطلب إلى مكتمل (completed)
        async with db.Session() as s:
            o_row = (await s.execute(db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == idemp_key))).scalars().first()
            o_row.status = "completed"
            await s.commit()

        # الآن التقييم يجب أن ينجح
        r_rev_ok = await client.post(
            f"/api/miniapp/{bot_username}/reviews",
            headers={"X-Telegram-Init-Data": buyer_init},
            json={"order_id": idemp_key, "rating": 5, "comment": "ممتاز وسريع جداً"},
        )
        assert r_rev_ok.status == 200
        assert (await r_rev_ok.json())["ok"] is True

        # محاولة تقييم نفس الطلب مرة أخرى (يجب أن ترفض 409 Conflict)
        r_rev_dup = await client.post(
            f"/api/miniapp/{bot_username}/reviews",
            headers={"X-Telegram-Init-Data": buyer_init},
            json={"order_id": idemp_key, "rating": 5, "comment": "تقييم مكرر"},
        )
        assert r_rev_dup.status == 409
        assert (await r_rev_dup.json())["error"] == "already_reviewed"

        # قراءة التقييمات للمنتج
        r_get_revs = await client.get(
            f"/api/miniapp/{bot_username}/reviews/{prod_id}",
            headers={"X-Telegram-Init-Data": buyer_init},
        )
        assert r_get_revs.status == 200
        revs_list = await r_get_revs.json()
        assert revs_list["total"] >= 1
        assert revs_list["reviews"][0]["is_verified"] is True
        assert revs_list["reviews"][0]["rating"] == 5

        # 12. اختبار حفظ الثيم للبائع مع سجل النسخ
        new_theme = {
            "primary_color": "#10b981",
            "font_family": "Tajawal",
            "border_radius": "rounded-2xl",
        }
        r_save_th = await client.post(
            f"/api/miniapp/{bot_username}/seller/theme",
            headers={"X-Telegram-Init-Data": seller_init},
            json=new_theme,
        )
        assert r_save_th.status == 200
        th_res = await r_save_th.json()
        assert th_res["ok"] is True
        assert th_res["theme"]["primary_color"] == "#10b981"
        assert th_res["version"] >= 1

        # جلب سجل النسخ
        r_vers = await client.get(
            f"/api/miniapp/{bot_username}/seller/theme/versions",
            headers={"X-Telegram-Init-Data": seller_init},
        )
        assert r_vers.status == 200
        vers_res = await r_vers.json()
        assert len(vers_res["versions"]) >= 1

        # 13. اختبار المساعد الذكي AI Customizer
        r_ai = await client.post(
            f"/api/miniapp/{bot_username}/seller/ai_customizer",
            headers={"X-Telegram-Init-Data": seller_init},
            json={"prompt": "أريد ثيم فخم ذهبي وأسود"},
        )
        assert r_ai.status == 200
        ai_res = await r_ai.json()
        assert ai_res["ok"] is True
        assert ai_res["suggested_theme"]["primary_color"] == "#d97706"

    finally:
        await client.close()


@pytest.mark.anyio
async def test_templates_catalog_and_orders():
    """اختبار الكتالوج وإنشاء الطلبات للقوالب الثلاثة الأخرى: sms, smm, tgstars."""
    await db.init()
    app = web.Application()
    miniapp_api.setup_routes(app)
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        base_seed = int(time.time() * 1000) % 700000 + 300000
        buyer_uid = base_seed + 99

        # ── 1. قالب أرقام التفعيل (SMS) ──
        sms_token = f"{base_seed}:AAHkL_sms_token_secret"
        sms_u = f"bot_sms_{base_seed}"
        async with db.Session() as s:
            s.add(db.Bot(
                id=base_seed + 1,
                owner_id=base_seed + 10,
                username=sms_u,
                name="متجر الأرقام",
                token=crypto.enc(sms_token),
                template="sms",
                status="active",
            ))
            await s.commit()

        sms_init = make_init_data(sms_token, {"id": buyer_uid, "first_name": "Sami SMS", "username": "smsuser"})
        r_sms_cat = await client.get(f"/api/miniapp/{sms_u}/catalog", headers={"X-Telegram-Init-Data": sms_init})
        assert r_sms_cat.status == 200
        sms_data = await r_sms_cat.json()
        assert len(sms_data["categories"]) > 0
        assert len(sms_data["products"]) > 0

        # شحن رصيد وشراء رقم
        await ledger.credit_user(base_seed + 1, buyer_uid, 10.0, "deposit_sms")
        sms_prod = sms_data["products"][0]
        r_sms_ord = await client.post(
            f"/api/miniapp/{sms_u}/order",
            headers={"X-Telegram-Init-Data": sms_init},
            json={"product_id": sms_prod["id"], "target": ""},
        )
        assert r_sms_ord.status == 200
        sms_ord_res = await r_sms_ord.json()
        assert sms_ord_res["ok"] is True
        assert sms_ord_res["status"] == "queued"

        # ── 2. قالب خدمات التفاعل (SMM) ──
        smm_token = f"{base_seed}:AAHkL_smm_token_secret"
        smm_u = f"bot_smm_{base_seed}"
        async with db.Session() as s:
            s.add(db.Bot(
                id=base_seed + 2,
                owner_id=base_seed + 20,
                username=smm_u,
                name="متجر التفاعل",
                token=crypto.enc(smm_token),
                template="smm",
                status="active",
            ))
            await s.commit()

        smm_init = make_init_data(smm_token, {"id": buyer_uid, "first_name": "Sami SMM", "username": "smmuser"})
        r_smm_cat = await client.get(f"/api/miniapp/{smm_u}/catalog", headers={"X-Telegram-Init-Data": smm_init})
        assert r_smm_cat.status == 200
        smm_data = await r_smm_cat.json()
        assert len(smm_data["categories"]) > 0
        assert len(smm_data["products"]) > 0

        # شحن وشراء متابعين
        await ledger.credit_user(base_seed + 2, buyer_uid, 20.0, "deposit_smm")
        smm_prod = smm_data["products"][0]
        r_smm_ord = await client.post(
            f"/api/miniapp/{smm_u}/order",
            headers={"X-Telegram-Init-Data": smm_init},
            json={"product_id": smm_prod["id"], "quantity": 1000, "target": "https://t.me/test_channel"},
        )
        assert r_smm_ord.status == 200
        smm_ord_res = await r_smm_ord.json()
        assert smm_ord_res["ok"] is True

        # ── 3. قالب النجوم والبريميوم والهدايا (TGStars) ──
        star_token = f"{base_seed}:AAHkL_star_token_secret"
        star_u = f"bot_star_{base_seed}"
        async with db.Session() as s:
            s.add(db.Bot(
                id=base_seed + 3,
                owner_id=base_seed + 30,
                username=star_u,
                name="متجر النجوم",
                token=crypto.enc(star_token),
                template="tgstars",
                status="active",
            ))
            await s.commit()

        star_init = make_init_data(star_token, {"id": buyer_uid, "first_name": "Sami Star", "username": "staruser"})
        r_star_cat = await client.get(f"/api/miniapp/{star_u}/catalog", headers={"X-Telegram-Init-Data": star_init})
        assert r_star_cat.status == 200
        star_data = await r_star_cat.json()
        assert len(star_data["categories"]) == 3
        assert len(star_data["products"]) > 0

        # شحن وشراء نجوم
        await ledger.credit_user(base_seed + 3, buyer_uid, 15.0, "deposit_star")
        star_prod = star_data["products"][0]
        r_star_ord = await client.post(
            f"/api/miniapp/{star_u}/order",
            headers={"X-Telegram-Init-Data": star_init},
            json={"product_id": star_prod["id"], "target": "@mycoolchannel"},
        )
        assert r_star_ord.status == 200
        star_ord_res = await r_star_ord.json()
        assert star_ord_res["ok"] is True

    finally:
        await client.close()


@pytest.mark.anyio
async def test_admin_miniapp_endpoints():
    """اختبار لوحة الأدمن المركزية (Admin Mini App API)."""
    await db.init()
    app = web.Application()
    miniapp_api.setup_routes(app)
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        admin_id = config.ADMIN_ID or 777888999
        config.ADMIN_ID = admin_id
        maker_tok = config.MAKER_TOKEN or "maker_test_secret_tok_123"
        config.MAKER_TOKEN = maker_tok

        admin_init = make_init_data(maker_tok, {"id": admin_id, "first_name": "Platform Admin", "username": "admin"})
        normal_init = make_init_data(maker_tok, {"id": 123456, "first_name": "Normal Person", "username": "normal"})

        # 1. رفض غير الأدمن (403 Forbidden)
        r_deny = await client.get("/api/admin_app/overview", headers={"X-Telegram-Init-Data": normal_init})
        assert r_deny.status == 403

        # 2. قبول الأدمن (200 OK)
        r_over = await client.get("/api/admin_app/overview", headers={"X-Telegram-Init-Data": admin_init})
        assert r_over.status == 200
        over_data = await r_over.json()
        assert over_data["ok"] is True
        assert "stats" in over_data
        assert "total_bots" in over_data["stats"]

        # 3. جلب قائمة الطلبات
        r_orders = await client.get("/api/admin_app/orders", headers={"X-Telegram-Init-Data": admin_init})
        assert r_orders.status == 200
        orders_data = await r_orders.json()
        assert orders_data["ok"] is True
        assert isinstance(orders_data["orders"], list)

        # 4. الاسترجاع المزدوج الذري من لوحة الأدمن
        test_oid = f"test_dual_ref_{int(time.time()*1000)}"
        async with db.Session() as s:
            s.add(db.ServiceOrder(
                order_id=test_oid,
                bot_id=10101,
                user_id=20202,
                tpl_key="digital",
                service_id="test_svc",
                service_name="خدمة تجريبية",
                target="tgt",
                quantity=1,
                price_user_usd=5.0,
                cost_platform_usd=3.5,
                status="queued",
                created=dt.datetime.now(dt.timezone.utc),
            ))
            await s.commit()

        r_dual = await client.post(
            "/api/admin_app/dual_refund",
            headers={"X-Telegram-Init-Data": admin_init},
            json={"order_id": test_oid, "reason": "استرجاع يدوي من لوحة الأدمن"},
        )
        assert r_dual.status == 200
        dual_res = await r_dual.json()
        assert dual_res["ok"] is True

        # التأكد من تحديث الطلب إلى refunded
        async with db.Session() as s:
            check_order = (await s.execute(db.select(db.ServiceOrder).where(db.ServiceOrder.order_id == test_oid))).scalars().first()
            assert check_order.status == "refunded"
            assert check_order.is_dual_refunded is True

    finally:
        await client.close()
