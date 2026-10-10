"""قالب نجوم وتلغرام بريميوم وهدايا تيليجرام (Telegram Stars & Premium):
- شحن فوري لنجوم تيليجرام (Stars) من 50 حتى 10,000+ نجمة.
- تفعيل اشتراكات تيليجرام بريميوم (Telegram Premium) لمدد 3، 6، و12 شهراً باسم المستخدم فقط.
- إرسال الهدايا والحزم للملفات الشخصية.
- محفظة داخلية مع دعم الدفع بنجوم تيليجرام أو الدفع اليدوي (Zain Cash, Sham Cash, Crypto).
- لوحة تحكم كاملة للمالك لهوامش الربح والأسعار ومراجعة الإيصالات.
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
from ..modules.providers.tgstars import (
    TGSTARS_CATALOG,
    TGStarsManager,
    clean_and_validate_username,
)

log = logging.getLogger("forge.tgstars")


class Tgstars(Tpl):
    key = "tgstars"
    emoji = "⭐"
    ar = "نجوم وتلغرام بريميوم"
    en = "Telegram Stars & Premium"
    d_ar = "شحن نجوم تيليجرام واشتراكات بريميوم وهدايا باليوزر فقط مع الدفع الآلي والمحفظة"
    d_en = "Top up Telegram Stars, Premium subscriptions and gifts via username with instant payments"
    cats = ("biz",)
    guide_ar = (
        "⭐ <b>قالب نجوم وتلغرام بريميوم وهدايا تيليجرام</b>\n\n"
        "1. <b>الخدمات والباقات:</b> يتيح البوت لزبائنك شراء نجوم تيليجرام واشتراكات بريميوم وهدايا باسم المستخدم فقط دون أي كلمات مرور.\n"
        "2. <b>الأسعار وهوامش الربح:</b> أسعار التكلفة الأصلية مدخلة افتراضياً، ويمكنك تحديد نسبة ربحك العامة (مثلاً +25%) أو تحديد سعر مخصص لكل باقة.\n"
        "3. <b>طرق الدفع:</b> فعّل وسائل الدفع التي تناسب زبائنك (زين كاش، شام كاش، USDT، نجوم تيليجرام) لشحن محافظهم بسهولة.\n"
        "4. <b>المزودون (API):</b> البوت يعمل فورياً مع المحاكي الافتراضي. لربط مزودك الخارجي، افتح «🔌 مزودو الـ API» وأدخل بياناتك.\n"
        "5. <b>التنفيذ الفوري:</b> الطلبات تُخصم وتُسجل في دفتر الأستاذ ذرياً وتصلك إشعارات فورية بكل طلب."
    )

    # ───────────────────────────── واجهة المستخدم ─────────────────────────────

    async def home(self, c: Ctx) -> None:
        bal_display = await ledger.get_user_balance_display(c.bot_id, c.uid)
        intro = await c.kv("tgstars:intro") or c.t(
            "مرحباً بك في بوت شحن نجوم وتلغرام بريميوم ⭐💎\nاختر الخدمة المطلوبة لشحن حسابك أو إهدائها لأي حساب تيليجرام فورياً وبأمان تام.",
            "Welcome to Telegram Stars & Premium Bot ⭐💎\nTop up your account or gift stars & premium to any username instantly.",
        )
        t = c.t
        text = (
            ui.head(c.brand) +
            f"{esc(intro)}\n\n"
            f"💰 <b>{t('رصيدك الحالي:', 'Your Balance:')}</b> <code>{bal_display}</code>\n"
            f"🆔 <b>{t('معرّف حسابك:', 'Your ID:')}</b> <code>{c.uid}</code>"
        )
        rows = [
            [B(t("⭐ شحن نجوم تيليجرام", "⭐ Telegram Stars"), "t:cat:stars", style="success"),
             B(t("💎 اشتراكات بريميوم", "💎 Telegram Premium"), "t:cat:premium")],
            [B(t("🎁 هدايا تيليجرام", "🎁 Telegram Gifts"), "t:cat:gifts"),
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

        # ── استعراض الأقسام (نجوم / بريميوم / هدايا) ──
        if act == "cat":
            cat_name = a[1]
            all_services = await TGStarsManager.get_services_catalog(c.bot_id)
            services = [s for s in all_services if s.get("category") == cat_name]

            titles = {
                "stars": ("⭐ باقات نجوم تيليجرام (Telegram Stars)", "⭐ Telegram Stars Packages"),
                "premium": ("💎 اشتراكات تيليجرام بريميوم الرسمية", "💎 Official Telegram Premium"),
                "gifts": ("🎁 هدايا وباقات تيليجرام المميزة", "🎁 Telegram Gift Bundles"),
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
                label = f"{s_name} — {price_str}"[:55]
                rows.append([B(label, f"t:svc:{s['id']}")])
            rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])

            await c.edit(
                ui.head(cat_title) +
                t("اختر الباقة المطلوبة لمعرفة التفاصيل وتحديد الحساب المستلم:",
                  "Select a package to view details and specify target username:"),
                kb(rows)
            )

        # ── تفاصيل الباقة ──
        elif act == "svc":
            sid = a[1]
            all_services = await TGStarsManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                await c.answer(t("الباقة غير موجودة", "Package not found"), True)
                return

            price_str = await currency.format_price_for_bot(c.bot_id, svc["price_usd"])
            bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
            desc = svc.get("desc_ar" if c.lang == "ar" else "desc_en", "")

            text = (
                f"<b>{esc(svc['name_ar'] if c.lang == 'ar' else svc['name_en'])}</b>\n"
                f"{ui.LINE}\n\n"
                f"💵 <b>{t('السعر الإجمالي:', 'Total Price:')}</b> {price_str}\n"
                f"⏱ <b>{t('سرعة التفعيل:', 'Activation Speed:')}</b> {svc.get('avg_time', 'فوري')}\n"
                f"🛡 <b>{t('الضمان:', 'Guarantee:')}</b> {t('تفعيل رسمي وآمن 100%', '100% Official & Safe')}\n\n"
                f"📝 <b>{t('الوصف:', 'Description:')}</b>\n{esc(desc)}\n\n"
                f"💰 <b>{t('رصيدك المتوفر:', 'Your Balance:')}</b> {bal_str}"
            )
            rows = [
                [B(t("🛒 طلب وشحن هذه الباقة الآن", "🛒 Order This Package"), f"t:ord_start:{sid}", style="success")],
                [B(t("⬅️ رجوع للباقات", "⬅️ Back to Packages"), f"t:cat:{svc['category']}")],
            ]
            await c.edit(text, kb(rows))

        # ── بدء الطلب واختيار الحساب المستلم ──
        elif act == "ord_start":
            sid = a[1]
            all_services = await TGStarsManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                return

            my_username = c.user.username if c.user and c.user.username else ""
            rows = []
            if my_username:
                rows.append([B(t(f"👤 شحن لحسابي الحالي (@{my_username})", f"👤 Charge my account (@{my_username})"),
                               f"t:ord_target:{sid}:self")])
            rows.append([B(t("🎁 إهداء / شحن لحساب آخر", "🎁 Gift to another username"), f"t:ord_target:{sid}:other")])
            rows.append([B(t("❌ إلغاء", "❌ Cancel"), f"t:svc:{sid}")])

            await c.edit(
                ui.head(t("👤 تحديد الحساب المستلم", "👤 Select Target Account")) +
                t(
                    f"الخدمة المحددة: <b>{esc(svc['name_ar'])}</b>\n\n"
                    "هل تود الشحن لحسابك الخاص أم إهداء الباقة لحساب شخص آخر؟",
                    f"Selected: <b>{esc(svc['name_en'])}</b>\n\n"
                    "Charge your own account or gift to a friend?"
                ),
                kb(rows)
            )

        # ── تحديد المعرف ──
        elif act == "ord_target":
            sid = a[1]
            target_type = a[2]
            all_services = await TGStarsManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                return

            if target_type == "self" and c.user and c.user.username:
                clean_user = f"@{c.user.username}"
                draft = {
                    "svc_id": sid,
                    "svc_name": svc["name_ar" if c.lang == "ar" else "name_en"],
                    "category": svc["category"],
                    "username": clean_user,
                    "price_usd": svc["price_usd"],
                    "discount_usd": 0.0,
                    "final_usd": svc["price_usd"],
                    "promo_code": "",
                }
                c.x.user_data["tgstars_draft"] = draft
                await self._show_order_review(c, draft)
                return

            # إدخال يوزر آخر
            c.set_state("tgstars_target_user", svc_id=sid)
            await c.edit(
                ui.head(t("✍️ إدخال اسم المستخدم (Username)", "✍️ Enter Target Username")) +
                t(
                    "أرسل اسم المستخدم (اليوزر) للحساب المطلوب شحنه:\n"
                    "مثال: <code>@username</code> أو <code>username</code>\n\n"
                    "⚠️ <i>لا نطلب أي كلمة مرور نهائياً، الشحن يتم عبر المعرف فقط.</i>\n\n"
                    "/cancel للإلغاء",
                    "Send the target Telegram username:\n"
                    "Example: <code>@username</code>\n\n"
                    "/cancel to abort"
                ),
                kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:svc:{sid}")]]))

        # ── تأكيد الطلب ──
        elif act == "ord_confirm":
            draft = c.x.user_data.get("tgstars_draft")
            if not draft:
                await c.answer(t("انتهت صلاحية الجلسة، ابدأ من جديد", "Session expired"), True)
                await self.home(c)
                return
            await self._execute_order(c, draft)

        # ── إلغاء الطلب ──
        elif act == "ord_cancel":
            c.x.user_data.pop("tgstars_draft", None)
            c.clear_state()
            await c.answer(t("تم إلغاء الطلب", "Order canceled"))
            await self.home(c)

        # ── إدخال كود خصم للطلب ──
        elif act == "ord_promo":
            draft = c.x.user_data.get("tgstars_draft")
            if not draft:
                await self.home(c)
                return
            c.set_state("tgstars_order_promo")
            await c.edit(
                ui.head(t("🎟 إدخال كود الخصم", "🎟 Enter Promo Code")) +
                t("أرسل كود الخصم لتطبيقه على هذا الطلب:\n\n/cancel للإلغاء",
                  "Send promo code to apply:\n\n/cancel to abort"),
                kb([[B(t("⬅️ رجوع لمراجعة الطلب", "⬅️ Back to Review"), "t:ord_back_review")]])
            )

        elif act == "ord_back_review":
            draft = c.x.user_data.get("tgstars_draft")
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
                t("اختر طريقة الدفع المناسبة لشحن محفظتك:", "Choose your payment method:"),
                kb(rows)
            )

        elif act == "dep_m":
            mid = a[1]
            methods = await payments.get_active_payment_methods(c.bot_id)
            method = next((m for m in methods if m["id"] == mid), None)
            if not method:
                await c.answer(t("طريقة الدفع غير مفعلة", "Inactive payment method"), True)
                return

            if mid == "telegram_stars":
                stars_rows = [
                    [B("⭐ 50 Star (~$0.80)", "t:stars_buy:50"), B("⭐ 100 Star (~$1.60)", "t:stars_buy:100")],
                    [B("⭐ 250 Star (~$4.00)", "t:stars_buy:250"), B("⭐ 500 Star (~$8.00)", "t:stars_buy:500")],
                    [B("⭐ 1000 Star (~$16.00)", "t:stars_buy:1000")],
                    [B(t("⬅️ طرق الدفع", "⬅️ Payment Methods"), "t:deposit")],
                ]
                await c.edit(
                    ui.head("⭐ نجوم تيليجرام (Telegram Stars)") +
                    t(
                        "ادفع بنجوم تيليجرام لتحصل على شحن فوري وآلي 100% دون انتظار!\n\nاختر الباقة المطلوبة:",
                        "Pay with Telegram Stars for 100% instant automatic top-up:\n\nSelect a package:"
                    ),
                    kb(stars_rows)
                )
                return

            c.set_state("tgstars_deposit_proof", method_id=mid)
            instr = method.get("instructions", "")
            acc = method.get("account", "")
            text = (
                ui.head(f"💳 {method['name']}") +
                (f"📌 <b>{t('تعليمات التحويل:', 'Instructions:')}</b>\n{esc(instr)}\n\n" if instr else "") +
                (f"🏦 <b>{t('رقم الحساب / المحفظة للتحويل:', 'Account / Address:')}</b>\n<code>{esc(acc)}</code>\n\n" if acc else "") +
                t(
                    "📸 <b>يرجى إرسال لقطة شاشة لإشعار التحويل (أو أرسل رقم العملية والمبلغ نصاً):</b>\n\n"
                    "/cancel للإلغاء",
                    "📸 <b>Send screenshot or transfer reference:\n\n/cancel to abort</b>"
                )
            )
            await c.edit(text, kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:deposit")]]))

        elif act == "stars_buy":
            stars_num = int(a[1])
            ok, tx, new_bal = await payments.process_stars_deposit(c.bot_id, c.uid, stars_num)
            if ok:
                bal_str = await ledger.get_user_balance_display(c.bot_id, c.uid)
                await c.edit(
                    ui.head(t("✅ تم الشحن بنجاح!", "✅ Top-up Successful!")) +
                    t(
                        f"تم شحن <b>{stars_num} ⭐</b> إلى محفظتك بنجاح!\n\n"
                        f"💰 <b>رصيدك الجديد:</b> <code>{bal_str}</code>",
                        f"Added <b>{stars_num} ⭐</b> to wallet!\nNew balance: <code>{bal_str}</code>"
                    ),
                    kb([[B(t("⭐ طلب الباقات الآن", "⭐ Browse Packages"), "t:cat:stars", style="success")],
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
                    kb([[B(t("⭐ شحن باقة جديدة", "⭐ New Order"), "t:cat:stars", style="success")],
                        [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
                )
                return

            lines = []
            for ord_row in orders:
                lines.append(
                    f"▫️ <b>#{ord_row.order_id}</b>\n"
                    f"   {esc(ord_row.service_name)} ➔ <code>{esc(ord_row.target)}</code>\n"
                    f"   الحالة: <b>{ord_row.status}</b> · السعر: <code>${ord_row.price_user_usd:.2f}</code>\n"
                )
            await c.edit(
                ui.head(t("📦 سجل آخر الطلبات", "📦 Recent Orders")) + "\n".join(lines),
                kb([[B(t("⭐ طلب جديد", "⭐ New Order"), "t:cat:stars", style="success")],
                    [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )

        # ── أكواد الخصم ──
        elif act == "promo":
            c.set_state("tgstars_enter_promo")
            await c.edit(
                ui.head(t("🎁 كود خصم أو هدية", "🎁 Promo Code")) +
                t("أرسل كود الخصم أو الهدية للحصول على رصيد إضافي في محفظتك:\n\n/cancel للإلغاء",
                  "Send promo code to claim bonus balance:\n\n/cancel to abort"),
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

        # ── مساعدة ──
        elif act == "help":
            await c.edit(
                ui.head(t("ℹ️ مساعدة وشروط الخدمة", "ℹ️ Help & Terms")) +
                t(
                    "📌 <b>تعليمات هامة لشحن النجوم والبريميوم:</b>\n"
                    "1. تأكد تماماً من صحة اسم المستخدم (Username) قبل تأكيد الدفع.\n"
                    "2. التفعيل يتم تلقائياً ورسمياً عبر تيليجرام ولا يتطلب أي كلمة مرور نهائياً.\n"
                    "3. النجوم تُضاف فورياً إلى رصيد حساب المستلم ويمكن استخدامها داخل تيليجرام أو التطبيقات المصغرة.\n"
                    "4. اشتراكات بريميوم تصل كرسالة هدية رسمية من تيليجرام وتُفعل مباشرة.",
                    "📌 <b>Important Ordering Rules:</b>\n"
                    "1. Verify the target Telegram username.\n"
                    "2. 100% official Telegram delivery, no password required."
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
                margin_conf = await c.kv("tgstars:margin", {"type": "percent", "val": 25.0})
                cur_val = f"{margin_conf['val']}%" if margin_conf["type"] == "percent" else f"${margin_conf['val']}"
                text = (
                    ui.head(t("📈 هامش الربح لباقات النجوم والبريميوم", "📈 Profit Margin")) +
                    f"هامش الربح الحالي المطبق على جميع الباقات: <b>{cur_val}</b>\n\n"
                    "اختر نسبة سريعة أو اضغط مخصص:"
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
                await c.kv_set("tgstars:margin", {"type": "percent", "val": val})
                await c.answer(t(f"تم ضبط الهامش إلى {val}%", f"Margin set to {val}%"))
                await self.cb(c, ["adm", "margin"])

            elif sub == "input_m":
                c.set_state("tgstars_adm_margin")
                await c.edit(
                    ui.head(t("📈 كتابة هامش الربح", "📈 Custom Margin")) +
                    t("أرسل نسبة الربح المئوية التي تريد إضافتها على تكلفة المزود (مثال: <code>25</code> لـ 25%):\n\n/cancel للإلغاء",
                      "Send percentage profit (e.g. <code>25</code> for 25%):\n\n/cancel to abort"),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:margin")]])
                )

            elif sub == "svcs":
                all_services = await TGStarsManager.get_services_catalog(c.bot_id)
                overrides = await c.kv("tgstars:services_override", {})
                rows = []
                for s in all_services:
                    is_hidden = overrides.get(s["id"], {}).get("hide", False)
                    status_icon = "🚫 " if is_hidden else "✅ "
                    btn_text = f"{status_icon}{s['name_ar'][:25]} (${s['price_usd']:.2f})"
                    rows.append([B(btn_text, f"t:adm:svc_edit:{s['id']}")])
                rows.append([B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")])
                await c.edit(
                    ui.head(t("📋 إدارة باقات النجوم والبريميوم", "📋 Manage Packages")) +
                    t("اضغط على أي باقة لتعديل سعر بيعها أو إخفائها عن الزبائن:",
                      "Tap any package to customize price or toggle visibility:"),
                    kb(rows)
                )

            elif sub == "svc_edit":
                sid = a[2]
                all_services = await TGStarsManager.get_services_catalog(c.bot_id)
                svc = next((s for s in all_services if s["id"] == sid), None)
                if not svc:
                    return
                overrides = await c.kv("tgstars:services_override", {})
                is_hidden = overrides.get(sid, {}).get("hide", False)
                custom_price = overrides.get(sid, {}).get("custom_price_usd")

                text = (
                    ui.head(f"⚙️ {esc(svc['name_ar'])}") +
                    f"التكلفة الأصلية للمزود: <code>${svc.get('base_cost_usd', 1.0):.2f}</code>\n"
                    f"سعر البيع الحالي للزبون: <code>${svc['price_usd']:.2f}</code>\n"
                    f"سعر مخصص محدد؟: <b>{'نعم ($' + str(custom_price) + ')' if custom_price else 'لا (حسب الهامش العام)'}</b>\n"
                    f"الحالة الحالية: <b>{'🚫 مخفية عن الزبائن' if is_hidden else '🟢 ظاهرة للزبائن'}</b>"
                )
                rows = [
                    [B(t("👁 إظهار الباقة", "👁 Show") if is_hidden else t("🚫 إخفاء الباقة", "🚫 Hide"),
                       f"t:adm:svc_toggle:{sid}")],
                    [B(t("💵 تحديد سعر بيع مخصص", "💵 Custom Price"), f"t:adm:svc_price:{sid}")],
                    [B(t("⬅️ قائمة الباقات", "⬅️ Packages List"), "t:adm:svcs")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "svc_toggle":
                sid = a[2]
                overrides = await c.kv("tgstars:services_override", {})
                cur = overrides.setdefault(sid, {})
                cur["hide"] = not cur.get("hide", False)
                await c.kv_set("tgstars:services_override", overrides)
                await c.answer(t("تم تغيير ظهور الباقة", "Toggled"))
                await self.cb(c, ["adm", "svc_edit", sid])

            elif sub == "svc_price":
                sid = a[2]
                c.set_state("tgstars_adm_price", sid=sid)
                await c.edit(
                    ui.head(t("💵 تحديد سعر بيع مخصص", "💵 Custom Price")) +
                    t("أرسل سعر البيع النهائي بالدولار لهذه الباقة (مثال: <code>2.20</code>):\n\n/cancel للإلغاء",
                      "Send the final retail price in USD:\n\n/cancel to abort"),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:adm:svc_edit:{sid}")]]))

            # مزودو API
            elif sub == "provs":
                provs = await c.kv("tgstars:providers", [])
                lines = []
                for i, p in enumerate(provs, 1):
                    lines.append(f"{i}. <b>{esc(p.get('name', 'Custom'))}</b> — URL: <code>{esc(p.get('api_url', ''))}</code>")
                if not lines:
                    lines.append("<i>يتم استخدام محاكي النجوم الافتراضي القياسي (جاهز للتجربة فوراً).</i>")

                text = (
                    ui.head(t("🔌 مزودو خدمات النجوم والبريميوم", "🔌 API Providers")) +
                    "\n".join(lines) + "\n\n"
                    "عند إضافة مزود حقيقي، يتم توجيه طلبات النجوم والبريميوم إليه آلياً."
                )
                rows = [
                    [B(t("➕ ربط مزود جديد", "➕ Add Provider"), "t:adm:prov_add", style="success")],
                    [B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "prov_add":
                c.set_state("tgstars_adm_prov_add")
                await c.edit(
                    ui.head(t("➕ ربط مزود جديد", "➕ Add Provider")) +
                    t("أرسل: <code>الاسم | رابط API | المفتاح السري</code>\n\n/cancel للإلغاء",
                      "Send: <code>Name | API URL | API Key</code>\n\n/cancel to abort"),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:provs")]])
                )

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
                await c.edit(
                    ui.head(t(f"🧾 إيصالات تنتظر المراجعة ({len(rcpts)})", f"🧾 Pending Receipts ({len(rcpts)})")),
                    kb(rows)
                )

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

            # سجل الطلبات
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
                    lines.append(f"#{o.order_id} | {esc(o.service_name[:20])} | {esc(o.target)} | ${o.price_user_usd:.2f} | <b>{o.status}</b>")
                text = (
                    ui.head(t(f"📦 سجل طلبات البوت ({len(orders)})", f"📦 Bot Orders ({len(orders)})")) +
                    ("\n".join(lines) if lines else t("لا توجد طلبات بعد.", "No orders yet."))
                )
                await c.edit(text, kb([[B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")]]))

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
            c.x.user_data.pop("tgstars_draft", None)
            await c.send(c.t("تم الإلغاء.", "Cancelled."), kb([c.home_row()]))
            return True

        k = st.get("k")
        t = c.t

        # 1. إدخال اسم المستخدم المستلم
        if k == "tgstars_target_user":
            raw_user = c.text.strip()
            sid = st.get("svc_id")

            ok_u, clean_username = clean_and_validate_username(raw_user)
            if not ok_u:
                await c.send(
                    t(
                        "⚠️ <b>اسم المستخدم غير صالح!</b>\n"
                        "يرجى التأكد من كتابة اليوزر بشكل صحيح (بين 5 و 32 حرفاً أو رقماً، مثال: <code>@username</code>).\n\n"
                        "/cancel للإلغاء",
                        "⚠️ <b>Invalid Telegram username!</b> Please re-enter (e.g. <code>@username</code>).\n\n/cancel to abort"
                    ),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), f"t:svc:{sid}")]]))
                return True

            all_services = await TGStarsManager.get_services_catalog(c.bot_id)
            svc = next((s for s in all_services if s["id"] == sid), None)
            if not svc:
                c.clear_state()
                return True

            c.clear_state()
            draft = {
                "svc_id": sid,
                "svc_name": svc["name_ar" if c.lang == "ar" else "name_en"],
                "category": svc["category"],
                "username": clean_username,
                "price_usd": svc["price_usd"],
                "discount_usd": 0.0,
                "final_usd": svc["price_usd"],
                "promo_code": "",
            }
            c.x.user_data["tgstars_draft"] = draft
            await self._show_order_review(c, draft)
            return True

        # 2. إدخال كود خصم أثناء مراجعة الطلب
        elif k == "tgstars_order_promo":
            code = c.text.strip().upper()
            draft = c.x.user_data.get("tgstars_draft")
            if not draft:
                c.clear_state()
                await self.home(c)
                return True

            val_ok, discount, msg = await promo.validate_promo(c.bot_id, c.uid, code, draft["price_usd"], draft["svc_id"])
            if not val_ok:
                await c.send(f"⚠️ {msg}\n\n/cancel للإلغاء")
                return True

            draft["discount_usd"] = discount
            draft["final_usd"] = max(round(draft["price_usd"] - discount, 2), 0.0)
            draft["promo_code"] = code
            c.x.user_data["tgstars_draft"] = draft
            c.clear_state()
            await c.send(f"✅ تم تطبيق كود الخصم بنجاح! خصم: ${discount:.2f}")
            await self._show_order_review(c, draft)
            return True

        # 3. إرسال إثبات الدفع اليدوي
        elif k == "tgstars_deposit_proof":
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
        elif k == "tgstars_enter_promo":
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
                kb([[B(t("⭐ شحن النجوم", "⭐ Stars"), "t:cat:stars", style="success")],
                    [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )
            return True

        # 5. هامش المالك
        elif k == "tgstars_adm_margin":
            try:
                val = float(c.text.strip())
                await c.kv_set("tgstars:margin", {"type": "percent", "val": val})
                c.clear_state()
                await c.send(t(f"✅ تم ضبط الهامش إلى {val}%.", f"✅ Margin set to {val}%."))
                await self.cb(c, ["adm", "margin"])
            except ValueError:
                await c.send(t("⚠️ أدخل رقماً صحيحاً.", "⚠️ Enter valid number."))
            return True

        # 6. سعر مخصص
        elif k == "tgstars_adm_price":
            sid = st.get("sid")
            try:
                price = float(c.text.strip())
                overrides = await c.kv("tgstars:services_override", {})
                cur = overrides.setdefault(sid, {})
                cur["custom_price_usd"] = price
                await c.kv_set("tgstars:services_override", overrides)
                c.clear_state()
                await c.send(t(f"✅ تم تحديد سعر البيع إلى ${price:.2f}.", f"✅ Price set to ${price:.2f}."))
                await self.cb(c, ["adm", "svc_edit", sid])
            except ValueError:
                await c.send(t("⚠️ أدخل رقماً صحيحاً.", "⚠️ Enter valid number."))
            return True

        # 7. ربط مزود جديد
        elif k == "tgstars_adm_prov_add":
            parts = [p.strip() for p in c.text.split("|")]
            if len(parts) < 3 or not parts[1].startswith("http"):
                await c.send("⚠️ الصيغة المطلوبة: <code>الاسم | الرابط | المفتاح</code>\n\n/cancel للإلغاء")
                return True
            provs = await c.kv("tgstars:providers", [])
            provs.append({"name": parts[0], "api_url": parts[1], "api_key": parts[2], "on": True})
            await c.kv_set("tgstars:providers", provs)
            c.clear_state()
            await c.send(t(f"✅ تم إضافة المزود {parts[0]} بنجاح.", f"✅ Provider {parts[0]} added."))
            await self.cb(c, ["adm", "provs"])
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
            ui.head(t("🧾 تأكيد ومراجعة طلب الشحن", "🧾 Order Review")) +
            f"📌 <b>{t('الباقة المختارة:', 'Selected Package:')}</b> {esc(draft['svc_name'])}\n"
            f"👤 <b>{t('المعرف المستلم:', 'Target Username:')}</b> <code>{esc(draft['username'])}</code>\n"
            f"{discount_line}"
            f"💵 <b>{t('المبلغ المطلوب:', 'Required Price:')}</b> <code>{price_disp}</code>\n"
            f"{ui.LINE}\n"
            f"💰 <b>{t('رصيدك المتوفر:', 'Your Balance:')}</b> {user_bal_disp}\n" +
            (f"📉 <b>{t('الرصيد بعد الخصم:', 'Remaining Balance:')}</b> {rem_disp}\n\n" if is_enough
             else f"\n⚠️ <b>{t('رصيدك الحالي غير كافٍ لإتمام هذا الطلب!', 'Insufficient balance to complete order!')}</b>\n\n")
        )

        rows = []
        if is_enough:
            rows.append([B(t("✅ تأكيد الشحن وخصم الرصيد", "✅ Confirm & Pay"), "t:ord_confirm", style="success")])
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

        ord_key = f"ord_tg_{uuid.uuid4().hex[:12]}"
        ok_debit, tx, new_bal = await ledger.debit_user(
            c.bot_id,
            c.uid,
            final_usd,
            kind="order_tgstars",
            ref_id=ord_key,
            description=f"شحن {draft['svc_name']} للحساب {draft['username']}",
        )
        if not ok_debit:
            await c.answer(t("فشل خصم الرصيد", "Debit failed"), True)
            return

        disp_ok, prov_order_id, prov_name, prov_cost = await TGStarsManager.dispatch_order_with_failover(
            c.bot_id,
            draft["svc_id"],
            draft["username"],
            1
        )
        order_status = "processing" if disp_ok else "pending"

        bot_cur = await currency.get_bot_currency(c.bot_id)
        cur_price = await currency.usd_to_currency(final_usd, bot_cur, bot_id=c.bot_id)
        async with db.Session() as s:
            s_order = db.ServiceOrder(
                order_id=ord_key,
                bot_id=c.bot_id,
                user_id=c.uid,
                tpl_key="tgstars",
                service_id=draft["svc_id"],
                service_name=draft["svc_name"],
                target=draft["username"],
                quantity=1,
                cost_provider_usd=prov_cost,
                cost_platform_usd=0.0,
                price_user_usd=final_usd,
                currency=bot_cur,
                price_user_currency=cur_price,
                status=order_status,
                provider_name=prov_name,
                provider_order_id=str(prov_order_id),
                details={"category": draft.get("category", "stars"), "promo": draft.get("promo_code", "")},
            )
            s.add(s_order)
            await s.commit()

        if draft.get("promo_code"):
            await promo.use_promo(c.bot_id, c.uid, draft["promo_code"])

        await promo.award_order_commission(c.bot_id, c.uid, final_usd, ord_key)

        c.x.user_data.pop("tgstars_draft", None)
        bal_disp = await ledger.get_user_balance_display(c.bot_id, c.uid)

        text = (
            ui.head(t("🎉 تم إرسال طلب الشحن بنجاح!", "🎉 Order Sent Successfully!")) +
            f"🆔 <b>{t('رقم الطلب:', 'Order ID:')}</b> <code>#{ord_key}</code>\n"
            f"📌 <b>{t('الباقة:', 'Package:')}</b> {esc(draft['svc_name'])}\n"
            f"👤 <b>{t('المعرف المستلم:', 'Target:')}</b> <code>{esc(draft['username'])}</code>\n"
            f"💵 <b>{t('المبلغ المدفوع:', 'Paid Amount:')}</b> <code>${final_usd:.2f}</code>\n"
            f"⏳ <b>{t('الحالة:', 'Status:')}</b> {t('قيد الإرسال والتفعيل السريع', 'Processing')}\n\n"
            f"💰 <b>{t('رصيدك المتبقي:', 'Remaining Balance:')}</b> <code>{bal_disp}</code>\n\n"
            f"<i>{t('يمكنك متابعة حالة الطلب في أي وقت من قسم «📦 طلباتي».', 'Track your order from «My Orders».')}</i>"
        )
        await c.edit(text, kb([
            [B(t("📦 متابعة الطلب", "📦 Track Order"), "t:orders", style="success")],
            [B(t("⭐ شحن باقة أخرى", "⭐ New Order"), "t:cat:stars")],
            [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
        ]))

        await c.notify_owner(
            f"⭐ <b>طلب نجوم/بريميوم جديد #{ord_key}!</b>\n"
            f"الباقة: {esc(draft['svc_name'])}\n"
            f"المستلم: <code>{esc(draft['username'])}</code>\n"
            f"الزبون: {esc(c.name)} (ID: <code>{c.uid}</code>)\n"
            f"المبلغ: <code>${final_usd:.2f}</code> | المزود: {prov_name}"
        )

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
                select(func.count(db.ServiceOrder.id)).where(db.ServiceOrder.bot_id == c.bot_id)
            )).scalar() or 0
            pending_rcpts = (await s.execute(
                select(func.count(db.PaymentReceipt.id))
                .where(db.PaymentReceipt.bot_id == c.bot_id, db.PaymentReceipt.status == "pending")
            )).scalar() or 0

        margin_conf = await c.kv("tgstars:margin", {"type": "percent", "val": 25.0})
        m_str = f"+{margin_conf['val']}%" if margin_conf["type"] == "percent" else f"+${margin_conf['val']}"
        bot_cur = await currency.get_bot_currency(c.bot_id)
        seller_bal = await ledger.get_seller_balance_display(c.owner_id)

        info = (
            f"⭐ <b>{t('إدارة متجر النجوم والبريميوم:', 'Stars & Premium Management:')}</b>\n"
            f"📦 <b>{t('إجمالي الطلبات المنفذة:', 'Total Orders:')}</b> {total_orders:,}\n"
            f"🧾 <b>{t('إيصالات شحن تنتظر الموافقة:', 'Pending Receipts:')}</b> <b>{pending_rcpts}</b>\n"
            f"📈 <b>{t('هامش الربح العام:', 'Profit Margin:')}</b> <code>{m_str}</code>\n"
            f"💱 <b>{t('عملة البوت:', 'Currency:')}</b> <code>{bot_cur}</code>\n"
            f"💼 <b>{t('رصيدك في الصانع:', 'Maker Balance:')}</b> <code>{seller_bal}</code>"
        )

        rows = [
            [B(t("📈 هامش الربح والأسعار", "📈 Profit Margins"), "t:adm:margin"),
             B(t("📋 باقات النجوم والبريميوم", "📋 Manage Packages"), "t:adm:svcs")],
            [B(t("🔌 مزودو الـ API", "🔌 API Providers"), "t:adm:provs"),
             B(t("💳 طرق الدفع والشحن", "💳 Payment Methods"), "t:adm:pay")],
            [B(t(f"🧾 طلبات الشحن المعلقة ({pending_rcpts})", f"🧾 Pending Receipts ({pending_rcpts})"), "t:adm:rcpts",
               style="warning" if pending_rcpts > 0 else "default"),
             B(t("📦 سجل الطلبات", "📦 Orders Log"), "t:adm:orders")],
            [B(t("🎟 أكواد الخصم", "🎟 Promo Codes"), "t:adm:promos"),
             B(t("💱 عملة البوت", "💱 Bot Currency"), "t:adm:cur")],
        ]
        return info, rows


TPL = Tgstars()
