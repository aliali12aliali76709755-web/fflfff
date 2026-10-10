"""قالب شحن الألعاب والاشتراكات والبطاقات الرقمية (Games & Digital Services):
- شحن الألعاب (ببجي موبايل، فري فاير، روبلوكس، كول أوف ديوتي).
- اشتراكات التطبيقات (نتفلكس، سبوتيفاي، يوتيوب، شات جي بي تي).
- بطاقات وقسائم رقمية مع دعم المخزون التلقائي (Stock) أو الطابور الآلي السريع.
- محفظة داخلية ودفع بالنجوم والدفع اليدوي.
- لوحة تحكم كاملة للمالك لتنفيذ الطلبات وتسليم الأكواد وإدارة المخزون.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import uuid
from typing import Any
from sqlalchemy import func, select

from .. import db, ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ..modules import currency, ledger, payments, promo
from ..modules.providers.digital import (
    DIGITAL_CATALOG,
    DigitalManager,
)

log = logging.getLogger("forge.digital")


class Digital(Tpl):
    key = "digital"
    emoji = "🎮"
    ar = "شحن الألعاب والاشتراكات"
    en = "Games & Digital Services"
    d_ar = "شحن شدات ببجي، جواهر فري فاير، روبلوكس، واشتراكات نتفلكس وبطاقات رقمية"
    d_en = "Game top-up (PUBG, Free Fire, Roblox), app subscriptions and digital gift cards"
    cats = ("biz",)
    guide_ar = (
        "🎮 <b>قالب شحن الألعاب والاشتراكات والخدمات الرقمية</b>\n\n"
        "1. <b>الأقسام والخدمات:</b> يتيح لزبائنك شحن الألعاب (ببجي، فري فاير)، اشتراكات التطبيقات، وشراء البطاقات الرقمية.\n"
        "2. <b>نظام المعالجة السريعة:</b> يتم إرسال الطلبات إلى طابور المعالجة الآمن، وتصلك إشعارات فورية بكل طلب مع أزرار التأكيد أو إرسال كود للزبون بضغطة زر.\n"
        "3. <b>المخزون الآلي للأكواد:</b> يمكنك رفع أكواد وبطاقات مسبقاً من قسم «📦 إدارة مخزون الأكواد» ليتم تسليمها للزبائن فورياً وبشكل آلي 100%.\n"
        "4. <b>الاسترجاع والأمان:</b> في حال تعذر تنفيذ أي طلب، يمكنك الضغط على «رفض واسترجاع» ليعود رصيد الزبون كاملاً لمحفظته تلقائياً."
    )

    # ───────────────────────────── واجهة المستخدم ─────────────────────────────

    async def home(self, c: Ctx) -> None:
        bal_display = await ledger.get_user_balance_display(c.bot_id, c.uid)
        intro = await c.kv("digital:intro") or c.t(
            "مرحباً بك في بوت شحن الألعاب والخدمات الرقمية 🎮✨\nاشحن ألعابك المفضلة واشترك في أقوى التطبيقات وبطاقات الهدايا بأمان وسرعة فائقة.",
            "Welcome to Games & Digital Services Bot 🎮✨\nTop up games, app subscriptions and gift cards with top speed and security.",
        )
        t = c.t
        text = (
            ui.head(c.brand) +
            f"{esc(intro)}\n\n"
            f"💰 <b>{t('رصيدك الحالي:', 'Your Balance:')}</b> <code>{bal_display}</code>\n"
            f"🆔 <b>{t('معرّف حسابك:', 'Your ID:')}</b> <code>{c.uid}</code>"
        )
        rows = [
            [B(t("🎮 شحن الألعاب", "🎮 Game Top-Up"), "t:cat:games", style="success"),
             B(t("🎬 اشتراكات التطبيقات", "🎬 App Subscriptions"), "t:cat:apps")],
            [B(t("🔑 بطاقات وقسائم رقمية", "🔑 Gift Cards"), "t:cat:cards"),
             B(t("💳 شحن المحفظة", "💳 Top-up Wallet"), "t:wallet")],
            [B(t("📦 طلباتي السابقة", "📦 My Orders"), "t:orders"),
             B(t("🎁 كود خصم", "🎁 Promo Code"), "t:promo")],
            [B(t("👥 كسب رصيد مجاني (الإحالة)", "👥 Earn Credit (Referral)"), "t:ref"),
             B(t("ℹ️ مساعدة وشروط", "ℹ️ Help & Terms"), "t:help")],
            c.tail(),
        ]
        await c.edit(text, kb(rows))

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        act = a[0]
        t = c.t

        # ── استعراض الأقسام ──
        if act == "cat":
            cat_name = a[1]
            all_services = await DigitalManager.get_services_catalog(c.bot_id)
            services = [s for s in all_services if s.get("category") == cat_name]

            titles = {
                "games": ("🎮 شحن الألعاب الرسمية", "🎮 Official Game Top-Up"),
                "apps": ("🎬 اشتراكات التطبيقات والبث", "🎬 App Subscriptions"),
                "cards": ("🔑 بطاقات وقسائم رقمية", "🔑 Digital Gift Cards"),
            }
            cat_title = titles.get(cat_name, (cat_name, cat_name))[0 if c.lang == "ar" else 1]

            if not services:
                await c.edit(
                    ui.head(cat_title) +
                    t("لا توجد خدمات متاحة حالياً في هذا القسم.", "No services currently available."),
                    kb([[B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
                )
                return

            rows = []
            for s in services:
                price_str = await currency.format_price_for_bot(c.bot_id, s["price_usd"])
                s_name = s.get("name_ar" if c.lang == "ar" else "name_en", s["name_ar"])
                rows.append([B(f"{s_name} — {price_str}", f"t:svc:{s['id']}")])
            rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])

            await c.edit(
                ui.head(cat_title) +
                t("اختر الخدمة أو الباقة المطلوبة:", "Select service or package:"),
                kb(rows)
            )

        # ── تفاصيل الخدمة ──
        elif act == "svc":
            sid = a[1]
            all_services = await DigitalManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                await c.answer(t("الخدمة غير موجودة", "Service not found"), True)
                return

            price_str = await currency.format_price_for_bot(c.bot_id, svc["price_usd"])
            bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
            field_name = svc.get("field_ar" if c.lang == "ar" else "field_en", "البيانات المطلوبة")
            desc = svc.get("desc_ar" if c.lang == "ar" else "desc_en", "")

            # فحص إن كان هناك مخزون فوري
            stock_count = await DigitalManager.get_stock_count(c.bot_id, sid)
            stock_badge = t(f"⚡ تسليم فوري متاح (متوفر: {stock_count})" if stock_count > 0 else "⏳ تنفيذ آلي سريع (30 - 120 دقيقة)",
                            f"⚡ Instant Delivery ({stock_count} in stock)" if stock_count > 0 else "⏳ Queue (30 - 120 mins)")

            text = (
                f"<b>{esc(svc['name_ar'] if c.lang == 'ar' else svc['name_en'])}</b>\n"
                f"{ui.LINE}\n\n"
                f"💵 <b>{t('السعر الإجمالي:', 'Total Price:')}</b> {price_str}\n"
                f"🚀 <b>{t('طريقة وسرعة التسليم:', 'Delivery Speed:')}</b> {stock_badge}\n"
                f"📝 <b>{t('المطلوب إدخاله:', 'Required Input:')}</b> {field_name}\n\n"
                f"📌 <b>{t('الوصف:', 'Description:')}</b>\n{esc(desc)}\n\n"
                f"💰 <b>{t('رصيدك المتوفر:', 'Your Balance:')}</b> {bal_str}"
            )
            rows = [
                [B(t("🛒 طلب هذه الخدمة الآن", "🛒 Order This Service"), f"t:ord_start:{sid}", style="success")],
                [B(t("⬅️ رجوع للقسم", "⬅️ Back to Category"), f"t:cat:{svc['category']}")],
            ]
            await c.edit(text, kb(rows))

        # ── بدء الطلب وإدخال البيانات ──
        elif act == "ord_start":
            sid = a[1]
            all_services = await DigitalManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                return

            field_name = svc.get("field_ar" if c.lang == "ar" else "field_en", "البيانات المطلوبة")
            c.set_state("digital_input_field", sid=sid)
            text = (
                ui.head(t("✍️ إدخال بيانات الشحن", "✍️ Enter Order Data")) +
                t(
                    f"الخدمة: <b>{esc(svc['name_ar'])}</b>\n\n"
                    f"يرجى إرسال <b>{field_name}</b> بدقة:\n\n"
                    f"/cancel للإلغاء",
                    f"Service: <b>{esc(svc['name_en'])}</b>\n\n"
                    f"Please send your <b>{field_name}</b>:\n\n"
                    f"/cancel to abort"
                )
            )
            await c.edit(text, kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:svc:{sid}")]]))

        # ── تأكيد الطلب ──
        elif act == "ord_confirm":
            draft = c.x.user_data.get("digital_draft")
            if not draft:
                await c.answer(t("انتهت صلاحية الجلسة، ابدأ من جديد", "Session expired"), True)
                await self.home(c)
                return
            await self._execute_order(c, draft)

        # ── إلغاء الطلب ──
        elif act == "ord_cancel":
            c.x.user_data.pop("digital_draft", None)
            c.clear_state()
            await c.answer(t("تم إلغاء الطلب", "Order canceled"))
            await self.home(c)

        # ── إدخال كود خصم للطلب ──
        elif act == "ord_promo":
            draft = c.x.user_data.get("digital_draft")
            if not draft:
                await self.home(c)
                return
            c.set_state("digital_order_promo")
            await c.edit(
                ui.head(t("🎟 إدخال كود الخصم", "🎟 Enter Promo Code")) +
                t("أرسل كود الخصم لتطبيقه على هذا الطلب:\n\n/cancel للإلغاء",
                  "Send promo code to apply:\n\n/cancel to abort"),
                kb([[B(t("⬅️ رجوع لمراجعة الطلب", "⬅️ Back to Review"), "t:ord_back_review")]])
            )

        elif act == "ord_back_review":
            draft = c.x.user_data.get("digital_draft")
            if not draft:
                await self.home(c)
                return
            await self._show_order_review(c, draft)

        # ── المحفظة والشحن ──
        elif act == "wallet":
            bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
            txs = await ledger.get_user_transactions(c.bot_id, c.uid, limit=5)
            t = c.t

            tx_lines = []
            for tx in txs:
                sign = "➕" if tx.direction == "credit" else "➖"
                d_str = tx.created.strftime("%m-%d %H:%M")
                desc = esc(tx.description or tx.kind)
                tx_lines.append(f"{sign} <b>${tx.amount_usd:.2f}</b> — {desc} <i>({d_str})</i>")

            hist_text = "\n".join(tx_lines) if tx_lines else t("لا توجد حركات مالية بعد.", "No transactions yet.")
            text = (
                ui.head(t("💼 المحفظة والرصيد", "💼 Wallet & Balance")) +
                f"💰 <b>{t('رصيدك الحالي:', 'Current Balance:')}</b> <code>{bal_display if (bal_display := bal_str) else ''}</code>\n"
                f"🆔 <b>{t('معرّف المحفظة:', 'Wallet ID:')}</b> <code>{c.uid}</code>\n\n"
                f"📜 <b>{t('آخر العمليات:', 'Recent Transactions:')}</b>\n{hist_text}"
            )
            rows = [
                [B(t("➕ شحن الرصيد الآن", "➕ Top-up Balance"), "t:deposit", style="success")],
                [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
            ]
            await c.edit(text, kb(rows))

        elif act == "deposit":
            methods = await payments.get_active_payment_methods(c.bot_id)
            rows = []
            for m in methods:
                rows.append([B(f"💳 {m['name']}", f"t:dep_m:{m['id']}")])
            rows.append([B(t("⬅️ المحفظة", "⬅️ Wallet"), "t:wallet")])
            await c.edit(
                ui.head(t("💳 شحن الرصيد", "💳 Top-up Balance")) +
                t("اختر طريقة الدفع المناسبة لشحن محفظتك:", "Choose your payment method:"),
                kb(rows)
            )

        elif act == "dep_m":
            mid = a[1]
            methods = await payments.get_active_payment_methods(c.bot_id)
            method = next((m for m in methods if m["id"] == mid), None)
            if not method:
                await c.answer(t("طريقة الدفع غير مفعلة", "Inactive method"), True)
                return

            if mid == "telegram_stars":
                stars_rows = [
                    [B("⭐ 50 Star (~$0.80)", "t:stars_buy:50"), B("⭐ 100 Star (~$1.60)", "t:stars_buy:100")],
                    [B("⭐ 250 Star (~$4.00)", "t:stars_buy:250"), B("⭐ 500 Star (~$8.00)", "t:stars_buy:500")],
                    [B(t("⬅️ طرق الدفع", "⬅️ Payment Methods"), "t:deposit")],
                ]
                await c.edit(
                    ui.head("⭐ نجوم تيليجرام (Telegram Stars)") +
                    t("ادفع بنجوم تيليجرام لتحصل على شحن فوري وآلي دون انتظار!\n\nاختر الباقة المطلوبة:",
                      "Pay with Telegram Stars for instant top-up:\n\nSelect package:"),
                    kb(stars_rows)
                )
                return

            c.set_state("digital_deposit_proof", method_id=mid)
            instr = method.get("instructions", "")
            acc = method.get("account", "")
            text = (
                ui.head(f"💳 {method['name']}") +
                (f"📌 <b>{t('تعليمات التحويل:', 'Instructions:')}</b>\n{esc(instr)}\n\n" if instr else "") +
                (f"🏦 <b>{t('رقم الحساب / المحفظة للتحويل:', 'Account / Address:')}</b>\n<code>{esc(acc)}</code>\n\n" if acc else "") +
                t("📸 <b>يرجى إرسال لقطة شاشة لإشعار التحويل (أو أرسل رقم العملية والمبلغ نصاً):</b>\n\n/cancel للإلغاء",
                  "📸 <b>Send screenshot or transfer reference:\n\n/cancel to abort</b>")
            )
            await c.edit(text, kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:deposit")]]))

        elif act == "stars_buy":
            stars_num = int(a[1])
            ok, tx, new_bal = await payments.process_stars_deposit(c.bot_id, c.uid, stars_num)
            if ok:
                bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
                await c.edit(
                    ui.head(t("✅ تم الشحن بنجاح!", "✅ Top-up Successful!")) +
                    t(f"تم شحن <b>{stars_num} ⭐</b> إلى محفظتك بنجاح!\n\n💰 <b>رصيدك الجديد:</b> <code>{bal_str}</code>",
                      f"Added <b>{stars_num} ⭐</b> to wallet!\nNew balance: <code>{bal_str}</code>"),
                    kb([[B(t("🎮 شحن الألعاب", "🎮 Game Top-Up"), "t:cat:games", style="success")],
                        [B(t("💼 المحفظة", "💼 Wallet"), "t:wallet")]])
                )
            else:
                await c.answer(t("فشل شحن النجوم", "Stars top-up failed"), True)

        # ── سجل الطلبات ──
        elif act == "orders":
            async with db.Session() as s:
                orders = (await s.execute(
                    select(db.ServiceOrder)
                    .where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.user_id == c.uid, db.ServiceOrder.tpl_key == "digital")
                    .order_by(db.ServiceOrder.created.desc())
                    .limit(10)
                )).scalars().all()

            if not orders:
                await c.edit(
                    ui.head(t("📦 طلباتي", "📦 My Orders")) +
                    t("ليس لديك أي طلبات سابقة بعد.", "You have no previous orders yet."),
                    kb([[B(t("🎮 شحن لعبة أو خدمة", "🎮 New Order"), "t:cat:games", style="success")],
                        [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
                )
                return

            lines = []
            st_map = {
                "queued": "⏳ قيد المعالجة (طابور آلي)",
                "completed": "✅ تم الشحن والتسليم",
                "canceled": "❌ ملغى ومسترجع",
            }
            for o in orders:
                note_txt = f"\n   📝 الكود/ملاحظة: <code>{o.details.get('fulfillment_note')}</code>" if o.details.get("fulfillment_note") else ""
                lines.append(f"▫️ <b>#{o.order_id}</b> | {esc(o.service_name)}\n   البيانات: <code>{esc(o.target)}</code>\n   الحالة: <b>{st_map.get(o.status, o.status)}</b> · ${o.price_user_usd:.2f}{note_txt}\n")

            await c.edit(
                ui.head(t("📦 سجل آخر الطلبات", "📦 Recent Orders")) + "\n".join(lines),
                kb([[B(t("🎮 طلب جديد", "🎮 New Order"), "t:cat:games", style="success")],
                    [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )

        # ── أكواد الخصم والإحالة ومساعدة ──
        elif act == "promo":
            c.set_state("digital_enter_promo")
            await c.edit(
                ui.head(t("🎁 كود خصم أو هدية", "🎁 Promo Code")) +
                t("أرسل كود الخصم أو الهدية للحصول على رصيد إضافي في محفظتك:\n\n/cancel للإلغاء",
                  "Send promo code to claim bonus balance:\n\n/cancel to abort"),
                kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:home")]])
            )

        elif act == "ref":
            ref_link = c.link(f"ref_{c.uid}")
            ref_cfg = await promo.get_referral_config(c.bot_id)
            bonus_str = f"${ref_cfg.get('signup_bonus', 0.10):.2f}"
            pct_str = f"{ref_cfg.get('order_bonus_percent', 5.0)}%"

            text = (
                ui.head(t("👥 نظام الإحالة والأرباح", "👥 Referral Program")) +
                t(
                    f"شارك رابطك الخاص مع أصدقائك واكسب رصيداً مجانياً عند انضمامهم وشحنهم:\n\n"
                    f"🎁 <b>مكافأة التسجيل:</b> {bonus_str} لكل عضو جديد\n"
                    f"📈 <b>عمولة من الطلبات:</b> {pct_str} من كل عملية شراء\n\n"
                    f"🔗 <b>رابطك المباشر:</b>\n<code>{ref_link}</code>",
                    f"Share referral link and earn rewards:\n\n"
                    f"🎁 <b>Signup reward:</b> {bonus_str}\n"
                    f"📈 <b>Commission:</b> {pct_str}\n\n"
                    f"🔗 <b>Link:</b>\n<code>{ref_link}</code>"
                )
            )
            rows = [
                [B(t("📤 مشاركة الرابط", "📤 Share Link"), url=f"https://t.me/share/url?url={ref_link}")],
                [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
            ]
            await c.edit(text, kb(rows))

        elif act == "help":
            await c.edit(
                ui.head(t("ℹ️ مساعدة وشروط الخدمة", "ℹ️ Help & Terms")) +
                t(
                    "📌 <b>تعليمات هامة عند شحن الألعاب والاشتراكات:</b>\n"
                    "1. تأكد من إدخال الآيدي (Player ID) أو الحساب بدقة تامة.\n"
                    "2. مدة تنفيذ الطلبات تتراوح عادة بين 30 دقيقة إلى ساعتين كحد أقصى.\n"
                    "3. سيصلك إشعار فوري في البوت فور اكتمال الشحن أو تسليم كود القسيمة.\n"
                    "4. في حال حدوث أي خطأ في الحساب المدخل، سيتم استرجاع رصيدك كاملاً إلى محفظتك.",
                    "📌 <b>Ordering Rules:</b>\n"
                    "1. Double check your Player ID / Email.\n"
                    "2. Execution queue takes between 30 to 120 minutes.\n"
                    "3. You will receive an instant notification when fulfilled."
                ),
                kb([[B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )

        # ───────────────────────── لوحة تحكم المالك ─────────────────────────
        elif act == "adm":
            sub = a[1]
            if not c.is_owner:
                await c.answer(t("للمالك فقط", "Owner only"), True)
                return

            if sub == "margin":
                margin_conf = await c.kv("digital:margin", {"type": "percent", "val": 20.0})
                cur_val = f"{margin_conf['val']}%" if margin_conf["type"] == "percent" else f"${margin_conf['val']}"
                text = (
                    ui.head(t("📈 هامش الربح للخدمات الرقمية", "📈 Profit Margin")) +
                    f"هامش الربح الحالي: <b>{cur_val}</b>\n\nاختر نسبة سريعة أو اضغط مخصص:"
                )
                rows = [
                    [B("+10%", "t:adm:set_m:10"), B("+20%", "t:adm:set_m:20"), B("+30%", "t:adm:set_m:30")],
                    [B("+40%", "t:adm:set_m:40"), B("+50%", "t:adm:set_m:50")],
                    [B(t("✏️ كتابة نسبة مخصصة", "✏️ Custom Margin"), "t:adm:input_m")],
                    [B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "set_m":
                val = float(a[2])
                await c.kv_set("digital:margin", {"type": "percent", "val": val})
                await c.answer(t(f"تم ضبط الهامش إلى {val}%", f"Margin set to {val}%"))
                await self.cb(c, ["adm", "margin"])

            elif sub == "input_m":
                c.set_state("digital_adm_margin")
                await c.edit(
                    ui.head(t("📈 كتابة هامش الربح", "📈 Custom Margin")) +
                    t("أرسل نسبة الربح المئوية (مثال: <code>25</code> لـ 25%):\n\n/cancel للإلغاء",
                      "Send percentage (e.g. <code>25</code> for 25%):\n\n/cancel to abort"),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:margin")]])
                )

            # تنفيذ الطلبات من قِبل المالك
            elif sub == "dig_done":
                ord_id = a[2]
                ok, msg = await DigitalManager.complete_order(c.bot_id, ord_id, note_or_code="تم الشحن بنجاح")
                if ok:
                    await c.answer(t("تم تأكيد إكمال الطلب بنجاح! ✅", "Order marked complete! ✅"), True)
                    # إشعار الزبون
                    async with db.Session() as s:
                        res = await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_id))
                        ord_row = res.scalars().first()
                    if ord_row:
                        try:
                            await c.bot.send_message(
                                ord_row.user_id,
                                t(
                                    f"🎉 <b>تم اكتمال شحن طلبك بنجاح!</b>\n\n"
                                    f"📌 <b>الخدمة:</b> {esc(ord_row.service_name)}\n"
                                    f"🆔 <b>رقم الطلب:</b> <code>#{ord_row.order_id}</code>\n"
                                    f"✅ تم تنفيذ الشحن بنجاح لحسابك، شكراً لاختيارك خدماتنا!",
                                    f"🎉 <b>Order Fulfilled Successfully!</b>\n\n"
                                    f"Service: {esc(ord_row.service_name)}\n"
                                    f"Order: #{ord_row.order_id}"
                                ),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    await self.cb(c, ["adm", "orders"])
                else:
                    await c.answer(msg, True)

            elif sub == "dig_send_code":
                ord_id = a[2]
                c.set_state("digital_adm_send_code", ord_id=ord_id)
                await c.edit(
                    ui.head(t("🔑 تسليم كود أو قسيمة للزبون", "🔑 Deliver Voucher Code")) +
                    t(
                        f"أرسل كود القسيمة أو بيانات الحساب المراد تسليمها للزبون للطلب <code>#{ord_id}</code>:\n\n"
                        f"/cancel للإلغاء",
                        f"Send voucher code for order #{ord_id}:\n\n/cancel to abort"
                    ),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:orders")]])
                )

            elif sub == "dig_refund":
                ord_id = a[2]
                ok, msg, new_bal = await DigitalManager.cancel_and_refund(c.bot_id, ord_id, reason="رفض لتعذر الشحن")
                if ok:
                    await c.answer(t("تم إلغاء الطلب واسترجاع الرصيد للزبون", "Canceled and refunded"), True)
                    async with db.Session() as s:
                        res = await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_id))
                        ord_row = res.scalars().first()
                    if ord_row:
                        try:
                            await c.bot.send_message(
                                ord_row.user_id,
                                t(
                                    f"⚠️ <b>تنبيه بخصوص طلبك #{ord_row.order_id}:</b>\n\n"
                                    f"تعذر تنفيذ الشحن للخدمة <b>{esc(ord_row.service_name)}</b>.\n"
                                    f"تم إعادة المبلغ كاملاً <code>${ord_row.price_user_usd:.2f}</code> إلى محفظتك بنجاح.",
                                    f"⚠️ Order #{ord_row.order_id} canceled and refunded."
                                ),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    await self.cb(c, ["adm", "orders"])

            # إدارة المخزون
            elif sub == "stock":
                all_services = await DigitalManager.get_services_catalog(c.bot_id)
                card_svcs = [s for s in all_services if s.get("category") == "cards"]
                rows = []
                for s in card_svcs:
                    cnt = await DigitalManager.get_stock_count(c.bot_id, s["id"])
                    rows.append([B(f"{s['name_ar'][:20]} (المتوفر: {cnt})", f"t:adm:add_stock:{s['id']}")])
                rows.append([B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")])

                await c.edit(
                    ui.head(t("📦 إدارة مخزون البطاقات الرقمية", "📦 Manage Voucher Stock")) +
                    t("اضغط على أي بطاقة لإضافة أكواد جديدة إلى مخزونها للتسليم الآلي الفوري:",
                      "Select a card to upload voucher codes for instant delivery:"),
                    kb(rows)
                )

            elif sub == "add_stock":
                sid = a[2]
                all_services = await DigitalManager.get_services_catalog(c.bot_id)
                svc = next((s for s in all_services if s["id"] == sid), None)
                if not svc:
                    return
                c.set_state("digital_adm_add_stock", sid=sid)
                cnt = await DigitalManager.get_stock_count(c.bot_id, sid)
                await c.edit(
                    ui.head(t(f"➕ شحن مخزون {esc(svc['name_ar'])}", f"➕ Add Stock for {esc(svc['name_en'])}")) +
                    t(
                        f"المتوفر حالياً: <b>{cnt} كود</b>\n\n"
                        f"أرسل الأكواد الجديدة (يمكنك إرسال كود واحد أو عدة أكواد كل كود في سطر مستقل):\n\n"
                        f"/cancel للإلغاء",
                        f"Current stock: {cnt}\n\nSend codes (one per line):\n\n/cancel to abort"
                    ),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:stock")]])
                )

            # سجل الطلبات
            elif sub == "orders":
                async with db.Session() as s:
                    orders = (await s.execute(
                        select(db.ServiceOrder)
                        .where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.tpl_key == "digital")
                        .order_by(db.ServiceOrder.created.desc())
                        .limit(10)
                    )).scalars().all()

                rows = []
                lines = []
                for o in orders:
                    lines.append(f"#{o.order_id} | {esc(o.service_name[:15])} | <code>{esc(o.target[:15])}</code> | ${o.price_user_usd:.2f} | <b>{o.status}</b>")
                    if o.status == "queued":
                        rows.append([
                            B(f"✅ تم #{o.order_id[-6:]}", f"t:adm:dig_done:{o.order_id}", style="success"),
                            B(f"🔑 كود #{o.order_id[-6:]}", f"t:adm:dig_send_code:{o.order_id}"),
                            B(f"❌ استرجاع", f"t:adm:dig_refund:{o.order_id}", style="danger"),
                        ])
                rows.append([B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")])

                text = (
                    ui.head(t(f"📦 طلبات الشحن الرقمي ({len(orders)})", f"📦 Digital Orders ({len(orders)})")) +
                    ("\n".join(lines) if lines else t("لا توجد طلبات بعد.", "No orders yet."))
                )
                await c.edit(text, kb(rows))

            # إيصالات الشحن
            elif sub == "rcpts":
                async with db.Session() as s:
                    rcpts = (await s.execute(
                        select(db.PaymentReceipt)
                        .where(db.PaymentReceipt.bot_id == c.bot_id, db.PaymentReceipt.status == "pending")
                        .order_by(db.PaymentReceipt.created.desc())
                        .limit(10)
                    )).scalars().all()

                if not rcpts:
                    await c.edit(
                        ui.head(t("🧾 إيصالات الدفع المعلقة", "🧾 Pending Receipts")) +
                        t("لا توجد إيصالات تنتظر المراجعة حالياً ✅", "No pending receipts right now ✅"),
                        kb([[B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")]])
                    )
                    return

                rows = []
                for r in rcpts:
                    rows.append([B(f"🧾 #{r.receipt_id} — ${r.amount_usd:.2f} ({r.user_name})", f"t:adm:rcpt_view:{r.receipt_id}")])
                rows.append([B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")])
                await c.edit(ui.head(t(f"🧾 إيصالات تنتظر المراجعة ({len(rcpts)})", f"🧾 Pending Receipts ({len(rcpts)})")), kb(rows))

            elif sub == "rcpt_view":
                rcpt_id = a[2]
                r = await payments.get_receipt(rcpt_id)
                if not r:
                    return
                text = (
                    ui.head(f"🧾 إيصال شحن #{r.receipt_id}") +
                    f"👤 <b>الزبون:</b> {esc(r.user_name)} (ID: <code>{r.user_id}</code>)\n"
                    f"💳 <b>طريقة الدفع:</b> {esc(r.method)}\n"
                    f"💵 <b>المبلغ:</b> {r.amount:,.2f} {r.currency} (≈ <code>${r.amount_usd:.2f}</code>)\n"
                    f"📝 <b>الإثبات:</b>\n{esc(r.proof_text or 'صورة مرفقة')}\n"
                    f"🕒 <b>التاريخ:</b> {r.created.strftime('%Y-%m-%d %H:%M')}"
                )
                rows = [
                    [B(t(f"✅ قبول وشحن (${r.amount_usd:.2f})", f"✅ Approve (${r.amount_usd:.2f})"),
                       f"t:adm:rcpt_ok:{r.receipt_id}", style="success"),
                     B(t("❌ رفض الإيصال", "❌ Reject"), f"t:adm:rcpt_no:{r.receipt_id}", style="danger")],
                    [B(t("⬅️ كل الإيصالات", "⬅️ All Receipts"), "t:adm:rcpts")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "rcpt_ok":
                rcpt_id = a[2]
                ok, msg, new_bal = await payments.approve_receipt(rcpt_id)
                if ok:
                    await c.answer(t("تمت الموافقة وشحن الرصيد! ✅", "Approved & Credited! ✅"), True)
                    r = await payments.get_receipt(rcpt_id)
                    if r:
                        try:
                            bal_str = await ledger.get_user_balance_display(c.bot_id, r.user_id)
                            await c.bot.send_message(
                                r.user_id,
                                t(f"✅ <b>تمت الموافقة على شحن رصيدك!</b>\nالمبلغ المضاف: <code>${r.amount_usd:.2f}</code>\nرصيدك الآن: <code>{bal_str}</code>",
                                  f"✅ Top-up approved! Credited: ${r.amount_usd:.2f}"),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    await self.cb(c, ["adm", "rcpts"])

            elif sub == "rcpt_no":
                rcpt_id = a[2]
                ok, msg = await payments.reject_receipt(rcpt_id, reason="رفض بواسطة الإدارة")
                if ok:
                    await c.answer(t("تم رفض الإيصال", "Receipt rejected"), True)
                    await self.cb(c, ["adm", "rcpts"])

            # العملة
            elif sub == "cur":
                cur_curr = await currency.get_bot_currency(c.bot_id)
                top_currencies = ["USD", "IQD", "SYP", "SAR", "AED", "EGP", "EUR", "TRY", "POINTS"]
                rows = []
                for cur_code in top_currencies:
                    c_info = currency.CURRENCIES.get(cur_code, {})
                    is_sel = "🔘 " if cur_code == cur_curr else ""
                    rows.append(B(f"{is_sel}{c_info.get('symbol', cur_code)} {c_info.get('name_ar', cur_code)}", f"t:adm:set_cur:{cur_code}"))
                grid = ui.grid(rows, 2)
                grid.append([B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")])
                await c.edit(
                    ui.head(t("💱 تغيير عملة عرض الأسعار", "💱 Bot Display Currency")) +
                    t(f"العملة المعتمدة حالياً: <b>{cur_curr}</b>\n\nاختر العملة التي تود أن تظهر بها الأسعار والأرصدة:",
                      f"Current currency: <b>{cur_curr}</b>\n\nSelect display currency:"),
                    kb(grid)
                )

            elif sub == "set_cur":
                new_c = a[2]
                await currency.set_bot_currency(c.bot_id, new_c)
                await c.answer(t(f"تم تغيير عملة البوت إلى {new_c}", f"Currency changed to {new_c}"))
                await self.cb(c, ["adm", "cur"])

    # ───────────────────────── معالجة الرسائل والإدخال ─────────────────────────

    async def msg(self, c: Ctx) -> bool:  # noqa: C901
        st = c.st
        if not st:
            return False

        if c.text == "/cancel":
            c.clear_state()
            c.x.user_data.pop("digital_draft", None)
            await c.send(c.t("تم الإلغاء.", "Cancelled."), kb([c.home_row()]))
            return True

        k = st.get("k")
        t = c.t

        # 1. إدخال بيانات الخدمة (Player ID أو الإيميل)
        if k == "digital_input_field":
            user_data = c.text.strip()
            sid = st.get("sid")
            all_services = await DigitalManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                c.clear_state()
                return True

            c.clear_state()
            draft = {
                "sid": sid,
                "sname": svc["name_ar" if c.lang == "ar" else "name_en"],
                "target": user_data,
                "price_usd": svc["price_usd"],
                "discount_usd": 0.0,
                "final_usd": svc["price_usd"],
                "promo_code": "",
            }
            c.x.user_data["digital_draft"] = draft
            await self._show_order_review(c, draft)
            return True

        # 2. كود خصم للطلب
        elif k == "digital_order_promo":
            code = c.text.strip().upper()
            draft = c.x.user_data.get("digital_draft")
            if not draft:
                c.clear_state()
                await self.home(c)
                return True

            val_ok, discount, msg = await promo.validate_promo(c.bot_id, c.uid, code, draft["price_usd"], draft["sid"])
            if not val_ok:
                await c.send(f"⚠️ {msg}\n\n/cancel للإلغاء")
                return True

            draft["discount_usd"] = discount
            draft["final_usd"] = max(round(draft["price_usd"] - discount, 2), 0.0)
            draft["promo_code"] = code
            c.x.user_data["digital_draft"] = draft
            c.clear_state()
            await c.send(f"✅ تم تطبيق كود الخصم بنجاح! خصم: ${discount:.2f}")
            await self._show_order_review(c, draft)
            return True

        # 3. إرسال إثبات الدفع اليدوي
        elif k == "digital_deposit_proof":
            mid = st.get("method_id", "manual")
            all_methods = await payments.get_payment_methods(c.bot_id)
            m_info = next((m for m in all_methods if m["id"] == mid), {"name": mid})
            bot_cur = await currency.get_bot_currency(c.bot_id)

            file_info = c.file_of()
            proof_file_id = file_info[0] if file_info else ""
            proof_txt = c.text or ""

            amount = 10.0
            for word in proof_txt.split():
                clean_w = word.replace("$", "").replace(",", "")
                try:
                    v = float(clean_w)
                    if v > 0:
                        amount = v
                        break
                except ValueError:
                    pass

            usd_amt = await currency.currency_to_usd(amount, bot_cur, bot_id=c.bot_id)

            rcpt = await payments.create_receipt(
                bot_id=c.bot_id,
                user_id=c.uid,
                user_name=c.name,
                username=c.user.username or "",
                method_name=m_info["name"],
                amount=amount,
                currency_code=bot_cur,
                amount_usd=usd_amt,
                proof_file_id=proof_file_id,
                proof_text=proof_txt,
            )
            c.clear_state()

            await c.send(
                t(
                    f"✅ <b>تم استلام إثبات الدفع بنجاح!</b>\n\n"
                    f"رقم الإيصال: <code>#{rcpt.receipt_id}</code>\n"
                    f"طلبك قيد المراجعة وسيتم شحن الرصيد فور تأكيده.",
                    f"✅ <b>Proof received!</b> Receipt: <code>#{rcpt.receipt_id}</code>"
                ),
                kb([[B(t("💼 المحفظة", "💼 Wallet"), "t:wallet"), B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )

            notify_owner_text = (
                f"🧾 <b>إشعار تحويل جديد قيد المراجعة!</b>\n"
                f"المرسل: {esc(c.name)} (@{esc(c.user.username or 'none')})\n"
                f"الطريقة: {esc(m_info['name'])}\n"
                f"المبلغ: {amount} {bot_cur} (≈ ${usd_amt:.2f})\n"
                f"الإثبات: {esc(proof_txt or 'صورة مرفقة')}"
            )
            owner_kb = kb([
                [B(f"✅ قبول وشحن (${usd_amt:.2f})", f"t:adm:rcpt_ok:{rcpt.receipt_id}", style="success"),
                 B("❌ رفض", f"t:adm:rcpt_no:{rcpt.receipt_id}", style="danger")]
            ])
            await c.notify_owner(notify_owner_text, kb=owner_kb)
            return True

        # 4. كود هدية عام
        elif k == "digital_enter_promo":
            code = c.text.strip().upper()
            val_ok, discount, msg = await promo.validate_promo(c.bot_id, c.uid, code, 10.0)
            if not val_ok:
                await c.send(f"⚠️ {msg}\n\n/cancel للإلغاء")
                return True
            await ledger.credit_user(c.bot_id, c.uid, discount, kind="promo_gift", description=f"هدية كود {code}")
            await promo.use_promo(c.bot_id, c.uid, code)
            c.clear_state()
            bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
            await c.send(
                t(f"🎉 <b>مبروك! تم تفعيل الكود وإضافة ${discount:.2f} إلى محفظتك!</b>\nرصيدك: <code>{bal_str}</code>",
                  f"🎉 Bonus added: ${discount:.2f}"),
                kb([[B(t("🎮 شحن الألعاب", "🎮 Game Top-Up"), "t:cat:games", style="success")],
                    [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )
            return True

        # 5. هامش المالك
        elif k == "digital_adm_margin":
            try:
                val = float(c.text.strip())
                await c.kv_set("digital:margin", {"type": "percent", "val": val})
                c.clear_state()
                await c.send(t(f"✅ تم ضبط الهامش إلى {val}%.", f"✅ Margin set to {val}%."))
                await self.cb(c, ["adm", "margin"])
            except ValueError:
                await c.send(t("⚠️ أدخل رقماً صحيحاً.", "⚠️ Enter valid number."))
            return True

        # 6. إرسال كود من المالك للزبون
        elif k == "digital_adm_send_code":
            ord_id = st.get("ord_id")
            code_val = c.text.strip()
            ok, msg = await DigitalManager.complete_order(c.bot_id, ord_id, note_or_code=code_val)
            if ok:
                c.clear_state()
                await c.send(f"✅ تم إرسال الكود للزبون وإكمال الطلب #{ord_id} بنجاح!")
                # إشعار الزبون بالكود
                async with db.Session() as s:
                    res = await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_id))
                    ord_row = res.scalars().first()
                if ord_row:
                    try:
                        await c.bot.send_message(
                            ord_row.user_id,
                            t(
                                f"🎉 <b>تم تسليم كود طلبك بنجاح!</b>\n\n"
                                f"📌 <b>الخدمة:</b> {esc(ord_row.service_name)}\n"
                                f"🆔 <b>رقم الطلب:</b> <code>#{ord_row.order_id}</code>\n\n"
                                f"🔑 <b>الكود الرقمي (اضغط للنسخ):</b>\n"
                                f"<code>{esc(code_val)}</code>\n\n"
                                f"شكراً لاختيارك خدماتنا!",
                                f"🎉 <b>Your Voucher Code:</b>\n<code>{esc(code_val)}</code>"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                await self.cb(c, ["adm", "orders"])
            else:
                await c.send(f"⚠️ {msg}")
            return True

        # 7. إضافة مخزون أكواد
        elif k == "digital_adm_add_stock":
            sid = st.get("sid")
            lines = [line.strip() for line in c.text.split("\n") if line.strip()]
            new_count = await DigitalManager.add_vouchers_to_stock(c.bot_id, sid, lines)
            c.clear_state()
            await c.send(t(f"✅ تم إضافة {len(lines)} كود إلى المخزون بنجاح! إجمالي المتوفر الآن: {new_count} كود.",
                           f"✅ Added {len(lines)} codes. Total stock: {new_count}."))
            await self.cb(c, ["adm", "stock"])
            return True

        return False

    # ───────────────────────── مراجعة وتنفيذ الطلب ─────────────────────────

    async def _show_order_review(self, c: Ctx, draft: dict[str, Any]) -> None:
        t = c.t
        user_bal_usd = await ledger.get_user_balance_usd(c.bot_id, c.uid)
        user_bal_disp = await ledger.get_user_balance_display(c.bot_id, c.uid)
        final_usd = draft["final_usd"]
        price_disp = await currency.format_price_for_bot(c.bot_id, final_usd)

        discount_line = ""
        if draft.get("discount_usd", 0) > 0:
            disc_disp = await currency.format_price_for_bot(c.bot_id, draft["discount_usd"])
            discount_line = f"🎁 <b>{t('الخصم المطبق:', 'Discount:')}</b> -{disc_disp} (كود: <code>{draft['promo_code']}</code>)\n"

        rem_usd = round(user_bal_usd - final_usd, 4)
        rem_disp = await currency.format_price_for_bot(c.bot_id, max(rem_usd, 0.0))
        is_enough = user_bal_usd >= final_usd

        text = (
            ui.head(t("🧾 تأكيد ومراجعة الطلب", "🧾 Order Review")) +
            f"📌 <b>{t('الخدمة:', 'Service:')}</b> {esc(draft['sname'])}\n"
            f"🎯 <b>{t('بيانات الحساب المدخلة:', 'Entered Target Data:')}</b> <code>{esc(draft['target'])}</code>\n"
            f"{discount_line}"
            f"💵 <b>{t('المبلغ المطلوب:', 'Required Price:')}</b> <code>{price_disp}</code>\n"
            f"{ui.LINE}\n"
            f"💰 <b>{t('رصيدك المتوفر:', 'Your Balance:')}</b> {user_bal_disp}\n" +
            (f"📉 <b>{t('الرصيد بعد الخصم:', 'Remaining Balance:')}</b> {rem_disp}\n\n" if is_enough
             else f"\n⚠️ <b>{t('رصيدك الحالي غير كافٍ لإتمام هذا الطلب!', 'Insufficient balance to complete order!')}</b>\n\n")
        )

        rows = []
        if is_enough:
            rows.append([B(t("✅ تأكيد الطلب وخصم الرصيد", "✅ Confirm & Pay"), "t:ord_confirm", style="success")])
        else:
            rows.append([B(t("💳 شحن المحفظة الآن", "💳 Top-up Balance Now"), "t:deposit", style="success")])

        if not draft.get("promo_code"):
            rows.append([B(t("🎟 إدخال كود خصم", "🎟 Apply Promo Code"), "t:ord_promo")])
        rows.append([B(t("❌ إلغاء", "❌ Cancel"), "t:ord_cancel", style="danger")])

        await c.edit(text, kb(rows))

    async def _execute_order(self, c: Ctx, draft: dict[str, Any]) -> None:
        t = c.t
        final_usd = draft["final_usd"]
        user_bal_usd = await ledger.get_user_balance_usd(c.bot_id, c.uid)

        if user_bal_usd < final_usd:
            await c.answer(t("رصيدك غير كافٍ", "Insufficient balance"), True)
            return

        ord_key = f"dig_{uuid.uuid4().hex[:10]}"

        # 1. خصم الرصيد ذرياً
        ok_debit, tx, new_bal = await ledger.debit_user(
            c.bot_id,
            c.uid,
            final_usd,
            kind="order_digital",
            ref_id=ord_key,
            description=f"طلب {draft['sname']} ({draft['target']})",
        )
        if not ok_debit:
            await c.answer(t("فشل خصم الرصيد", "Debit failed"), True)
            return

        # 2. فحص هل يوجد كود فوري في المخزون؟
        voucher_code = await DigitalManager.get_voucher_from_stock(c.bot_id, draft["sid"])
        order_status = "completed" if voucher_code else "queued"

        # 3. حفظ الطلب في قاعدة البيانات
        bot_cur = await currency.get_bot_currency(c.bot_id)
        cur_price = await currency.usd_to_currency(final_usd, bot_cur, bot_id=c.bot_id)
        async with db.Session() as s:
            s_order = db.ServiceOrder(
                order_id=ord_key,
                bot_id=c.bot_id,
                user_id=c.uid,
                tpl_key="digital",
                service_id=draft["sid"],
                service_name=draft["sname"],
                target=draft["target"],
                quantity=1,
                cost_provider_usd=0.0,
                cost_platform_usd=0.0,
                price_user_usd=final_usd,
                currency=bot_cur,
                price_user_currency=cur_price,
                status=order_status,
                provider_name="DigitalFulfillment",
                provider_order_id=ord_key,
                details={"fulfillment_note": voucher_code if voucher_code else "", "promo": draft.get("promo_code", "")},
            )
            s.add(s_order)
            await s.commit()

        if draft.get("promo_code"):
            await promo.use_promo(c.bot_id, c.uid, draft["promo_code"])

        await promo.award_order_commission(c.bot_id, c.uid, final_usd, ord_key)

        c.x.user_data.pop("digital_draft", None)
        bal_disp = await ledger.get_user_balance_display(c.bot_id, c.uid)

        # 4. إشعار الزبون
        if voucher_code:
            text = (
                ui.head(t("🎉 تم تسليم طلبك فورياً من المخزون!", "🎉 Order Delivered Instantly!")) +
                f"🆔 <b>{t('رقم الطلب:', 'Order ID:')}</b> <code>#{ord_key}</code>\n"
                f"📌 <b>{t('الخدمة:', 'Service:')}</b> {esc(draft['sname'])}\n\n"
                f"🔑 <b>{t('الكود الرقمي (اضغط لنسخه):', 'Your Voucher Code (Tap to copy):')}</b>\n"
                f"<code>{esc(voucher_code)}</code>\n\n"
                f"💰 <b>{t('رصيدك المتبقي:', 'Remaining Balance:')}</b> <code>{bal_disp}</code>\n\n"
                f"شكراً لاختيارك خدماتنا! 🌟"
            )
        else:
            text = (
                ui.head(t("⏳ تم استلام طلبك وجاري التنفيذ عبر النظام الآلي!", "⏳ Order Received & Queued!")) +
                f"🆔 <b>{t('رقم الطلب:', 'Order ID:')}</b> <code>#{ord_key}</code>\n"
                f"📌 <b>{t('الخدمة:', 'Service:')}</b> {esc(draft['sname'])}\n"
                f"🎯 <b>{t('البيانات المدخلة:', 'Target Data:')}</b> <code>{esc(draft['target'])}</code>\n"
                f"💵 <b>{t('المبلغ المدفوع:', 'Paid Amount:')}</b> <code>${final_usd:.2f}</code>\n\n"
                f"⏱ <b>{t('مدة التنفيذ التقديرية:', 'Estimated Queue Time:')}</b>\n"
                f"<i>{t('بين 30 دقيقة إلى ساعتين كحد أقصى. سيصلك إشعار فوري هنا فور اكتمال الشحن أو تسليم الكود.', 'Between 30 to 120 minutes. You will receive an instant notification when ready.')}</i>\n\n"
                f"💰 <b>{t('رصيدك المتبقي:', 'Remaining Balance:')}</b> <code>{bal_disp}</code>"
            )

        rows = [
            [B(t("📦 متابعة الطلب", "📦 Track Order"), "t:orders", style="success")],
            [B(t("🎮 شحن لعبة أخرى", "🎮 New Order"), "t:cat:games")],
            [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
        ]
        await c.edit(text, kb(rows))

        # 5. إشعار المالك فوري مع أزرار التنفيذ
        owner_text = (
            f"🎮 <b>طلب شحن رقمي جديد #{ord_key}!</b>\n"
            f"الخدمة: <b>{esc(draft['sname'])}</b>\n"
            f"البيانات: <code>{esc(draft['target'])}</code>\n"
            f"الزبون: {esc(c.name)} (ID: <code>{c.uid}</code>)\n"
            f"المبلغ المدفوع: <code>${final_usd:.2f}</code>"
        )
        owner_kb = kb([
            [B("✅ تأكيد الشحن والتسليم", f"t:adm:dig_done:{ord_key}", style="success"),
             B("🔑 إرسال كود للزبون", f"t:adm:dig_send_code:{ord_key}")],
            [B("❌ رفض واسترجاع الرصيد", f"t:adm:dig_refund:{ord_key}", style="danger")]
        ])
        await c.notify_owner(owner_text, kb=owner_kb)

    async def start_param(self, c: Ctx, param: str) -> bool:
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.split("_")[1])
                await promo.check_and_award_signup(c.bot_id, referrer_id, c.uid)
            except Exception as e:
                log.debug("Referral param parsing error: %s", e)
        return False

    async def owner(self, c: Ctx) -> tuple[str, list]:
        t = c.t
        async with db.Session() as s:
            total_orders = (await s.execute(
                select(func.count(db.ServiceOrder.id))
                .where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.tpl_key == "digital")
            )).scalar() or 0
            pending_rcpts = (await s.execute(
                select(func.count(db.PaymentReceipt.id))
                .where(db.PaymentReceipt.bot_id == c.bot_id, db.PaymentReceipt.status == "pending")
            )).scalar() or 0

        margin_conf = await c.kv("digital:margin", {"type": "percent", "val": 20.0})
        m_str = f"+{margin_conf['val']}%" if margin_conf["type"] == "percent" else f"+${margin_conf['val']}"
        bot_cur = await currency.get_bot_currency(c.bot_id)
        seller_bal = await ledger.get_seller_balance_display(c.owner_id)

        info = (
            f"🎮 <b>{t('إدارة متجر الألعاب والخدمات الرقمية:', 'Games & Digital Management:')}</b>\n"
            f"📦 <b>{t('إجمالي الطلبات المنفذة:', 'Total Orders:')}</b> {total_orders:,}\n"
            f"🧾 <b>{t('إيصالات شحن تنتظر الموافقة:', 'Pending Receipts:')}</b> <b>{pending_rcpts}</b>\n"
            f"📈 <b>{t('هامش الربح العام:', 'Profit Margin:')}</b> <code>{m_str}</code>\n"
            f"💱 <b>{t('عملة البوت:', 'Currency:')}</b> <code>{bot_cur}</code>\n"
            f"💼 <b>{t('رصيدك في الصانع:', 'Maker Balance:')}</b> <code>{seller_bal}</code>"
        )

        rows = [
            [B(t("📈 هامش الربح والأسعار", "📈 Profit Margins"), "t:adm:margin"),
             B(t("📦 إدارة مخزون الأكواد", "📦 Manage Voucher Stock"), "t:adm:stock")],
            [B(t(f"🧾 طلبات الشحن المعلقة ({pending_rcpts})", f"🧾 Pending Receipts ({pending_rcpts})"), "t:adm:rcpts",
               style="warning" if pending_rcpts > 0 else "default"),
             B(t("💳 طرق الدفع والشحن", "💳 Payment Methods"), "t:adm:pay")],
            [B(t("📦 سجل الطلبات والتنفيذ", "📦 Orders & Fulfillment"), "t:adm:orders"),
             B(t("💱 عملة البوت", "💱 Bot Currency"), "t:adm:cur")],
        ]
        return info, rows


TPL = Digital()
