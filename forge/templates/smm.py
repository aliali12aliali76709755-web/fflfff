"""قالب زيادة التفاعل (SMM / Social Media Services):
- خدمات المتابعين، الإعجابات، المشاهدات والتفاعلات لجميع المنصات.
- ربط تلقائي مع مزودي SMM Panels مع التبديل التلقائي عند التعطل (Failover).
- محفظة داخلية وشحن فوري بنجوم تيليجرام أو إيصالات الدفع اليدوي (Zain Cash, Sham Cash, Crypto).
- لوحة تحكم كاملة للبائع: ضبط هوامش الربح، إدارة الخدمات، تخصيص الأسعار، ومراجعة الإيصالات.
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
from ..modules.providers.smm import (
    MOCK_CATALOG,
    PLATFORMS,
    SMMManager,
    StandardSMMAdapter,
    validate_target_url,
)

log = logging.getLogger("forge.smm")


class Smm(Tpl):
    key = "smm"
    emoji = "🚀"
    ar = "زيادة التفاعل"
    en = "Social Media Boost"
    d_ar = "متابعين، لايكات، مشاهدات وتفاعلات لجميع المنصات مع ربط المزودين والشحن الآلي"
    d_en = "Followers, likes, views and reactions for all platforms with provider APIs and instant wallet"
    cats = ("biz",)
    guide_ar = (
        "🚀 <b>قالب زيادة التفاعل وشبكات التواصل (SMM Panel)</b>\n\n"
        "1. <b>الخدمات والأسعار:</b> يحتوي البوت افتراضياً على باقة خدمات جاهزة مع تكاليفها الأصلية. يمكنك تحديد نسبة ربحك (مثلاً +30%) أو تحديد سعر مخصص لكل خدمة.\n"
        "2. <b>مزودو الخدمة (API):</b> البوت يعمل فورياً بكتالوج افتراضي. لربط مزودك الحقيقي، اذهب إلى «🔌 مزودو الـ API» وأدخل رابط الـ API ومفتاحك.\n"
        "3. <b>طرق الدفع:</b> فعّل وسائل الدفع التي تناسب زبائنك (زين كاش، شام كاش، USDT، نجوم تيليجرام).\n"
        "4. <b>طلبات الشحن:</b> عندما يرسل الزبون إشعار دفع، سيصلك إشعار فوري بزرّي «قبول» و«رفض» لشحن رصيده تلقائياً بضغطة زر.\n"
        "5. <b>أكواد الخصم والإحالة:</b> يمكنك إنشاء كوبونات ترويجية وتفعيل نظام الإحالة لمضاعفة مبيعاتك."
    )

    # ───────────────────────────── واجهة المستخدم ─────────────────────────────

    async def home(self, c: Ctx) -> None:
        bal_display = await ledger.get_user_balance_display(c.bot_id, c.uid)
        intro = await c.kv("smm:intro") or c.t(
            "مرحباً بك في بوت خدمات شبكات التواصل الاجتماعي 🚀\nاختر المنصة والخدمة المطلوبة، وسنقوم بتنفيذ طلبك بأعلى سرعة وضمان.",
            "Welcome to the Social Media Services bot 🚀\nPick your platform and service, and your order will be delivered with top speed and guarantee.",
        )
        t = c.t
        text = (
            ui.head(c.brand) +
            f"{esc(intro)}\n\n"
            f"💰 <b>{t('رصيدك الحالي:', 'Your Balance:')}</b> <code>{bal_display}</code>\n"
            f"🆔 <b>{t('معرّف حسابك:', 'Your ID:')}</b> <code>{c.uid}</code>"
        )
        web_url = await c.kv("store:webstore_url", "")
        web_row = [B(t("🌐 متجر الويب", "🌐 Web Store"), url=web_url)] if web_url else []

        rows = [
            [B(t("🚀 تصفح الخدمات والطلب", "🚀 Browse Services & Order"), "t:cats", style="success"),
             B(t("💳 شحن المحفظة", "💳 Top-up Wallet"), "t:wallet")],
            [B(t("📦 طلباتي السابقة", "📦 My Orders"), "t:orders"),
             B(t("🎁 كود خصم", "🎁 Promo Code"), "t:promo")],
            [B(t("👥 كسب رصيد مجاني (الإحالة)", "👥 Earn Free Credit (Referral)"), "t:ref"),
             B(t("ℹ️ مساعدة وشروط", "ℹ️ Help & Terms"), "t:help")],
            [B(t("📞 الدعم الفني والتذاكر", "📞 Support & Tickets"), "t:support"),
             B(t("❓ الأسئلة الشائعة", "❓ FAQ"), "t:faq")],
            web_row if web_row else None,
            c.tail(),
        ]
        await c.edit(text, kb([r for r in rows if r]))

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        act = a[0]
        t = c.t

        # ── تصنيفات المنصات ──
        if act == "cats":
            rows = []
            row = []
            for plat_key, p in PLATFORMS.items():
                row.append(B(f"{p['emoji']} {p['name_ar'] if c.lang == 'ar' else p['name_en']}", f"t:plat:{plat_key}"))
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])
            await c.edit(
                ui.head(t("🌐 اختر المنصة المطلوبة", "🌐 Select Platform")) +
                t("اختر الشبكة التي ترغب بزيادة التفاعل أو المتابعين لها:",
                  "Choose the social platform you want engagement for:"),
                kb(rows)
            )

        # ── خدمات المنصة ──
        elif act == "plat":
            plat_key = a[1]
            p_info = PLATFORMS.get(plat_key, {"name_ar": plat_key, "name_en": plat_key, "emoji": "📱"})
            all_services = await SMMManager.get_services_catalog(c.bot_id)
            services = [s for s in all_services if s.get("platform") == plat_key]

            if not services:
                await c.edit(
                    ui.head(f"{p_info['emoji']} {p_info['name_ar']}") +
                    t("لا توجد خدمات متاحة حالياً لهذه المنصة.", "No services currently available for this platform."),
                    kb([[B(t("⬅️ كل المنصات", "⬅️ All Platforms"), "t:cats")]])
                )
                return

            rows = []
            for s in services:
                price_str = await currency.format_price_for_bot(c.bot_id, s["price_per_1k_usd"])
                s_name = s.get("name_ar" if c.lang == "ar" else "name_en", s["name_ar"])
                label = f"{s_name} — {price_str} / 1k"[:55]
                rows.append([B(label, f"t:svc:{s['id']}")])
            rows.append([B(t("⬅️ كل المنصات", "⬅️ All Platforms"), "t:cats")])

            await c.edit(
                ui.head(f"{p_info['emoji']} {p_info['name_ar']}") +
                t("اختر الخدمة للاطلاع على التفاصيل وطلبها:", "Select a service to view details and order:"),
                kb(rows)
            )

        # ── تفاصيل الخدمة ──
        elif act == "svc":
            sid = a[1]
            all_services = await SMMManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                await c.answer(t("الخدمة غير موجودة", "Service not found"), True)
                return

            plat_key = svc.get("platform", "other")
            p_info = PLATFORMS.get(plat_key, {"emoji": "📱", "name_ar": plat_key, "name_en": plat_key})
            price_str = await currency.format_price_for_bot(c.bot_id, svc["price_per_1k_usd"])
            bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
            refill_str = t("ضمان تعويض ✅" if svc.get("refill") else "بدون تعويض ⚠️",
                           "Guaranteed Refill ✅" if svc.get("refill") else "No Refill ⚠️")
            avg_time = svc.get("avg_time", "فوري")
            desc = svc.get("desc_ar" if c.lang == "ar" else "desc_en", "")

            text = (
                f"{p_info['emoji']} <b>{esc(svc['name_ar'] if c.lang == 'ar' else svc['name_en'])}</b>\n"
                f"{ui.LINE}\n\n"
                f"💵 <b>{t('السعر لكل 1000:', 'Price per 1k:')}</b> {price_str}\n"
                f"📊 <b>{t('الحدود:', 'Limits:')}</b> {t('أدنى:', 'Min:')} {svc['min']} | {t('أقصى:', 'Max:')} {svc['max']:,}\n"
                f"⏱ <b>{t('سرعة البدء التقريبية:', 'Avg start speed:')}</b> {avg_time}\n"
                f"🛡 <b>{t('الضمان:', 'Guarantee:')}</b> {refill_str}\n\n"
                f"📝 <b>{t('الوصف:', 'Description:')}</b>\n{esc(desc)}\n\n"
                f"💰 <b>{t('رصيدك المتوفر:', 'Your Balance:')}</b> {bal_str}"
            )
            rows = [
                [B(t("🛒 طلب هذه الخدمة الآن", "🛒 Order This Service"), f"t:ord_start:{sid}", style="success")],
                [B(t("⬅️ رجوع للخدمات", "⬅️ Back to Services"), f"t:plat:{plat_key}")],
            ]
            await c.edit(text, kb(rows))

        # ── بدء عملية الطلب ──
        elif act == "ord_start":
            sid = a[1]
            all_services = await SMMManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                return

            c.set_state("smm_link", svc_id=sid, plat=svc["platform"])
            ex_url = {
                "instagram": "https://instagram.com/username",
                "tiktok": "https://www.tiktok.com/@username/video/...",
                "telegram": "https://t.me/channel_name",
                "youtube": "https://youtube.com/watch?v=...",
                "x": "https://x.com/username",
                "facebook": "https://facebook.com/...",
            }.get(svc["platform"], "https://...")

            text = (
                ui.head(t("🔗 إدخال الرابط", "🔗 Enter Target Link")) +
                t(
                    f"أرسل رابط الحساب أو المنشور المطلوب للخدمة:\n"
                    f"<b>{esc(svc['name_ar'])}</b>\n\n"
                    f"مثال صحيح: <code>{ex_url}</code>\n\n"
                    f"⚠️ <i>تأكد أن الحساب عام (Public) وليس خاصاً (Private).</i>\n\n"
                    f"/cancel للإلغاء",
                    f"Send the link for the account or post:\n"
                    f"<b>{esc(svc['name_en'])}</b>\n\n"
                    f"Example: <code>{ex_url}</code>\n\n"
                    f"/cancel to abort"
                )
            )
            await c.edit(text, kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:svc:{sid}")]]))

        # ── تأكيد الطلب بعد إدخال الكمية ──
        elif act == "ord_confirm":
            draft = c.x.user_data.get("smm_draft")
            if not draft:
                await c.answer(t("انتهت صلاحية الجلسة، ابدأ من جديد", "Session expired, please start over"), True)
                await self.home(c)
                return
            await self._execute_order(c, draft)

        # ── إلغاء الطلب ──
        elif act == "ord_cancel":
            c.x.user_data.pop("smm_draft", None)
            c.clear_state()
            await c.answer(t("تم إلغاء الطلب", "Order canceled"))
            await self.home(c)

        # ── إدخال كود خصم للطلب ──
        elif act == "ord_promo":
            draft = c.x.user_data.get("smm_draft")
            if not draft:
                await self.home(c)
                return
            c.set_state("smm_order_promo")
            await c.edit(
                ui.head(t("🎟 إدخال كود الخصم", "🎟 Enter Promo Code")) +
                t("أرسل كود الخصم لتطبيقه على هذا الطلب:\n\n/cancel للإلغاء",
                  "Send the promo code to apply to this order:\n\n/cancel to abort"),
                kb([[B(t("⬅️ رجوع لمراجعة الطلب", "⬅️ Back to Review"), "t:ord_back_review")]])
            )

        elif act == "ord_back_review":
            draft = c.x.user_data.get("smm_draft")
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
                f"💰 <b>{t('رصيدك الحالي:', 'Current Balance:')}</b> <code>{bal_str}</code>\n"
                f"🆔 <b>{t('معرّف المحفظة:', 'Wallet ID:')}</b> <code>{c.uid}</code>\n\n"
                f"📜 <b>{t('آخر العمليات:', 'Recent Transactions:')}</b>\n{hist_text}"
            )
            rows = [
                [B(t("➕ شحن الرصيد الآن", "➕ Top-up Balance"), "t:deposit", style="success")],
                [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
            ]
            await c.edit(text, kb(rows))

        # ── طرق الشحن ──
        elif act == "deposit":
            methods = await payments.get_active_payment_methods(c.bot_id)
            rows = []
            for m in methods:
                rows.append([B(f"💳 {m['name']}", f"t:dep_m:{m['id']}")])
            rows.append([B(t("⬅️ المحفظة", "⬅️ Wallet"), "t:wallet")])
            await c.edit(
                ui.head(t("💳 شحن الرصيد", "💳 Top-up Balance")) +
                t("اختر طريقة الدفع المناسبة لك لشحن محفظتك:",
                  "Choose your preferred payment method to top up:"),
                kb(rows)
            )

        # ── اختيار طريقة شحن محددة ──
        elif act == "dep_m":
            mid = a[1]
            methods = await payments.get_active_payment_methods(c.bot_id)
            method = next((m for m in methods if m["id"] == mid), None)
            if not method:
                await c.answer(t("طريقة الدفع غير مفعلة", "Payment method inactive"), True)
                return

            if mid == "telegram_stars":
                # شحن النجوم
                stars_rows = [
                    [B("⭐ 50 Star (~$0.80)", "t:stars_buy:50"), B("⭐ 100 Star (~$1.60)", "t:stars_buy:100")],
                    [B("⭐ 250 Star (~$4.00)", "t:stars_buy:250"), B("⭐ 500 Star (~$8.00)", "t:stars_buy:500")],
                    [B("⭐ 1000 Star (~$16.00)", "t:stars_buy:1000")],
                    [B(t("⬅️ طرق الدفع", "⬅️ Payment Methods"), "t:deposit")],
                ]
                await c.edit(
                    ui.head("⭐ نجوم تيليجرام (Telegram Stars)") +
                    t(
                        "ادفع بنجوم تيليجرام لتحصل على شحن فوري وآلي 100% دون الحاجة لانتظار مراجعة الإدارة!\n\nاختر الباقة المطلوبة:",
                        "Pay with Telegram Stars for 100% instant automatic top-up without waiting!\n\nSelect a package:"
                    ),
                    kb(stars_rows)
                )
                return

            # الدفع اليدوي
            c.set_state("smm_deposit_proof", method_id=mid)
            instr = method.get("instructions", "")
            acc = method.get("account", "")
            text = (
                ui.head(f"💳 {method['name']}") +
                (f"📌 <b>{t('تعليمات التحويل:', 'Instructions:')}</b>\n{esc(instr)}\n\n" if instr else "") +
                (f"🏦 <b>{t('رقم الحساب / المحفظة للتحويل:', 'Account / Address:')}</b>\n<code>{esc(acc)}</code>\n\n" if acc else "") +
                t(
                    "📸 <b>يرجى إرسال لقطة شاشة لإشعار التحويل (أو أرسل رقم العملية والمبلغ نصاً):</b>\n\n"
                    "/cancel للإلغاء",
                    "📸 <b>Please send a screenshot of the transfer proof (or send the transaction ID and amount):</b>\n\n"
                    "/cancel to abort"
                )
            )
            await c.edit(text, kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:deposit")]]))

        # ── شراء النجوم وشحنها ──
        elif act == "stars_buy":
            stars_num = int(a[1])
            # شحن النجوم الآلي عبر محرك المدفوعات المشترك
            ok, tx, new_bal = await payments.process_stars_deposit(c.bot_id, c.uid, stars_num)
            if ok:
                bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
                await c.edit(
                    ui.head(t("✅ تم الشحن بنجاح!", "✅ Top-up Successful!")) +
                    t(
                        f"تم شحن <b>{stars_num} ⭐</b> إلى محفظتك بنجاح!\n\n"
                        f"💰 <b>رصيدك الجديد:</b> <code>{bal_str}</code>",
                        f"Successfully added <b>{stars_num} ⭐</b> to your wallet!\n\n"
                        f"💰 <b>New balance:</b> <code>{bal_str}</code>"
                    ),
                    kb([[B(t("🚀 تصفح الخدمات الآن", "🚀 Browse Services"), "t:cats", style="success")],
                        [B(t("💼 المحفظة", "💼 Wallet"), "t:wallet")]])
                )
            else:
                await c.answer(t("فشل شحن النجوم", "Stars top-up failed"), True)

        # ── سجل الطلبات ──
        elif act == "orders":
            async with db.Session() as s:
                orders = (await s.execute(
                    select(db.ServiceOrder)
                    .where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.user_id == c.uid)
                    .order_by(db.ServiceOrder.created.desc())
                    .limit(10)
                )).scalars().all()

            if not orders:
                await c.edit(
                    ui.head(t("📦 طلباتي", "📦 My Orders")) +
                    t("ليس لديك أي طلبات سابقة بعد.", "You have no previous orders yet."),
                    kb([[B(t("🚀 طلب خدمة جديدة", "🚀 New Order"), "t:cats", style="success")],
                        [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
                )
                return

            rows = []
            st_map = {
                "pending": ("⏳ قيد الانتظار", "⏳ Pending"),
                "processing": ("🔄 قيد المعالجة", "🔄 Processing"),
                "completed": ("✅ مكتمل", "✅ Completed"),
                "canceled": ("❌ ملغى ومسترجع", "❌ Canceled & Refunded"),
                "failed": ("⚠️ تعذر التنفيذ", "⚠️ Failed"),
            }
            lines = []
            for ord_row in orders:
                st_label = st_map.get(ord_row.status, (ord_row.status, ord_row.status))[0 if c.lang == "ar" else 1]
                lines.append(
                    f"▫️ <b>#{ord_row.order_id}</b>\n"
                    f"   {esc(ord_row.service_name)} (×{ord_row.quantity:,})\n"
                    f"   الحالة: <b>{st_label}</b> · السعر: <code>${ord_row.price_user_usd:.2f}</code>\n"
                )
            rows.append([B(t("🚀 طلب جديد", "🚀 New Order"), "t:cats", style="success")])
            rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])

            await c.edit(
                ui.head(t("📦 سجل آخر الطلبات", "📦 Recent Orders")) + "\n".join(lines),
                kb(rows)
            )

        # ── أكواد الخصم الترويجية ──
        elif act == "promo":
            c.set_state("smm_enter_promo")
            await c.edit(
                ui.head(t("🎁 كود خصم أو هدية", "🎁 Promo Code")) +
                t(
                    "أرسل كود الخصم أو الهدية للحصول على رصيد إضافي في محفظتك:\n\n/cancel للإلغاء",
                    "Send your promo code to claim bonus balance:\n\n/cancel to abort"
                ),
                kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:home")]])
            )

        # ── نظام الإحالة ──
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
                    f"Share your referral link with friends and earn rewards:\n\n"
                    f"🎁 <b>Signup reward:</b> {bonus_str}\n"
                    f"📈 <b>Commission:</b> {pct_str}\n\n"
                    f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>"
                )
            )
            rows = [
                [B(t("📤 مشاركة الرابط", "📤 Share Link"), url=f"https://t.me/share/url?url={ref_link}")],
                [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
            ]
            await c.edit(text, kb(rows))

        # ── مساعدة ──
        elif act == "help":
            await c.edit(
                ui.head(t("ℹ️ مساعدة وشروط الخدمة", "ℹ️ Help & Terms")) +
                t(
                    "📌 <b>تعليمات هامة عند الطلب:</b>\n"
                    "1. تأكد من أن حسابك عام (Public) وليس خاصاً طوال فترة التنفيذ.\n"
                    "2. لا تقم بتغيير اسم المستخدم (Username) أو رابط الحساب أثناء معالجة الطلب.\n"
                    "3. سرعة التنفيذ والضمان تعتمد على نوع الخدمة المحددة في الوصف.\n"
                    "4. في حال حدوث أي نقص في الخدمات التي تشمل الضمان، يمكنك التواصل مع الإدارة لطلب التعويض.\n\n"
                    "لأي استفسار تواصل مع إدارة البوت.",
                    "📌 <b>Important Ordering Rules:</b>\n"
                    "1. Keep your profile public during order execution.\n"
                    "2. Do not change your username or link while processing.\n"
                    "3. Speed and refill depend on the service details."
                ),
                kb([[B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )

        # ───────────────────────── لوحة تحكم المالك ─────────────────────────
        elif act == "adm":
            sub = a[1]
            if not c.is_owner:
                await c.answer(t("للمالك فقط", "Owner only"), True)
                return

            # 1. ضبط هامش الربح
            if sub == "margin":
                margin_conf = await c.kv("smm:margin", {"type": "percent", "val": 30.0})
                cur_val = f"{margin_conf['val']}%" if margin_conf["type"] == "percent" else f"${margin_conf['val']}"
                text = (
                    ui.head(t("📈 هامش الربح للخدمات", "📈 Profit Margin")) +
                    f"هامش الربح الحالي المطبق على جميع الخدمات: <b>{cur_val}</b>\n\n"
                    "اختر نسبة سريعة أو اضغط مخصص:"
                )
                rows = [
                    [B("+15%", "t:adm:set_m:percent:15"), B("+30%", "t:adm:set_m:percent:30"), B("+50%", "t:adm:set_m:percent:50")],
                    [B("+75%", "t:adm:set_m:percent:75"), B("+100%", "t:adm:set_m:percent:100")],
                    [B(t("✏️ كتابة نسبة مخصصة", "✏️ Custom Margin"), "t:adm:input_m")],
                    [B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "set_m":
                m_type, m_val = a[2], float(a[3])
                await c.kv_set("smm:margin", {"type": m_type, "val": m_val})
                await c.answer(t(f"تم ضبط الهامش إلى {m_val}%", f"Margin set to {m_val}%"))
                await self.cb(c, ["adm", "margin"])

            elif sub == "input_m":
                c.set_state("smm_adm_margin")
                await c.edit(
                    ui.head(t("📈 كتابة هامش الربح", "📈 Custom Margin")) +
                    t("أرسل نسبة الربح المئوية التي تريد إضافتها على تكلفة المزود (مثال: <code>35</code> لـ 35%):\n\n/cancel للإلغاء",
                      "Send the profit percentage to add on provider cost (e.g. <code>35</code> for 35%):\n\n/cancel to abort"),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:margin")]])
                )

            # 2. إدارة الخدمات وتخصيصها
            elif sub == "svcs":
                plat_filter = a[2] if len(a) > 2 else "instagram"
                all_services = await SMMManager.get_services_catalog(c.bot_id)
                plat_svcs = [s for s in all_services if s.get("platform") == plat_filter]
                overrides = await c.kv("smm:services_override", {})

                rows = []
                # تصفية المنصات
                plat_btns = [B(f"{p['emoji']} {p['name_ar']}", f"t:adm:svcs:{k}") for k, p in PLATFORMS.items()]
                rows.extend(ui.grid(plat_btns, 3))

                # الخدمات
                for s in plat_svcs:
                    is_hidden = overrides.get(s["id"], {}).get("hide", False)
                    status_icon = "🚫 " if is_hidden else "✅ "
                    price_str = await currency.format_price_for_bot(c.bot_id, s["price_per_1k_usd"])
                    btn_text = f"{status_icon}{s['name_ar'][:25]} (${s['price_per_1k_usd']:.2f})"
                    rows.append([B(btn_text, f"t:adm:svc_edit:{s['id']}")])

                rows.append([B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")])
                await c.edit(
                    ui.head(t("📋 إدارة الخدمات وتعديلها", "📋 Manage Services")) +
                    t(f"المنصة الحالية: <b>{PLATFORMS.get(plat_filter, {}).get('name_ar', plat_filter)}</b>\n"
                      f"اضغط على أي خدمة لتعديل سعر بيعها أو إخفائها عن الزبائن:",
                      "Tap any service to customize price or toggle visibility:"),
                    kb(rows)
                )

            elif sub == "svc_edit":
                sid = a[2]
                all_services = await SMMManager.get_services_catalog(c.bot_id)
                svc = next((s for s in all_services if s["id"] == sid), None)
                if not svc:
                    return
                overrides = await c.kv("smm:services_override", {})
                is_hidden = overrides.get(sid, {}).get("hide", False)
                custom_price = overrides.get(sid, {}).get("custom_price_usd")

                text = (
                    ui.head(f"⚙️ {esc(svc['name_ar'])}") +
                    f"المنصة: <b>{svc['platform']}</b>\n"
                    f"التكلفة الأصلية للمزود: <code>${svc.get('base_cost_per_1k', 1.0):.4f}</code> / 1k\n"
                    f"سعر البيع الحالي للزبون: <code>${svc['price_per_1k_usd']:.4f}</code> / 1k\n"
                    f"سعر مخصص محدد؟: <b>{'نعم ($' + str(custom_price) + ')' if custom_price else 'لا (حسب الهامش العام)'}</b>\n"
                    f"الحالة الحالية: <b>{'🚫 مخفية عن الزبائن' if is_hidden else '🟢 ظاهرة للزبائن'}</b>"
                )
                rows = [
                    [B(t("👁 إظهار الخدمة", "👁 Show Service") if is_hidden else t("🚫 إخفاء الخدمة", "🚫 Hide Service"),
                       f"t:adm:svc_toggle:{sid}")],
                    [B(t("💵 تحديد سعر بيع مخصص", "💵 Custom Price"), f"t:adm:svc_price:{sid}")],
                    [B(t("⬅️ قائمة الخدمات", "⬅️ Services List"), f"t:adm:svcs:{svc['platform']}")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "svc_toggle":
                sid = a[2]
                overrides = await c.kv("smm:services_override", {})
                cur = overrides.setdefault(sid, {})
                cur["hide"] = not cur.get("hide", False)
                await c.kv_set("smm:services_override", overrides)
                await c.answer(t("تم تغيير ظهور الخدمة", "Visibility toggled"))
                await self.cb(c, ["adm", "svc_edit", sid])

            elif sub == "svc_price":
                sid = a[2]
                c.set_state("smm_adm_price", sid=sid)
                await c.edit(
                    ui.head(t("💵 تحديد سعر بيع مخصص", "💵 Custom Price")) +
                    t("أرسل سعر البيع النهائي بالدولار لكل 1000 متابع/تفاعل (مثال: <code>1.50</code>):\n\n/cancel للإلغاء",
                      "Send the final retail price in USD per 1,000 (e.g. <code>1.50</code>):\n\n/cancel to abort"),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:adm:svc_edit:{sid}")]]))

            # 3. إعدادات مزودي الـ API
            elif sub == "provs":
                provs = await c.kv("smm:providers", [])
                lines = []
                for i, p in enumerate(provs, 1):
                    lines.append(f"{i}. <b>{esc(p.get('name', 'Custom'))}</b> — URL: <code>{esc(p.get('api_url', ''))}</code>")
                if not lines:
                    lines.append("<i>لم يتم ربط أي مزود مخصص بعد (يتم استخدام المحاكي الافتراضي القياسي).</i>")

                text = (
                    ui.head(t("🔌 مزودو خدمات الـ SMM (API)", "🔌 SMM API Providers")) +
                    "\n".join(lines) + "\n\n"
                    "عند إضافة مزود حقيقي، يتم إرسال الطلبات إليه تلقائياً. يمكنك إضافة أكثر من مزود للتبديل التلقائي في حال تعطل أحدهم (Failover)."
                )
                rows = [
                    [B(t("➕ ربط مزود SMM جديد (v2 API)", "➕ Add SMM Provider"), "t:adm:prov_add", style="success")],
                    [B(t("🧪 اختبار رصيد المزود", "🧪 Test Provider Balance"), "t:adm:prov_test")] if provs else None,
                    [B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "prov_add":
                c.set_state("smm_adm_prov_add")
                text = (
                    ui.head(t("➕ ربط مزود SMM جديد", "➕ Add SMM Provider")) +
                    t(
                        "أرسل بيانات المزود بهذه الصيغة:\n"
                        "<code>الاسم | رابط API | المفتاح السري API Key</code>\n\n"
                        "مثال:\n"
                        "<code>BestPanel | https://bestpanel.com/api/v2 | 98abc4f2898...</code>\n\n"
                        "/cancel للإلغاء",
                        "Send provider details in format:\n"
                        "<code>Name | API URL | API Key</code>\n\n"
                        "/cancel to abort"
                    )
                )
                await c.edit(text, kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:provs")]]))

            elif sub == "prov_test":
                adapters = await SMMManager.get_configured_providers(c.bot_id)
                results = []
                for adp in adapters:
                    try:
                        b = await adp.get_balance()
                        results.append(f"✅ <b>{adp.name}</b>: رصيد المزود = <code>${b:,.2f}</code>")
                    except Exception as e:
                        results.append(f"❌ <b>{adp.name}</b>: تعذر الاتصال ({esc(str(e))[:80]})")
                await c.edit(
                    ui.head(t("🧪 نتائج فحص المزودين", "🧪 Provider Test Results")) + "\n".join(results),
                    kb([[B(t("⬅️ المزودون", "⬅️ Providers"), "t:adm:provs")]])
                )

            # 4. طرق الدفع للبائع
            elif sub == "pay":
                all_methods = await payments.get_payment_methods(c.bot_id)
                rows = []
                for m in all_methods:
                    st_icon = "🟢 مفعل" if m.get("on") else "⚪ متوقف"
                    rows.append([B(f"{m['name']} ({st_icon})", f"t:adm:pay_view:{m['id']}")])
                rows.append([B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")])
                await c.edit(
                    ui.head(t("💳 طرق الدفع والشحن", "💳 Payment Methods")) +
                    t("اضغط على أي طريقة دفع لتفعيلها أو تعديل رقم الحساب وتعليمات التحويل:",
                      "Select any method to configure instructions and toggle:"),
                    kb(rows)
                )

            elif sub == "pay_view":
                mid = a[2]
                all_methods = await payments.get_payment_methods(c.bot_id)
                m = next((x for x in all_methods if x["id"] == mid), None)
                if not m:
                    return
                text = (
                    ui.head(f"⚙️ {esc(m['name'])}") +
                    f"الحالة: <b>{'🟢 مفعل' if m.get('on') else '⚪ متوقف'}</b>\n"
                    f"الحساب / العنوان: <code>{esc(m.get('account', 'غير محدد'))}</code>\n"
                    f"التعليمات: <i>{esc(m.get('instructions', ''))}</i>"
                )
                rows = [
                    [B(t("⚪ إيقاف الطريقة", "⚪ Disable") if m.get("on") else t("🟢 تفعيل الطريقة", "🟢 Enable"),
                       f"t:adm:pay_toggle:{mid}")],
                    [B(t("✏️ تعديل الحساب والتعليمات", "✏️ Edit Account & Info"), f"t:adm:pay_edit:{mid}")],
                    [B(t("⬅️ كل طرق الدفع", "⬅️ All Methods"), "t:adm:pay")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "pay_toggle":
                mid = a[2]
                all_methods = await payments.get_payment_methods(c.bot_id)
                for x in all_methods:
                    if x["id"] == mid:
                        x["on"] = not x.get("on", False)
                await payments.save_payment_methods(c.bot_id, all_methods)
                await c.answer(t("تم التحديث", "Updated"))
                await self.cb(c, ["adm", "pay_view", mid])

            elif sub == "pay_edit":
                mid = a[2]
                c.set_state("smm_adm_pay_edit", mid=mid)
                await c.edit(
                    ui.head(t("✏️ تعديل بيانات طريقة الدفع", "✏️ Edit Payment Method")) +
                    t(
                        "أرسل البيانات بالصيغة التالية:\n"
                        "<code>رقم الحساب أو المحفظة | تعليمات التحويل للزبون</code>\n\n"
                        "مثال:\n"
                        "<code>07701234567 | حوّل المبلغ إلى زين كاش ثم أرسل لقطة الشاشة ورقم العملية</code>\n\n"
                        "/cancel للإلغاء",
                        "Send details in format:\n"
                        "<code>Account number or address | Instructions for customer</code>\n\n"
                        "/cancel to abort"
                    ),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:adm:pay_view:{mid}")]]))

            # 5. مراجعة إيصالات الدفع المعلقة
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
                await c.edit(
                    ui.head(t(f"🧾 إيصالات تنتظر المراجعة ({len(rcpts)})", f"🧾 Pending Receipts ({len(rcpts)})")) +
                    t("اضغط على أي إيصال لعرضه والموافقة على شحن الرصيد أو رفضه:",
                      "Select a receipt to approve top-up or reject:"),
                    kb(rows)
                )

            elif sub == "rcpt_view":
                rcpt_id = a[2]
                r = await payments.get_receipt(rcpt_id)
                if not r:
                    await c.answer(t("الإيصال غير موجود", "Receipt not found"), True)
                    return

                text = (
                    ui.head(f"🧾 إيصال شحن #{r.receipt_id}") +
                    f"👤 <b>الزبون:</b> {esc(r.user_name)} (ID: <code>{r.user_id}</code>)\n"
                    f"💳 <b>طريقة الدفع:</b> {esc(r.method)}\n"
                    f"💵 <b>المبلغ المحول:</b> {r.amount:,.2f} {r.currency} (≈ <code>${r.amount_usd:.2f}</code>)\n"
                    f"📝 <b>بيانات الإثبات:</b>\n{esc(r.proof_text or 'لا يوجد نص')}\n"
                    f"🕒 <b>تاريخ الإرسال:</b> {r.created.strftime('%Y-%m-%d %H:%M')}"
                )
                rows = [
                    [B(t(f"✅ قبول وشحن (${r.amount_usd:.2f})", f"✅ Approve & Top-up (${r.amount_usd:.2f})"),
                       f"t:adm:rcpt_ok:{r.receipt_id}", style="success"),
                     B(t("❌ رفض الإيصال", "❌ Reject"), f"t:adm:rcpt_no:{r.receipt_id}", style="danger")],
                    [B(t("⬅️ كل الإيصالات", "⬅️ All Receipts"), "t:adm:rcpts")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "rcpt_ok":
                rcpt_id = a[2]
                ok, msg, new_bal = await payments.approve_receipt(rcpt_id)
                if ok:
                    await c.answer(t("تمت الموافقة وشحن رصيد الزبون بنجاح! ✅", "Approved & credited successfully! ✅"), True)
                    # إشعار الزبون
                    r = await payments.get_receipt(rcpt_id)
                    if r:
                        try:
                            bal_str = await ledger.get_user_balance_display(c.bot_id, r.user_id)
                            await c.bot.send_message(
                                r.user_id,
                                t(
                                    f"✅ <b>تمت الموافقة على شحن رصيدك!</b>\n\n"
                                    f"المبلغ المضاف: <code>${r.amount_usd:.2f}</code>\n"
                                    f"رصيدك الإجمالي الآن: <code>{bal_str}</code>",
                                    f"✅ <b>Your top-up was approved!</b>\n\n"
                                    f"Credited: <code>${r.amount_usd:.2f}</code>\n"
                                    f"New Balance: <code>{bal_str}</code>"
                                ),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    await self.cb(c, ["adm", "rcpts"])
                else:
                    await c.answer(msg, True)

            elif sub == "rcpt_no":
                rcpt_id = a[2]
                ok, msg = await payments.reject_receipt(rcpt_id, reason="رفض بواسطة الإدارة")
                if ok:
                    await c.answer(t("تم رفض الإيصال", "Receipt rejected"), True)
                    r = await payments.get_receipt(rcpt_id)
                    if r:
                        try:
                            await c.bot.send_message(
                                r.user_id,
                                t("❌ تم رفض إيصال الشحن الخاص بك من قِبل الإدارة. يرجى التواصل مع الدعم للتوضيح.",
                                  "❌ Your top-up receipt was rejected by admin. Please contact support."),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    await self.cb(c, ["adm", "rcpts"])

            # 6. سجل طلبات البوت
            elif sub == "orders":
                async with db.Session() as s:
                    orders = (await s.execute(
                        select(db.ServiceOrder)
                        .where(db.ServiceOrder.bot_id == c.bot_id)
                        .order_by(db.ServiceOrder.created.desc())
                        .limit(15)
                    )).scalars().all()

                lines = []
                for o in orders:
                    lines.append(f"#{o.order_id} | {esc(o.service_name[:20])} | {o.quantity:,} | ${o.price_user_usd:.2f} | <b>{o.status}</b>")
                text = (
                    ui.head(t(f"📦 سجل طلبات البوت ({len(orders)})", f"📦 Bot Orders ({len(orders)})")) +
                    ("\n".join(lines) if lines else t("لا توجد طلبات بعد.", "No orders yet."))
                )
                await c.edit(text, kb([[B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")]]))

            # 7. تغيير عملة البوت
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
                    t(f"العملة المعتمدة حالياً: <b>{cur_curr}</b>\n\nاختر العملة التي تود أن تظهر بها أسعار الخدمات وأرصدة الزبائن:",
                      f"Current currency: <b>{cur_curr}</b>\n\nChoose the currency to display prices and balances:"),
                    kb(grid)
                )

            elif sub == "set_cur":
                new_c = a[2]
                await currency.set_bot_currency(c.bot_id, new_c)
                await c.answer(t(f"تم تغيير عملة البوت إلى {new_c}", f"Currency changed to {new_c}"))
                await self.cb(c, ["adm", "cur"])

            # 8. أكواد الخصم
            elif sub == "promos":
                promos = await promo.get_bot_promos(c.bot_id)
                lines = []
                for code, p in promos.items():
                    val_str = f"{p['val']}%" if p["type"] == "percent" else f"${p['val']}"
                    lines.append(f"🎟 <b>{code}</b>: خصم {val_str} (استخدم: {p.get('used_count', 0)}/{p.get('max_uses', 100)})")

                text = (
                    ui.head(t("🎟 أكواد الخصم الترويجية", "🎟 Promo Codes")) +
                    ("\n".join(lines) if lines else t("لا توجد أكواد خصم معرفة بعد.", "No promo codes configured yet."))
                )
                rows = [
                    [B(t("➕ إنشاء كود خصم جديد", "➕ Create Promo Code"), "t:adm:promo_new", style="success")],
                    [B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "promo_new":
                c.set_state("smm_adm_promo_add")
                await c.edit(
                    ui.head(t("➕ إنشاء كود خصم جديد", "➕ Create Promo Code")) +
                    t(
                        "أرسل بيانات الكود بالصيغة:\n"
                        "<code>الكود | النسبة المئوية للخصم | الحد الأقصى للاستخدام</code>\n\n"
                        "مثال:\n"
                        "<code>VIP20 | 20 | 100</code>\n\n"
                        "/cancel للإلغاء",
                        "Send details in format:\n"
                        "<code>CODE | PERCENT_DISCOUNT | MAX_USES</code>\n\n"
                        "/cancel to abort"
                    ),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:promos")]])
                )

    # ───────────────────────── معالجة الرسائل والإدخال ─────────────────────────

    async def msg(self, c: Ctx) -> bool:  # noqa: C901
        st = c.st
        if not st:
            return False

        if c.text == "/cancel":
            c.clear_state()
            c.x.user_data.pop("smm_draft", None)
            await c.send(c.t("تم الإلغاء.", "Cancelled."), kb([c.home_row()]))
            return True

        k = st.get("k")
        t = c.t

        # 1. إدخال رابط الخدمة
        if k == "smm_link":
            raw_url = c.text.strip()
            plat = st.get("plat", "other")
            sid = st.get("svc_id")

            if not validate_target_url(plat, raw_url):
                await c.send(
                    t(
                        f"⚠️ <b>الرابط غير صالح لمنصة {PLATFORMS.get(plat, {}).get('name_ar', plat)}!</b>\n"
                        "يرجى التأكد من نسخ الرابط بشكل صحيح وإرساله مجدداً.\n\n/cancel للإلغاء",
                        f"⚠️ <b>Invalid link for {plat}!</b> Please verify and re-send.\n\n/cancel to abort"
                    ),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:svc:{sid}")]]))
                return True

            all_services = await SMMManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                c.clear_state()
                return True

            c.set_state("smm_qty", svc_id=sid, link=raw_url, plat=plat)
            await c.send(
                t(
                    f"✅ تم حفظ الرابط بنجاح!\n\n"
                    f"🔢 <b>الآن أدخل الكمية المطلوبة:</b>\n"
                    f"الحد الأدنى: <b>{svc['min']}</b> | الحد الأقصى: <b>{svc['max']:,}</b>\n\n"
                    f"/cancel للإلغاء",
                    f"✅ Link accepted!\n\n"
                    f"🔢 <b>Now enter desired quantity:</b>\n"
                    f"Min: <b>{svc['min']}</b> | Max: <b>{svc['max']:,}</b>\n\n"
                    f"/cancel to abort"
                ),
                kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:svc:{sid}")]])
            )
            return True

        # 2. إدخال الكمية
        elif k == "smm_qty":
            sid = st.get("svc_id")
            link = st.get("link")
            raw_qty = c.text.strip()

            if not raw_qty.isdigit():
                await c.send(t("⚠️ يرجى إدخال أرقام فقط للكمية.", "⚠️ Please enter digits only for quantity."))
                return True

            qty = int(raw_qty)
            all_services = await SMMManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                c.clear_state()
                return True

            if qty < svc["min"] or qty > svc["max"]:
                await c.send(
                    t(f"⚠️ الكمية يجب أن تكون بين {svc['min']} و {svc['max']:,}!",
                      f"⚠️ Quantity must be between {svc['min']} and {svc['max']:,}!")
                )
                return True

            # حساب السعر بالدولار
            total_usd = round((qty / 1000.0) * svc["price_per_1k_usd"], 4)
            c.clear_state()

            draft = {
                "svc_id": sid,
                "svc_name": svc["name_ar" if c.lang == "ar" else "name_en"],
                "platform": svc["platform"],
                "link": link,
                "qty": qty,
                "price_per_1k_usd": svc["price_per_1k_usd"],
                "total_usd": total_usd,
                "discount_usd": 0.0,
                "final_usd": total_usd,
                "promo_code": "",
            }
            c.x.user_data["smm_draft"] = draft
            await self._show_order_review(c, draft)
            return True

        # 3. إدخال كود الخصم أثناء مراجعة الطلب
        elif k == "smm_order_promo":
            code = c.text.strip().upper()
            draft = c.x.user_data.get("smm_draft")
            if not draft:
                c.clear_state()
                await self.home(c)
                return True

            val_ok, discount, msg = await promo.validate_promo(c.bot_id, c.uid, code, draft["total_usd"], draft["svc_id"])
            if not val_ok:
                await c.send(f"⚠️ {msg}\n\n/cancel للإلغاء")
                return True

            draft["discount_usd"] = discount
            draft["final_usd"] = max(round(draft["total_usd"] - discount, 4), 0.0)
            draft["promo_code"] = code
            c.x.user_data["smm_draft"] = draft
            c.clear_state()
            await c.send(f"✅ تم تطبيق كود الخصم بنجاح! خصم: ${discount:.2f}")
            await self._show_order_review(c, draft)
            return True

        # 4. إرسال إثبات الدفع اليدوي
        elif k == "smm_deposit_proof":
            mid = st.get("method_id", "manual")
            all_methods = await payments.get_payment_methods(c.bot_id)
            m_info = next((m for m in all_methods if m["id"] == mid), {"name": mid})
            bot_cur = await currency.get_bot_currency(c.bot_id)

            file_info = c.file_of()
            proof_file_id = file_info[0] if file_info else ""
            proof_txt = c.text or ""

            # استخراج المبلغ إن أمكن من النص أو افتراضي 10$
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

            # إشعار الزبون
            await c.send(
                t(
                    f"✅ <b>تم استلام إثبات الدفع بنجاح!</b>\n\n"
                    f"رقم الإيصال: <code>#{rcpt.receipt_id}</code>\n"
                    f"طلبك قيد المراجعة الآن من قِبل الإدارة وسيتم شحن رصيدك فور التأكيد.",
                    f"✅ <b>Payment proof received!</b>\n\n"
                    f"Receipt: <code>#{rcpt.receipt_id}</code>\n"
                    f"Under review by admin."
                ),
                kb([[B(t("💼 المحفظة", "💼 Wallet"), "t:wallet"), B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )

            # إشعار المالك فوري مع أزرار التحكم
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

        # 5. إدخال كود هدية عام
        elif k == "smm_enter_promo":
            code = c.text.strip().upper()
            val_ok, discount, msg = await promo.validate_promo(c.bot_id, c.uid, code, 10.0)
            if not val_ok:
                await c.send(f"⚠️ {msg}\n\n/cancel للإلغاء")
                return True
            # إضافة رصيد هدية مباشر
            await ledger.credit_user(c.bot_id, c.uid, discount, kind="promo_gift", description=f"هدية كود الخصم {code}")
            await promo.use_promo(c.bot_id, c.uid, code)
            c.clear_state()
            bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
            await c.send(
                t(
                    f"🎉 <b>مبروك! تم تفعيل الكود وإضافة ${discount:.2f} إلى محفظتك!</b>\n"
                    f"رصيدك الإجمالي: <code>{bal_str}</code>",
                    f"🎉 <b>Code redeemed! ${discount:.2f} added to your balance.</b>"
                ),
                kb([[B(t("🚀 تصفح الخدمات", "🚀 Browse Services"), "t:cats", style="success")],
                    [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )
            return True

        # 6. إدخال هامش الربح للبائع
        elif k == "smm_adm_margin":
            val_str = c.text.strip()
            try:
                val = float(val_str)
                await c.kv_set("smm:margin", {"type": "percent", "val": val})
                c.clear_state()
                await c.send(t(f"✅ تم ضبط هامش الربح إلى {val}% بنجاح.", f"✅ Margin set to {val}%."))
                await self.cb(c, ["adm", "margin"])
            except ValueError:
                await c.send(t("⚠️ يرجى إدخال رقم صحيح للنسبة.", "⚠️ Please enter a valid number."))
            return True

        # 7. إدخال سعر مخصص لخدمة
        elif k == "smm_adm_price":
            sid = st.get("sid")
            try:
                price = float(c.text.strip())
                overrides = await c.kv("smm:services_override", {})
                cur = overrides.setdefault(sid, {})
                cur["custom_price_usd"] = price
                await c.kv_set("smm:services_override", overrides)
                c.clear_state()
                await c.send(t(f"✅ تم تحديد سعر البيع إلى ${price:.4f} لكل 1000.", f"✅ Price set to ${price:.4f}."))
                await self.cb(c, ["adm", "svc_edit", sid])
            except ValueError:
                await c.send(t("⚠️ يرجى إدخال رقم صحيح للسعر.", "⚠️ Please enter a valid price."))
            return True

        # 8. إضافة مزود API جديد
        elif k == "smm_adm_prov_add":
            parts = [p.strip() for p in c.text.split("|")]
            if len(parts) < 3 or not parts[1].startswith("http"):
                await c.send(
                    t("⚠️ صيغة غير صحيحة. يرجى إرسال: <code>الاسم | الرابط | المفتاح</code>\n\n/cancel للإلغاء",
                      "⚠️ Invalid format. Send: <code>Name | URL | Key</code>\n\n/cancel to abort")
                )
                return True

            name, api_url, api_key = parts[0], parts[1], parts[2]
            # اختبار المزود سريعاً
            test_adp = StandardSMMAdapter(name, api_url, api_key)
            try:
                bal = await test_adp.get_balance()
            except Exception as e:
                await c.send(f"⚠️ فشل الاتصال بالمزود: {esc(str(e))}\nيرجى التأكد من الرابط والمفتاح والمحاولة مجدداً.")
                return True

            provs = await c.kv("smm:providers", [])
            provs.append({"name": name, "api_url": api_url, "api_key": api_key, "on": True})
            await c.kv_set("smm:providers", provs)
            c.clear_state()
            await c.send(t(f"✅ تم ربط المزود {name} بنجاح! رصيده الحالي لدى الموقع: ${bal:,.2f}",
                           f"✅ Provider {name} added! Balance: ${bal:,.2f}"))
            await self.cb(c, ["adm", "provs"])
            return True

        # 9. تعديل طريقة دفع
        elif k == "smm_adm_pay_edit":
            mid = st.get("mid")
            parts = [p.strip() for p in c.text.split("|")]
            all_methods = await payments.get_payment_methods(c.bot_id)
            for m in all_methods:
                if m["id"] == mid:
                    m["account"] = parts[0]
                    if len(parts) > 1:
                        m["instructions"] = parts[1]
            await payments.save_payment_methods(c.bot_id, all_methods)
            c.clear_state()
            await c.send(t("✅ تم تحديث بيانات طريقة الدفع بنجاح.", "✅ Payment method updated."))
            await self.cb(c, ["adm", "pay_view", mid])
            return True

        # 10. إنشاء كود خصم للبائع
        elif k == "smm_adm_promo_add":
            parts = [p.strip() for p in c.text.split("|")]
            if len(parts) < 2:
                await c.send(t("⚠️ أرسل: <code>الكود | النسبة | الحد الأقصى</code>", "⚠️ Send: <code>CODE | % | MAX</code>"))
                return True
            code = parts[0]
            val = float(parts[1]) if parts[1].replace(".", "").isdigit() else 10.0
            max_u = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 100
            await promo.save_bot_promo(c.bot_id, code, discount_type="percent", value=val, max_uses=max_u)
            c.clear_state()
            await c.send(t(f"✅ تم إنشاء كود الخصم {code} بنسبة {val}% بنجاح.", f"✅ Promo code {code} created."))
            await self.cb(c, ["adm", "promos"])
            return True

        return False

    # ───────────────────────── مراجعة وتنفيذ الطلب ─────────────────────────

    async def _show_order_review(self, c: Ctx, draft: dict[str, Any]) -> None:
        t = c.t
        user_bal_usd = await ledger.get_user_balance_usd(c.bot_id, c.uid)
        user_bal_disp = await ledger.get_user_balance_display(c.bot_id, c.uid)
        final_usd = draft["final_usd"]
        price_disp = await currency.format_price_for_bot(c.bot_id, final_usd)
        plat_info = PLATFORMS.get(draft["platform"], {"emoji": "📱", "name_ar": draft["platform"]})

        discount_line = ""
        if draft.get("discount_usd", 0) > 0:
            disc_disp = await currency.format_price_for_bot(c.bot_id, draft["discount_usd"])
            discount_line = f"🎁 <b>{t('الخصم المطبق:', 'Discount:')}</b> -{disc_disp} (كود: <code>{draft['promo_code']}</code>)\n"

        rem_usd = round(user_bal_usd - final_usd, 4)
        rem_disp = await currency.format_price_for_bot(c.bot_id, max(rem_usd, 0.0))

        is_enough = user_bal_usd >= final_usd

        text = (
            ui.head(t("🧾 تأكيد ومراجعة الطلب", "🧾 Order Review")) +
            f"📌 <b>{t('الخدمة:', 'Service:')}</b> {plat_info['emoji']} {esc(draft['svc_name'])}\n"
            f"🔗 <b>{t('الرابط:', 'Target Link:')}</b> <code>{esc(draft['link'])}</code>\n"
            f"🔢 <b>{t('الكمية:', 'Quantity:')}</b> <b>{draft['qty']:,}</b>\n"
            f"{discount_line}"
            f"💵 <b>{t('المبلغ الإجمالي:', 'Total Price:')}</b> <code>{price_disp}</code>\n"
            f"{ui.LINE}\n"
            f"💰 <b>{t('رصيدك المتوفر:', 'Your Balance:')}</b> {user_bal_disp}\n" +
            (f"📉 <b>{t('الرصيد بعد الخصم:', 'Remaining Balance:')}</b> {rem_disp}\n\n" if is_enough
             else f"\n⚠️ <b>{t('رصيدك الحالي غير كافٍ لإتمام هذا الطلب!', 'Insufficient balance to complete order!')}</b>\n\n")
        )

        rows = []
        if is_enough:
            rows.append([B(t("✅ تأكيد الطلب ودفع الرصيد", "✅ Confirm & Pay"), "t:ord_confirm", style="success")])
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
            await self._show_order_review(c, draft)
            return

        # 1. خصم رصيد المستخدم ذرياً
        ord_key = f"ord_{uuid.uuid4().hex[:12]}"
        ok_debit, tx, new_bal = await ledger.debit_user(
            c.bot_id,
            c.uid,
            final_usd,
            kind="order_smm",
            ref_id=ord_key,
            description=f"طلب {draft['svc_name']} (×{draft['qty']:,})",
        )
        if not ok_debit:
            await c.answer(t("فشل خصم الرصيد، يرجى المحاولة لاحقاً", "Debit failed, please retry"), True)
            return

        # 2. فحص رصيد البائع في الصانع (إذا كان هناك رسم منصة مفروض)
        # إذا تعذر، نسترجع رصيد الزبون فوراً ونعرض رسالة لبقة
        platform_fee_usd = 0.0  # سيتم ربطه مستقبلاً بنظام رسوم المنصة
        if platform_fee_usd > 0:
            ok_seller, _, _ = await ledger.debit_seller(c.owner_id, platform_fee_usd, kind="platform_smm_fee", ref_id=ord_key)
            if not ok_seller:
                # استرجاع رصيد الزبون
                await ledger.credit_user(c.bot_id, c.uid, final_usd, kind="order_refund", ref_id=ord_key, description="استرجاع فوري لتعذر الخدمة")
                await c.edit(
                    ui.head(t("⚠️ الخدمة غير متوفرة مؤقتاً", "⚠️ Service Temporarily Unavailable")) +
                    t("نعتذر منك، الخدمة غير متوفرة في الوقت الحالي. تم حفظ رصيدك كاملاً ولم يُخصم أي شيء.",
                      "We apologize, this service is temporarily unavailable. Your full balance is safe."),
                    kb([[B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
                )
                await c.notify_owner(f"⚠️ تنبيه للبائع: فشل تنفيذ طلب لزبونك #{ord_key} بسبب عدم كفاية رصيدك بالدولار في منصة الصانع!")
                return

        # 3. إرسال الطلب للمزود مع التبديل التلقائي
        disp_ok, prov_order_id, prov_name, prov_cost = await SMMManager.dispatch_order_with_failover(
            c.bot_id,
            draft["svc_id"],
            draft["link"],
            draft["qty"]
        )

        order_status = "processing" if disp_ok else "pending"

        # 4. تسجيل الطلب في قاعدة البيانات
        bot_cur = await currency.get_bot_currency(c.bot_id)
        cur_price = await currency.usd_to_currency(final_usd, bot_cur, bot_id=c.bot_id)
        async with db.Session() as s:
            s_order = db.ServiceOrder(
                order_id=ord_key,
                bot_id=c.bot_id,
                user_id=c.uid,
                tpl_key="smm",
                service_id=draft["svc_id"],
                service_name=draft["svc_name"],
                target=draft["link"],
                quantity=draft["qty"],
                cost_provider_usd=prov_cost,
                cost_platform_usd=platform_fee_usd,
                price_user_usd=final_usd,
                currency=bot_cur,
                price_user_currency=cur_price,
                status=order_status,
                provider_name=prov_name,
                provider_order_id=str(prov_order_id),
                details={"promo": draft.get("promo_code", ""), "discount": draft.get("discount_usd", 0.0)},
            )
            s.add(s_order)
            await s.commit()

        # 5. تسجيل استخدام كود الخصم إن وجد
        if draft.get("promo_code"):
            await promo.use_promo(c.bot_id, c.uid, draft["promo_code"])

        # 6. مكافأة الإحالة للبائع عند أول طلب
        await promo.award_order_commission(c.bot_id, c.uid, final_usd, ord_key)

        # مسح المسودة
        c.x.user_data.pop("smm_draft", None)
        bal_disp = await ledger.get_user_balance_display(c.bot_id, c.uid)

        # إشعار الزبون بنجاح العملية
        text = (
            ui.head(t("🎉 تم استلام طلبك بنجاح!", "🎉 Order Placed Successfully!")) +
            f"🆔 <b>{t('رقم الطلب:', 'Order ID:')}</b> <code>#{ord_key}</code>\n"
            f"📌 <b>{t('الخدمة:', 'Service:')}</b> {esc(draft['svc_name'])}\n"
            f"🔢 <b>{t('الكمية:', 'Quantity:')}</b> <b>{draft['qty']:,}</b>\n"
            f"🔗 <b>{t('الرابط:', 'Target:')}</b> <code>{esc(draft['link'])}</code>\n"
            f"💵 <b>{t('المبلغ المدفوع:', 'Paid Amount:')}</b> <code>${final_usd:.2f}</code>\n"
            f"⏳ <b>{t('الحالة:', 'Status:')}</b> {t('قيد المعالجة السريعة', 'Processing')}\n\n"
            f"💰 <b>{t('رصيدك المتبقي:', 'Remaining Balance:')}</b> <code>{bal_disp}</code>\n\n"
            f"<i>{t('يمكنك متابعة حالة تنفيذ طلبك في أي وقت من قسم «📦 طلباتي».', 'You can track execution status from «My Orders».')}</i>"
        )
        await c.edit(text, kb([
            [B(t("📦 متابعة الطلب", "📦 Track Order"), "t:orders", style="success")],
            [B(t("🚀 طلب خدمة أخرى", "🚀 New Order"), "t:cats")],
            [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
        ]))

        # إشعار المالك
        await c.notify_owner(
            f"📦 <b>طلب جديد #{ord_key}!</b>\n"
            f"الخدمة: {esc(draft['svc_name'])} (×{draft['qty']:,})\n"
            f"الزبون: {esc(c.name)} (ID: <code>{c.uid}</code>)\n"
            f"المبلغ: <code>${final_usd:.2f}</code> | المزود: {prov_name}"
        )

    # ───────────────────────── دعم رابط الإحالة عند الدخول ─────────────────────────

    async def start_param(self, c: Ctx, param: str) -> bool:
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.split("_")[1])
                await promo.check_and_award_signup(c.bot_id, referrer_id, c.uid)
            except Exception as e:
                log.debug("Referral param parsing error: %s", e)
        return False

    # ───────────────────────── لوحة المالك في غرفة التحكم ─────────────────────────

    async def owner(self, c: Ctx) -> tuple[str, list]:
        t = c.t
        # جلب إحصائيات سريعة للبائع
        async with db.Session() as s:
            total_orders = (await s.execute(
                select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == c.bot_id)
            )).scalar() or 0
            pending_rcpts = (await s.execute(
                select(func.count(db.PaymentReceipt.id))
                .where(db.PaymentReceipt.bot_id == c.bot_id, db.PaymentReceipt.status == "pending")
            )).scalar() or 0

        margin_conf = await c.kv("smm:margin", {"type": "percent", "val": 30.0})
        m_str = f"+{margin_conf['val']}%" if margin_conf["type"] == "percent" else f"+${margin_conf['val']}"
        bot_cur = await currency.get_bot_currency(c.bot_id)
        seller_bal = await ledger.get_seller_balance_display(c.owner_id)

        info = (
            f"🚀 <b>{t('إدارة متجر التفاعل (SMM):', 'SMM Store Management:')}</b>\n"
            f"📦 <b>{t('إجمالي الطلبات المنفذة:', 'Total Orders:')}</b> {total_orders:,}\n"
            f"🧾 <b>{t('إيصالات شحن تنتظر الموافقة:', 'Pending Receipts:')}</b> <b>{pending_rcpts}</b>\n"
            f"📈 <b>{t('هامش الربح العام:', 'Profit Margin:')}</b> <code>{m_str}</code>\n"
            f"💱 <b>{t('عملة البوت:', 'Currency:')}</b> <code>{bot_cur}</code>\n"
            f"💼 <b>{t('رصيدك في الصانع:', 'Maker Balance:')}</b> <code>{seller_bal}</code>"
        )

        rows = [
            [B(t("📈 هامش الربح والأسعار", "📈 Profit Margins"), "t:adm:margin"),
             B(t("📋 الخدمات (إخفاء/تعديل)", "📋 Manage Services"), "t:adm:svcs")],
            [B(t("🔌 مزودو الـ API (SMM)", "🔌 API Providers"), "t:adm:provs"),
             B(t("💳 طرق الدفع والشحن", "💳 Payment Methods"), "t:adm:pay")],
            [B(t(f"🧾 طلبات الشحن المعلقة ({pending_rcpts})", f"🧾 Pending Receipts ({pending_rcpts})"), "t:adm:rcpts",
               style="warning" if pending_rcpts > 0 else "default"),
             B(t("📦 سجل الطلبات", "📦 Orders Log"), "t:adm:orders")],
            [B(t("🎟 أكواد الخصم", "🎟 Promo Codes"), "t:adm:promos"),
             B(t("📢 قناة استقبال الطلبات", "📢 Orders Channel"), "t:adm:chan")],
            [B(t("💱 عملة البوت", "💱 Bot Currency"), "t:adm:cur")],
        ]
        return info, rows


TPL = Smm()
