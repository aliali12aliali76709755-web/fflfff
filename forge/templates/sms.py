"""قالب أرقام التفعيل الافتراضية (SMS Virtual Numbers):
- اختيار الدولة والتطبيق (Telegram, WhatsApp, Google, TikTok, X).
- شحن الرصيد بالمحفظة أو نجوم تيليجرام أو الدفع اليدوي.
- جلب الرقم المخصص مع مؤقت العد التنازلي.
- زر فحص واستقبال كود التفعيل فورياً.
- زر إلغاء فوري واسترجاع الرصيد كاملاً وتلقائياً في حال عدم وصول الكود.
- لوحة تحكم كاملة للبائع لضبط الهامش والأسعار وربط المزودين.
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
from ..modules.providers.sms import (
    SMS_APPS,
    SMS_COUNTRIES,
    SMSManager,
)

log = logging.getLogger("forge.sms")


class Sms(Tpl):
    key = "sms"
    emoji = "📱"
    ar = "أرقام التفعيل"
    en = "SMS Virtual Numbers"
    d_ar = "أرقام وهمية لتفعيل تلغرام وواتساب والتطبيقات مع استرجاع تلقائي عند تعذر الكود"
    d_en = "Virtual numbers for Telegram, WhatsApp and apps with auto-refund if SMS fails"
    cats = ("biz",)
    guide_ar = (
        "📱 <b>قالب أرقام التفعيل الافتراضية (SMS Virtual Numbers)</b>\n\n"
        "1. <b>استئجار الأرقام:</b> يختار الزبون الدولة والتطبيق، ويحصل على رقم فوري لتفعيل الحساب.\n"
        "2. <b>الاسترجاع التلقائي الآمن:</b> إذا لم يصل كود الـ SMS، يستطيع الزبون الضغط على «إلغاء واسترجاع» ليعود رصيده لمحفظته فوراً وذرياً.\n"
        "3. <b>المزودون (API):</b> متوافق مع بروتوكول SMS-Activate و 5SIM و SMSHub العالمي. يمكنك ربط مزودك الحقيقي أو ترك المحاكي الافتراضي للتجربة.\n"
        "4. <b>هامش الربح:</b> يمكنك تحديد نسبة ربحك العامة (مثلاً +35%) وتعديل أسعار أي دولة وتطبيق."
    )

    # ───────────────────────────── واجهة المستخدم ─────────────────────────────

    async def home(self, c: Ctx) -> None:
        bal_display = await ledger.get_user_balance_display(c.bot_id, c.uid)
        intro = await c.kv("sms:intro") or c.t(
            "مرحباً بك في بوت أرقام التفعيل الافتراضية 📱\nاحصل على أرقام جاهزة ومضمونة لتفعيل تيليجرام، واتساب، وجميع التطبيقات، مع استرجاع فوري للرصيد إذا لم يصل الكود.",
            "Welcome to SMS Virtual Numbers Bot 📱\nGet temporary numbers for Telegram, WhatsApp & apps with instant auto-refund if SMS is not received.",
        )
        t = c.t
        text = (
            ui.head(c.brand) +
            f"{esc(intro)}\n\n"
            f"💰 <b>{t('رصيدك الحالي:', 'Your Balance:')}</b> <code>{bal_display}</code>\n"
            f"🆔 <b>{t('معرّف حسابك:', 'Your ID:')}</b> <code>{c.uid}</code>"
        )
        rows = [
            [B(t("📱 طلب رقم تفعيل جديد", "📱 Rent New Number"), "t:countries", style="success"),
             B(t("💳 شحن المحفظة", "💳 Top-up Wallet"), "t:wallet")],
            [B(t("🔢 أرقامي النشطة والكود", "🔢 Active Numbers & Code"), "t:active"),
             B(t("📦 سجل أرقامي السابقة", "📦 Number History"), "t:orders")],
            [B(t("🎁 كود خصم", "🎁 Promo Code"), "t:promo"),
             B(t("👥 كسب رصيد مجاني (الإحالة)", "👥 Earn Credit (Referral)"), "t:ref")],
            [B(t("ℹ️ مساعدة وشروط الاستخدام", "ℹ️ Help & Terms"), "t:help")],
            c.tail(),
        ]
        await c.edit(text, kb(rows))

    async def cb(self, c: Ctx, a: list[str]) -> None:  # noqa: C901
        act = a[0]
        t = c.t

        # ── اختيار الدولة ──
        if act == "countries":
            rows = []
            btn_list = []
            for c_code, c_info in SMS_COUNTRIES.items():
                btn_list.append(B(f"{c_info['flag']} {c_info['name_ar'] if c.lang == 'ar' else c_info['name_en']}", f"t:country:{c_code}"))
            rows.extend(ui.grid(btn_list, 2))
            rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])

            await c.edit(
                ui.head(t("🌍 اختر الدولة المطلوبة", "🌍 Select Country")) +
                t("اختر الدولة التي ترغب بالحصول على رقم تفعيل تابع لها:",
                  "Choose the country for your virtual number:"),
                kb(rows)
            )

        # ── اختيار التطبيق للدولة ──
        elif act == "country":
            c_code = a[1]
            c_info = SMS_COUNTRIES.get(c_code, {"name_ar": c_code, "name_en": c_code, "flag": "🌐"})

            rows = []
            for app_code, a_info in SMS_APPS.items():
                price_usd = await SMSManager.calculate_number_price(c.bot_id, c_code, app_code)
                price_disp = await currency.format_price_for_bot(c.bot_id, price_usd)
                app_name = a_info["name_ar"] if c.lang == "ar" else a_info["name_en"]
                label = f"{a_info['emoji']} {app_name} — {price_disp}"
                rows.append([B(label, f"t:rent_prompt:{c_code}:{app_code}")])
            rows.append([B(t("⬅️ الدول", "⬅️ Countries"), "t:countries")])

            await c.edit(
                ui.head(f"{c_info['flag']} {c_info['name_ar']}") +
                t("اختر التطبيق أو الخدمة المطلوب استلام كود التفعيل لها:",
                  "Select the application to activate:"),
                kb(rows)
            )

        # ── مراجعة وتأكيد طلب الرقم ──
        elif act == "rent_prompt":
            c_code = a[1]
            app_code = a[2]
            c_info = SMS_COUNTRIES.get(c_code, {"name_ar": c_code, "flag": "🌐"})
            a_info = SMS_APPS.get(app_code, {"name_ar": app_code, "emoji": "📱"})

            price_usd = await SMSManager.calculate_number_price(c.bot_id, c_code, app_code)
            price_disp = await currency.format_price_for_bot(c.bot_id, price_usd)
            user_bal_usd = await ledger.get_user_balance_usd(c.bot_id, c.uid)
            user_bal_disp = await ledger.get_user_balance_display(c.bot_id, c.uid)
            is_enough = user_bal_usd >= price_usd

            text = (
                ui.head(t("🧾 تأكيد طلب رقم التفعيل", "🧾 Confirm Number Rental")) +
                f"🌍 <b>{t('الدولة:', 'Country:')}</b> {c_info['flag']} {c_info['name_ar']}\n"
                f"📱 <b>{t('التطبيق:', 'App:')}</b> {a_info['emoji']} {a_info['name_ar']}\n"
                f"💵 <b>{t('سعر الرقم:', 'Price:')}</b> <code>{price_disp}</code>\n"
                f"⏱ <b>{t('مدة انتظار الكود:', 'SMS Timeout:')}</b> 20 دقيقة\n\n"
                f"🛡 <b>{t('ضمان الاسترجاع التلقائي:', 'Guarantee:')}</b>\n"
                f"<i>{t('إذا لم يصلك كود الـ SMS لأي سبب، يمكنك الضغط على زر «إلغاء واسترجاع» ليعود رصيدك كاملاً لمحفظتك فوراً دون أي نقص.', 'If no SMS is received, you can cancel anytime for a 100% full instant refund.')}</i>\n\n"
                f"{ui.LINE}\n"
                f"💰 <b>{t('رصيدك الحالي:', 'Your Balance:')}</b> {user_bal_disp}\n" +
                ("" if is_enough else f"\n⚠️ <b>{t('رصيدك غير كافٍ لإتمام الطلب!', 'Insufficient balance!')}</b>\n")
            )
            rows = []
            if is_enough:
                rows.append([B(t("✅ تأكيد واستئجار الرقم الآن", "✅ Confirm & Rent Number"),
                               f"t:do_rent:{c_code}:{app_code}", style="success")])
            else:
                rows.append([B(t("💳 شحن المحفظة الآن", "💳 Top-up Balance Now"), "t:deposit", style="success")])
            rows.append([B(t("⬅️ رجوع للتطبيقات", "⬅️ Back to Apps"), f"t:country:{c_code}")])

            await c.edit(text, kb(rows))

        # ── استئجار الرقم وتنفيذه ──
        elif act == "do_rent":
            c_code = a[1]
            app_code = a[2]
            await self._execute_rent_number(c, c_code, app_code)

        # ── فحص كود التفعيل للرقم ──
        elif act == "check_sms":
            ord_id = a[1]
            await self._check_sms_order(c, ord_id)

        # ── إلغاء الرقم واسترجاع الرصيد ──
        elif act == "cancel_refund":
            ord_id = a[1]
            ok, msg, new_bal = await SMSManager.cancel_number_and_refund(c.bot_id, c.uid, ord_id, reason="إلغاء بطلب الزبون")
            if ok:
                bal_disp = await ledger.get_user_balance_display(c.bot_id, c.uid)
                await c.edit(
                    ui.head(t("✅ تم الإلغاء واسترجاع الرصيد بنجاح!", "✅ Canceled & Refunded!")) +
                    t(
                        f"تم إلغاء الرقم وإعادة المبلغ كاملاً إلى محفظتك بنجاح!\n\n"
                        f"💰 <b>رصيدك الحالي:</b> <code>{bal_disp}</code>",
                        f"Order canceled and full amount refunded to your balance!\n\n"
                        f"💰 <b>Current Balance:</b> <code>{bal_disp}</code>"
                    ),
                    kb([[B(t("📱 طلب رقم جديد", "📱 Rent New Number"), "t:countries", style="success")],
                        [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
                )
            else:
                await c.answer(msg, True)

        # ── الأرقام النشطة حالياً ──
        elif act == "active":
            async with db.Session() as s:
                orders = (await s.execute(
                    select(db.ServiceOrder)
                    .where(db.ServiceOrder.bot_id == c.bot_id,
                           db.ServiceOrder.user_id == c.uid,
                           db.ServiceOrder.tpl_key == "sms",
                           db.ServiceOrder.status == "waiting_sms")
                    .order_by(db.ServiceOrder.created.desc())
                )).scalars().all()

            if not orders:
                await c.edit(
                    ui.head(t("🔢 الأرقام النشطة", "🔢 Active Numbers")) +
                    t("لا يوجد لديك أي رقم نشط بانتظار الكود حالياً.", "No active numbers awaiting SMS."),
                    kb([[B(t("📱 طلب رقم تفعيل جديد", "📱 Rent Number"), "t:countries", style="success")],
                        [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
                )
                return

            rows = []
            for ord_row in orders:
                rows.append([B(f"📱 {ord_row.target} ({ord_row.service_name})", f"t:view_num:{ord_row.order_id}")])
            rows.append([B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")])

            await c.edit(
                ui.head(t(f"🔢 أرقامك النشطة ({len(orders)})", f"🔢 Active Numbers ({len(orders)})")) +
                t("اختر الرقم لعرضه واستقبال الكود أو إلغائه:", "Select a number to check code or cancel:"),
                kb(rows)
            )

        elif act == "view_num":
            ord_id = a[1]
            await self._show_active_screen(c, ord_id)

        # ── سجل الأرقام السابقة ──
        elif act == "orders":
            async with db.Session() as s:
                orders = (await s.execute(
                    select(db.ServiceOrder)
                    .where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.user_id == c.uid, db.ServiceOrder.tpl_key == "sms")
                    .order_by(db.ServiceOrder.created.desc())
                    .limit(10)
                )).scalars().all()

            if not orders:
                await c.edit(
                    ui.head(t("📦 سجل الأرقام", "📦 Numbers History")) +
                    t("ليس لديك أي أرقام سابقة بعد.", "No previous numbers yet."),
                    kb([[B(t("📱 طلب رقم جديد", "📱 Rent Number"), "t:countries", style="success")],
                        [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
                )
                return

            lines = []
            st_map = {
                "waiting_sms": "⏳ بانتظار الكود",
                "completed": "✅ تم استلام الكود",
                "canceled": "❌ ملغى ومسترجع",
            }
            for o in orders:
                code_txt = f" [كود: {o.details.get('sms_code')}]" if o.details.get("sms_code") else ""
                lines.append(f"▫️ <code>{esc(o.target)}</code> ({esc(o.service_name)})\n   الحالة: <b>{st_map.get(o.status, o.status)}</b>{code_txt} · ${o.price_user_usd:.2f}")

            await c.edit(
                ui.head(t("📦 سجل آخر الأرقام", "📦 Numbers History")) + "\n".join(lines),
                kb([[B(t("📱 طلب رقم جديد", "📱 Rent Number"), "t:countries", style="success")],
                    [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )

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
                    [B(t("⬅️ طرق الدفع", "⬅️ Payment Methods"), "t:deposit")],
                ]
                await c.edit(
                    ui.head("⭐ نجوم تيليجرام (Telegram Stars)") +
                    t("ادفع بنجوم تيليجرام لتحصل على شحن فوري وآلي دون انتظار!\n\nاختر الباقة المطلوبة:",
                      "Pay with Telegram Stars for instant top-up:\n\nSelect package:"),
                    kb(stars_rows)
                )
                return

            c.set_state("sms_deposit_proof", method_id=mid)
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
                    kb([[B(t("📱 طلب رقم تفعيل", "📱 Rent Number"), "t:countries", style="success")],
                        [B(t("💼 المحفظة", "💼 Wallet"), "t:wallet")]])
                )
            else:
                await c.answer(t("فشل شحن النجوم", "Stars top-up failed"), True)

        # ── أكواد الخصم ──
        elif act == "promo":
            c.set_state("sms_enter_promo")
            await c.edit(
                ui.head(t("🎁 كود خصم أو هدية", "🎁 Promo Code")) +
                t("أرسل كود الخصم أو الهدية للحصول على رصيد إضافي في محفظتك:\n\n/cancel للإلغاء",
                  "Send promo code to claim bonus balance:\n\n/cancel to abort"),
                kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:home")]])
            )

        # ── الإحالة ──
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
                ui.head(t("ℹ️ مساعدة وشروط أرقام التفعيل", "ℹ️ Help & Terms")) +
                t(
                    "📌 <b>كيفية استخدام أرقام التفعيل:</b>\n"
                    "1. اطلب الرقم وانسخه من الشاشة وضعه في التطبيق المطلوب (تلغرام، واتساب...).\n"
                    "2. اضغط على زر إرسال كود الـ SMS داخل التطبيق.\n"
                    "3. ارجع للبوت واضغط «🔄 تحديث وفحص الكود الآن».\n"
                    "4. إذا لم يصلك الكود لأي سبب، اضغط «❌ إلغاء واسترجاع الرصيد» ليعود رصيدك فورياً لمحفظتك.\n\n"
                    "الأرقام آمنة وصالحة للاستخدام مرة واحدة.",
                    "📌 <b>How to use:</b>\n"
                    "1. Rent number, copy and paste in app.\n"
                    "2. Request SMS in the app.\n"
                    "3. Click check code.\n"
                    "4. Cancel anytime for 100% full refund if no SMS."
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
                margin_conf = await c.kv("sms:margin", {"type": "percent", "val": 35.0})
                cur_val = f"{margin_conf['val']}%" if margin_conf["type"] == "percent" else f"${margin_conf['val']}"
                text = (
                    ui.head(t("📈 هامش الربح لأرقام التفعيل", "📈 Profit Margin")) +
                    f"هامش الربح الحالي المطبق على جميع الأرقام: <b>{cur_val}</b>\n\n"
                    "اختر نسبة سريعة أو اضغط مخصص:"
                )
                rows = [
                    [B("+20%", "t:adm:set_m:20"), B("+35%", "t:adm:set_m:35"), B("+50%", "t:adm:set_m:50")],
                    [B("+75%", "t:adm:set_m:75"), B("+100%", "t:adm:set_m:100")],
                    [B(t("✏️ كتابة نسبة مخصصة", "✏️ Custom Margin"), "t:adm:input_m")],
                    [B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "set_m":
                val = float(a[2])
                await c.kv_set("sms:margin", {"type": "percent", "val": val})
                await c.answer(t(f"تم ضبط الهامش إلى {val}%", f"Margin set to {val}%"))
                await self.cb(c, ["adm", "margin"])

            elif sub == "input_m":
                c.set_state("sms_adm_margin")
                await c.edit(
                    ui.head(t("📈 كتابة هامش الربح", "📈 Custom Margin")) +
                    t("أرسل نسبة الربح المئوية التي تريد إضافتها على تكلفة المزود (مثال: <code>40</code> لـ 40%):\n\n/cancel للإلغاء",
                      "Send percentage profit (e.g. <code>40</code> for 40%):\n\n/cancel to abort"),
                    kb([[B(t("❌ إلغاء", "❌ Cancel"), "t:adm:margin")]])
                )

            # مزودو API
            elif sub == "provs":
                provs = await c.kv("sms:providers", [])
                lines = []
                for i, p in enumerate(provs, 1):
                    lines.append(f"{i}. <b>{esc(p.get('name', 'Custom'))}</b> — URL: <code>{esc(p.get('api_url', ''))}</code>")
                if not lines:
                    lines.append("<i>يتم استخدام محاكي أرقام الـ SMS الافتراضي القياسي (جاهز للتجربة فوراً).</i>")

                text = (
                    ui.head(t("🔌 مزودو خدمات أرقام التفعيل (SMS API)", "🔌 SMS API Providers")) +
                    "\n".join(lines) + "\n\n"
                    "متوافق مع بروتوكول SMS-Activate القياسي (SMSHub, 5SIM, SMS-Activate)."
                )
                rows = [
                    [B(t("➕ ربط مزود SMS جديد", "➕ Add SMS Provider"), "t:adm:prov_add", style="success")],
                    [B(t("🎛 غرفة التحكم", "🎛 Control Room"), "o:home")],
                ]
                await c.edit(text, kb(rows))

            elif sub == "prov_add":
                c.set_state("sms_adm_prov_add")
                await c.edit(
                    ui.head(t("➕ ربط مزود SMS جديد", "➕ Add SMS Provider")) +
                    t("أرسل بيانات المزود بهذه الصيغة:\n<code>الاسم | رابط API | المفتاح السري</code>\n\nمثال:\n<code>SMS-Activate | https://api.sms-activate.org/stubs/handler_api.php | abc123def...</code>\n\n/cancel للإلغاء",
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

            # سجل الطلبات
            elif sub == "orders":
                async with db.Session() as s:
                    orders = (await s.execute(
                        select(db.ServiceOrder)
                        .where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.tpl_key == "sms")
                        .order_by(db.ServiceOrder.created.desc())
                        .limit(15)
                    )).scalars().all()

                lines = []
                for o in orders:
                    lines.append(f"#{o.order_id} | {esc(o.target)} | {esc(o.service_name[:15])} | ${o.price_user_usd:.2f} | <b>{o.status}</b>")
                text = (
                    ui.head(t(f"📦 سجل أرقام البوت ({len(orders)})", f"📦 Bot Numbers ({len(orders)})")) +
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

    # ───────────────────────── شاشات تشغيل أرقام الـ SMS ─────────────────────────

    async def _execute_rent_number(self, c: Ctx, country: str, app: str) -> None:
        t = c.t
        price_usd = await SMSManager.calculate_number_price(c.bot_id, country, app)
        user_bal_usd = await ledger.get_user_balance_usd(c.bot_id, c.uid)

        if user_bal_usd < price_usd:
            await c.answer(t("رصيدك غير كافٍ لشراء هذا الرقم", "Insufficient balance"), True)
            return

        ord_key = f"sms_{uuid.uuid4().hex[:10]}"
        c_info = SMS_COUNTRIES.get(country, {"flag": "🌐", "name_ar": country})
        a_info = SMS_APPS.get(app, {"emoji": "📱", "name_ar": app})
        svc_title = f"{c_info['flag']} {a_info['name_ar']}"

        # 1. خصم الرصيد ذرياً
        ok_debit, tx, new_bal = await ledger.debit_user(
            c.bot_id,
            c.uid,
            price_usd,
            kind="order_sms",
            ref_id=ord_key,
            description=f"طلب رقم {svc_title}",
        )
        if not ok_debit:
            await c.answer(t("فشل خصم الرصيد", "Debit failed"), True)
            return

        # 2. طلب الرقم من المزود
        disp_ok, act_id, phone_number, prov_name, prov_cost = await SMSManager.rent_number_with_failover(
            c.bot_id, country, app
        )
        if not disp_ok:
            # استرجاع فوري
            await ledger.credit_user(c.bot_id, c.uid, price_usd, kind="sms_refund", ref_id=ord_key, description="استرجاع فوري لنفاد الأرقام")
            await c.edit(
                ui.head(t("⚠️ لا توجد أرقام متوفرة حالياً", "⚠️ No Numbers Available")) +
                t("نعتذر منك، لا توجد أرقام متوفرة لهذه الدولة والتطبيق حالياً. تم حفظ رصيدك كاملاً.",
                  "Sorry, no numbers available for this country/app right now. Full refund credited."),
                kb([[B(t("🌍 تجربة دولة أخرى", "🌍 Try Another Country"), "t:countries")],
                    [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )
            return

        # 3. حفظ الطلب في قاعدة البيانات
        bot_cur = await currency.get_bot_currency(c.bot_id)
        cur_price = await currency.usd_to_currency(price_usd, bot_cur, bot_id=c.bot_id)
        async with db.Session() as s:
            s_order = db.ServiceOrder(
                order_id=ord_key,
                bot_id=c.bot_id,
                user_id=c.uid,
                tpl_key="sms",
                service_id=f"{country}_{app}",
                service_name=svc_title,
                target=phone_number,
                quantity=1,
                cost_provider_usd=prov_cost,
                cost_platform_usd=0.0,
                price_user_usd=price_usd,
                currency=bot_cur,
                price_user_currency=cur_price,
                status="waiting_sms",
                provider_name=prov_name,
                provider_order_id=act_id,
                details={"country": country, "app": app, "rent_time": dt.datetime.utcnow().isoformat()},
            )
            s.add(s_order)
            await s.commit()

        await self._show_active_screen(c, ord_key)

    async def _show_active_screen(self, c: Ctx, ord_id: str) -> None:
        t = c.t
        async with db.Session() as s:
            res = await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_id))
            ord_row = res.scalars().first()

        if not ord_row:
            await self.home(c)
            return

        phone = ord_row.target
        svc_name = ord_row.service_name
        code_received = ord_row.details.get("sms_code", "")

        if code_received:
            text = (
                ui.head(t("🎉 وصل كود التفعيل بنجاح!", "🎉 SMS Code Received!")) +
                f"📱 <b>{t('الرقم:', 'Phone:')}</b> <code>{phone}</code>\n"
                f"📌 <b>{t('الخدمة:', 'Service:')}</b> {esc(svc_name)}\n\n"
                f"🔑 <b>{t('كود التفعيل (اضغط للنسخ):', 'Activation Code (Tap to copy):')}</b>\n"
                f"<code>{code_received}</code>\n\n"
                f"✅ <i>{t('تم اكتمال التفعيل بنجاح، شكراً لاختيارك خدماتنا!', 'Activation completed successfully!')}</i>"
            )
            rows = [
                [B(t("📱 طلب رقم جديد", "📱 Rent Another Number"), "t:countries", style="success")],
                [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
            ]
            await c.edit(text, kb(rows))
            return

        text = (
            ui.head(t("⏳ بانتظار وصول كود التفعيل", "⏳ Awaiting SMS Code")) +
            f"📱 <b>{t('الرقم المخصص (اضغط لنسخه):', 'Phone (Tap to copy):')}</b>\n"
            f"<code>{phone}</code>\n\n"
            f"📌 <b>{t('الخدمة:', 'Service:')}</b> {esc(svc_name)}\n"
            f"⏱ <b>{t('المهلة المتبقية:', 'Timeout:')}</b> 20 دقيقة\n\n"
            f"📝 <b>{t('الخطوات:', 'Steps:')}</b>\n"
            f"1. انسخ الرقم وضعه في التطبيق المطلوب.\n"
            f"2. اضغط على إرسال كود الـ SMS داخل التطبيق.\n"
            f"3. اضغط على الزر الأخضر بالأسفل لفحص وصول الكود.\n\n"
            f"<i>{t('إذا لم يصلك الكود لأي سبب، يمكنك الضغط على «إلغاء واسترجاع» ليعود رصيدك فورياً لمحفظتك.', 'If you cancel, you get an instant 100% refund.')}</i>"
        )
        rows = [
            [B(t("🔄 تحديث وفحص الكود الآن", "🔄 Check SMS Code Now"), f"t:check_sms:{ord_id}", style="success")],
            [B(t("❌ إلغاء واسترجاع الرصيد كاملاً", "❌ Cancel & Full Refund"), f"t:cancel_refund:{ord_id}", style="danger")],
            [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")],
        ]
        await c.edit(text, kb(rows))

    async def _check_sms_order(self, c: Ctx, ord_id: str) -> None:
        t = c.t
        async with db.Session() as s:
            res = await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_id))
            ord_row = res.scalars().first()

        if not ord_row:
            return

        res = await SMSManager.check_sms_code(c.bot_id, ord_row.provider_order_id, ord_row.provider_name)
        status = res.get("status")
        code = res.get("code")

        if status == "received" and code:
            async with db.Session() as s:
                res2 = await s.execute(select(db.ServiceOrder).where(db.ServiceOrder.order_id == ord_id))
                row2 = res2.scalars().first()
                if row2:
                    row2.status = "completed"
                    row2.details = dict(row2.details or {}, sms_code=code)
                    await s.commit()

            await c.answer(t(f"🎉 وصل الكود: {code}", f"Code: {code}"), True)
            await self._show_active_screen(c, ord_id)
        elif status == "canceled":
            await SMSManager.cancel_number_and_refund(c.bot_id, c.uid, ord_id, reason="ألغي لدى المزود")
            await c.answer(t("تم إلغاء الرقم من المزود واسترجاع رصيدك كاملاً", "Canceled and refunded"), True)
            await self.home(c)
        else:
            await c.answer(t("⏳ لم يصل الكود بعد، أرسل الكود في التطبيق واضغط تحديث مجدداً", "Waiting for SMS..."), True)

    # ───────────────────────── معالجة الرسائل والإدخال ─────────────────────────

    async def msg(self, c: Ctx) -> bool:  # noqa: C901
        st = c.st
        if not st:
            return False

        if c.text == "/cancel":
            c.clear_state()
            await c.send(c.t("تم الإلغاء.", "Cancelled."), kb([c.home_row()]))
            return True

        k = st.get("k")
        t = c.t

        # 1. إرسال إثبات الدفع اليدوي
        if k == "sms_deposit_proof":
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

        # 2. كود هدية عام
        elif k == "sms_enter_promo":
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
                kb([[B(t("📱 طلب رقم تفعيل", "📱 Rent Number"), "t:countries", style="success")],
                    [B(t("⬅️ الرئيسية", "⬅️ Home"), "t:home")]])
            )
            return True

        # 3. هامش المالك
        elif k == "sms_adm_margin":
            try:
                val = float(c.text.strip())
                await c.kv_set("sms:margin", {"type": "percent", "val": val})
                c.clear_state()
                await c.send(t(f"✅ تم ضبط الهامش إلى {val}%.", f"✅ Margin set to {val}%."))
                await self.cb(c, ["adm", "margin"])
            except ValueError:
                await c.send(t("⚠️ أدخل رقماً صحيحاً.", "⚠️ Enter valid number."))
            return True

        # 4. إضافة مزود
        elif k == "sms_adm_prov_add":
            parts = [p.strip() for p in c.text.split("|")]
            if len(parts) < 3 or not parts[1].startswith("http"):
                await c.send("⚠️ الصيغة: <code>الاسم | الرابط | المفتاح</code>\n\n/cancel للإلغاء")
                return True
            provs = await c.kv("sms:providers", [])
            provs.append({"name": parts[0], "api_url": parts[1], "api_key": parts[2], "on": True})
            await c.kv_set("sms:providers", provs)
            c.clear_state()
            await c.send(t(f"✅ تم ربط المزود {parts[0]} بنجاح.", f"✅ Provider {parts[0]} added."))
            await self.cb(c, ["adm", "provs"])
            return True

        return False

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
                .where(db.ServiceOrder.bot_id == c.bot_id, db.ServiceOrder.tpl_key == "sms")
            )).scalar() or 0
            pending_rcpts = (await s.execute(
                select(func.count(db.PaymentReceipt.id))
                .where(db.PaymentReceipt.bot_id == c.bot_id, db.PaymentReceipt.status == "pending")
            )).scalar() or 0

        margin_conf = await c.kv("sms:margin", {"type": "percent", "val": 35.0})
        m_str = f"+{margin_conf['val']}%" if margin_conf["type"] == "percent" else f"+${margin_conf['val']}"
        bot_cur = await currency.get_bot_currency(c.bot_id)
        seller_bal = await ledger.get_seller_balance_display(c.owner_id)

        info = (
            f"📱 <b>{t('إدارة متجر أرقام التفعيل:', 'SMS Numbers Management:')}</b>\n"
            f"📦 <b>{t('إجمالي الأرقام المطلوبة:', 'Total Numbers Rented:')}</b> {total_orders:,}\n"
            f"🧾 <b>{t('إيصالات شحن تنتظر الموافقة:', 'Pending Receipts:')}</b> <b>{pending_rcpts}</b>\n"
            f"📈 <b>{t('هامش الربح العام:', 'Profit Margin:')}</b> <code>{m_str}</code>\n"
            f"💱 <b>{t('عملة البوت:', 'Currency:')}</b> <code>{bot_cur}</code>\n"
            f"💼 <b>{t('رصيدك في الصانع:', 'Maker Balance:')}</b> <code>{seller_bal}</code>"
        )

        rows = [
            [B(t("📈 هامش الربح والأسعار", "📈 Profit Margins"), "t:adm:margin"),
             B(t("🔌 مزودو الـ API", "🔌 API Providers"), "t:adm:provs")],
            [B(t(f"🧾 طلبات الشحن المعلقة ({pending_rcpts})", f"🧾 Pending Receipts ({pending_rcpts})"), "t:adm:rcpts",
               style="warning" if pending_rcpts > 0 else "default"),
             B(t("💳 طرق الدفع والشحن", "💳 Payment Methods"), "t:adm:pay")],
            [B(t("📦 سجل الأرقام", "📦 Numbers Log"), "t:adm:orders"),
             B(t("💱 عملة البوت", "💱 Bot Currency"), "t:adm:cur")],
        ]
        return info, rows


TPL = Sms()
