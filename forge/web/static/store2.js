/* المتجر المصغّر v2 — واجهة الزبون + لوحة البائع + لوحة المدير (Vue 3 بلا أدوات بناء) */
(function () {
  "use strict";
  const { createApp, reactive, computed, ref, onMounted, watch } = Vue;
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

  // ───────────── الترجمة ─────────────
  const T = {
    ar: {
      home: "المتجر", orders: "طلباتي", wallet: "المحفظة", account: "حسابي", dash: "لوحتي", admin: "الإدارة",
      search: "ابحث عن منتج…", all: "الكل", sections: "الأقسام", categories: "الفئات", products: "المنتجات",
      no_products: "لا توجد منتجات هنا بعد", balance: "رصيدك", topup: "شحن", buy: "شراء الآن", qty: "الكمية",
      per1k: "لكل 1000", total: "الإجمالي", discount: "الخصم", price: "السعر", coupon: "كود خصم (اختياري)", apply: "تطبيق",
      need_topup: "رصيدك لا يكفي — اشحن", insufficient: "رصيدك غير كافٍ", ordered: "تم إنشاء الطلب ✅", instant: "تسليم فوري",
      min: "الأدنى", max: "الأقصى", target_required: "أدخل البيانات المطلوبة", copy: "نسخ", copied: "تم النسخ ✅",
      no_orders: "لا توجد طلبات بعد", browse: "تصفّح المتجر", check_code: "فحص الكود", cancel_refund: "إلغاء واسترجاع",
      phone: "الرقم", code: "الكود", delivery: "بيانات التسليم", refund_note: "ملاحظة",
      st_completed: "مكتمل", st_processing: "قيد التنفيذ", st_queued: "بانتظار التنفيذ", st_pending: "بانتظار التنفيذ",
      st_waiting_sms: "بانتظار الكود", st_refunded: "مُسترجع", st_canceled: "ملغي", st_failed: "فشل", st_approved: "مقبول", st_rejected: "مرفوض",
      topup_wallet: "شحن المحفظة", choose_amount: "اختر الباقة أو اكتب مبلغاً", custom_amount: "مبلغ مخصص", pay_stars: "ادفع بالنجوم",
      stars: "نجوم تيليجرام", manual: "تحويل", amount: "المبلغ", ref: "رقم العملية", proof: "صورة الإيصال (اختياري)", send_receipt: "إرسال الإيصال",
      receipt_sent: "استلمنا الإيصال وهو قيد المراجعة", statement: "كشف الحساب", my_receipts: "إيصالاتي", no_tx: "لا حركات بعد",
      language: "اللغة", currency: "العملة", referral: "اربح رصيداً بدعوة أصدقائك", ref_desc: "تحصل على نسبة من كل عملية شراء لأصدقائك",
      invited: "المدعوون", earned: "أرباحك", share: "مشاركة", support: "الدعم الفني", contact: "تواصل معنا", faq: "الأسئلة الشائعة",
      help: "المساعدة", terms: "شروط الاستخدام", close: "إغلاق", save: "حفظ", saved: "تم الحفظ ✅", loading: "جارٍ التحميل…",
      maint: "المتجر في صيانة حالياً، نعود قريباً", guest: "افتح المتجر من داخل تيليجرام لتتمكن من الشراء", error: "حدث خطأ، حاول مجدداً",
      orders_count: "طلباتك", spent: "مشترياتك", paid_stars: "تم الدفع ✅ سيُضاف الرصيد خلال ثوانٍ", open_invoice: "فتح الفاتورة",
      eta: "مدة التنفيذ", refill: "ضمان تعويض", method_instr: "التعليمات", account_no: "الحساب",
    },
    en: {
      home: "Store", orders: "Orders", wallet: "Wallet", account: "Account", dash: "Dashboard", admin: "Admin",
      search: "Search products…", all: "All", sections: "Sections", categories: "Categories", products: "Products",
      no_products: "No products here yet", balance: "Balance", topup: "Top up", buy: "Buy now", qty: "Quantity",
      per1k: "per 1000", total: "Total", discount: "Discount", price: "Price", coupon: "Promo code (optional)", apply: "Apply",
      need_topup: "Not enough balance — top up", insufficient: "Insufficient balance", ordered: "Order placed ✅", instant: "Instant",
      min: "Min", max: "Max", target_required: "Enter the required details", copy: "Copy", copied: "Copied ✅",
      no_orders: "No orders yet", browse: "Browse the store", check_code: "Check code", cancel_refund: "Cancel & refund",
      phone: "Number", code: "Code", delivery: "Delivery", refund_note: "Note",
      st_completed: "Completed", st_processing: "Processing", st_queued: "Queued", st_pending: "Pending",
      st_waiting_sms: "Waiting code", st_refunded: "Refunded", st_canceled: "Canceled", st_failed: "Failed", st_approved: "Approved", st_rejected: "Rejected",
      topup_wallet: "Top up wallet", choose_amount: "Pick a pack or type an amount", custom_amount: "Custom amount", pay_stars: "Pay with Stars",
      stars: "Telegram Stars", manual: "Transfer", amount: "Amount", ref: "Transaction ID", proof: "Receipt photo (optional)", send_receipt: "Send receipt",
      receipt_sent: "Receipt received and under review", statement: "Statement", my_receipts: "My receipts", no_tx: "No activity yet",
      language: "Language", currency: "Currency", referral: "Earn credit by inviting friends", ref_desc: "Get a share of every purchase your friends make",
      invited: "Invited", earned: "Earned", share: "Share", support: "Support", contact: "Contact us", faq: "FAQ",
      help: "Help", terms: "Terms of use", close: "Close", save: "Save", saved: "Saved ✅", loading: "Loading…",
      maint: "The store is under maintenance, back soon", guest: "Open the store inside Telegram to buy", error: "Something went wrong",
      orders_count: "Orders", spent: "Spent", paid_stars: "Paid ✅ balance arrives in seconds", open_invoice: "Open invoice",
      eta: "ETA", refill: "Refill guarantee", method_instr: "Instructions", account_no: "Account",
    },
  };

  // ───────────── الحالة العامة ─────────────
  const path = location.pathname.replace(/\/+$/, "");
  const isAdminApp = path.startsWith("/admin_app");
  const startParam = (tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param) || "";
  const fromPath = (path.match(/^\/(?:app|store)\/([A-Za-z0-9_]{3,40})/) || [])[1];
  const storeId = fromPath || (startParam && /^[A-Za-z0-9_]{3,40}$/.test(startParam) ? startParam : "") || "default";
  const S = reactive({
    ready: false, lang: "ar", cur: "USD", store: {}, user: {}, currencies: [], tab: isAdminApp ? "admin" : "home",
    toast: "", sheet: null, busy: false,
  });
  const t = (k) => (T[S.lang] || T.ar)[k] || T.ar[k] || k;

  function guestId() {
    try { let g = localStorage.getItem("gid"); if (!g) { g = Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem("gid", g); } return g; } catch (e) { return ""; }
  }
  async function api(p, opts) {
    opts = opts || {};
    const h = { "X-Telegram-Init-Data": (tg && tg.initData) || "", "X-Guest-Id": guestId() };
    let body = opts.body;
    if (body && !(body instanceof FormData)) { h["Content-Type"] = "application/json"; body = JSON.stringify(body); }
    const r = await fetch("/api/v2/" + storeId + p, { method: opts.method || (body ? "POST" : "GET"), headers: h, body });
    let j = {};
    try { j = await r.json(); } catch (e) { j = { ok: false, message: t("error") }; }
    if (!r.ok && j.ok !== false) j.ok = false;
    return j;
  }
  function toast(m) { S.toast = m; clearTimeout(toast._t); toast._t = setTimeout(() => (S.toast = ""), 2600); }
  function haptic(k) { try { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred(k || "success"); } catch (e) {} }
  function copy(v) { try { navigator.clipboard.writeText(String(v)); toast(t("copied")); } catch (e) {} }

  const curInfo = computed(() => S.currencies.find((c) => c.code === S.cur) || { code: "USD", symbol: "$", rate: 1, decimals: 2 });
  function money(usd) {
    const c = curInfo.value; const v = (Number(usd) || 0) * (c.rate || 1); const d = c.decimals == null ? 2 : c.decimals;
    const whole = Math.abs(v - Math.round(v)) < 1e-9;
    const s = v.toLocaleString("en-US", { minimumFractionDigits: d > 0 && !whole ? Math.min(d, 2) : 0, maximumFractionDigits: d });
    if (c.symbol === "$") return "$" + s;
    if (["€", "₺", "₽", "₹"].includes(c.symbol)) return c.symbol + s;
    return s + " " + c.symbol;
  }
  const usd = (v) => "$" + (Number(v) || 0).toFixed(2);
  const KINDS = {
    ar: { deposit: "شحن رصيد", deposit_stars: "شحن بالنجوم", deposit_manual: "شحن بتحويل", order_refund: "استرجاع طلب", sms_refund: "استرجاع رقم",
      referral_reward: "مكافأة إحالة", wheel_reward: "جائزة", seller_adjust: "تعديل من المتجر", promo_gift: "هدية كود" },
    en: { deposit: "Top-up", deposit_stars: "Stars top-up", deposit_manual: "Transfer top-up", order_refund: "Order refund", sms_refund: "Number refund",
      referral_reward: "Referral reward", wheel_reward: "Prize", seller_adjust: "Store adjustment", promo_gift: "Promo gift" },
  };
  const kindLabel = (x) => (KINDS[S.lang] || KINDS.ar)[x.kind] || x.desc || x.kind;
  function stLabel(s) { return t("st_" + s) || s; }
  function stTag(s) { return { completed: "ok", approved: "ok", processing: "info", waiting_sms: "warn", queued: "warn", pending: "warn" }[s] || "bad"; }

  function applyTheme() {
    const scheme = S.store.theme && S.store.theme !== "auto" ? S.store.theme : (tg && tg.colorScheme) || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.dataset.theme = scheme;
    document.documentElement.style.setProperty("--accent", S.store.accent || "#6d5dfc");
    document.documentElement.lang = S.lang; document.documentElement.dir = S.lang === "ar" ? "rtl" : "ltr";
    try { tg && tg.setHeaderColor && tg.setHeaderColor(scheme === "dark" ? "#0f1115" : "#f4f5f8"); } catch (e) {}
  }

  async function setPref(o) {
    if (o.lang) S.lang = o.lang;
    if (o.currency) S.cur = o.currency;
    applyTheme();
    if (!S.user.is_guest) await api("/prefs", { body: o });
  }

  // ───────────── مكوّنات مشتركة ─────────────
  const Sheet = {
    props: ["title"], emits: ["close"],
    template: `<div class="sheet-bg" @click.self="$emit('close')"><div class="sheet"><div class="grab"></div>
      <div class="row sb" v-if="title"><b style="font-size:17px">{{title}}</b><button class="btn ghost sm" @click="$emit('close')">✕</button></div>
      <slot></slot></div></div>`,
  };
  const Toggle = { props: ["modelValue"], emits: ["update:modelValue"], template: `<button class="toggle" :class="{on:modelValue}" @click="$emit('update:modelValue',!modelValue)"></button>` };
  const Bars = {
    props: ["series"],
    setup(p) { const mx = computed(() => Math.max(1, ...(p.series || []).map((x) => x.v))); return { mx }; },
    template: `<div class="bars"><div v-for="x in series" :key="x.d" :title="x.d+': '+x.v" :style="{height:(x.v/mx*100)+'%'}"></div></div>`,
  };

  // ───────────── المتجر (الرئيسية) ─────────────
  const Home = {
    components: { Sheet },
    setup() {
      const cat = reactive({ sections: [], categories: [], products: [], loaded: false });
      const sec = ref(""), cid = ref(""), q = ref("");
      const prod = ref(null);
      async function load() {
        const j = await api("/catalog?lang=" + S.lang);
        if (j.ok) { Object.assign(cat, j, { loaded: true }); if (!sec.value && j.sections.length) sec.value = j.sections[0].id; }
      }
      onMounted(load);
      watch(() => S.lang, load);
      const cats = computed(() => cat.categories.filter((c) => c.sec === sec.value));
      const list = computed(() => {
        const s = q.value.trim().toLowerCase();
        if (s) return cat.products.filter((p) => (p.name + " " + (p.desc || "")).toLowerCase().includes(s)).slice(0, 60);
        if (!cid.value) return [];
        return cat.products.filter((p) => p.cat === cid.value);
      });
      const catName = computed(() => (cat.categories.find((c) => c.id === cid.value) || {}).name || "");
      return { S, t, cat, sec, cid, q, cats, list, catName, prod, money };
    },
    template: `<div class="wrap">
      <div v-if="S.store.announcement" class="ann">📣 {{S.store.announcement}}</div>
      <img v-if="S.store.banner" :src="S.store.banner" class="banner mt" alt="">
      <div class="search mt"><span>🔎</span><input class="inp" v-model="q" :placeholder="t('search')"></div>
      <template v-if="!q">
        <div v-if="cat.sections.length>1" class="chips mt"><button v-for="s in cat.sections" :key="s.id" class="chip" :class="{on:sec===s.id}" @click="sec=s.id;cid=''">{{s.icon}} {{s.name}}</button></div>
        <template v-if="!cid">
          <div class="h">{{t('categories')}}</div>
          <div v-if="!cat.loaded" class="grid"><div class="skel" v-for="i in 6" :key="i"></div></div>
          <div v-else class="grid"><div v-for="c in cats" :key="c.id" class="cat" @click="cid=c.id"><div class="ic">{{c.icon}}</div><b>{{c.name}}</b></div></div>
          <div v-if="cat.loaded && !cats.length" class="empty"><div>🛍</div>{{t('no_products')}}</div>
        </template>
        <template v-else>
          <div class="h"><span>{{catName}}</span><button class="btn sm" @click="cid=''">↩</button></div>
        </template>
      </template>
      <div class="plist">
        <div v-for="p in list" :key="p.id" class="prod" @click="prod=p">
          <div class="pi"><img v-if="p.img" :src="p.img" alt=""><span v-else>{{p.icon}}</span></div>
          <div class="grow"><div class="pn">{{p.name}}</div><div class="pd">{{p.desc}}</div>
            <span v-if="p.instant" class="tag ok">⚡ {{t('instant')}}</span></div>
          <div class="price">{{money(p.price_usd)}}<div v-if="p.unit==='1k'" class="tiny muted" style="font-weight:500">{{t('per1k')}}</div></div>
        </div>
      </div>
      <div v-if="(cid||q) && !list.length" class="empty"><div>🔍</div>{{t('no_products')}}</div>
      <buy-sheet v-if="prod" :p="prod" @close="prod=null"></buy-sheet>
    </div>`,
  };

  const BuySheet = {
    components: { Sheet }, props: ["p"], emits: ["close"],
    setup(props, { emit }) {
      const p = props.p;
      const qty = ref(p.unit === "1k" ? p.min : 1);
      const target = ref(""), coupon = ref(""), showCoupon = ref(false);
      const quote = reactive({ total: null, discount: 0, msg: "" });
      const unitPrice = computed(() => (p.unit === "1k" ? p.price_usd / 1000 : p.price_usd));
      const subtotal = computed(() => unitPrice.value * (Number(qty.value) || 0));
      const total = computed(() => (quote.total != null ? quote.total : subtotal.value));
      const presets = computed(() => (p.unit === "1k" ? [p.min, 1000, 5000, 10000, 50000].filter((x, i, a) => x >= p.min && x <= p.max && a.indexOf(x) === i) : []));
      async function applyCoupon() {
        const j = await api("/quote", { body: { product_id: p.id, quantity: Number(qty.value), coupon: coupon.value } });
        if (j.ok) { quote.total = j.total_usd; quote.discount = j.discount_usd; quote.msg = j.coupon_msg || ""; toast(j.discount_usd > 0 ? "🎉 " + money(j.discount_usd) : (j.coupon_msg || t("error"))); }
      }
      watch(qty, () => { quote.total = null; quote.discount = 0; });
      const enough = computed(() => (S.user.balance_usd || 0) + 1e-9 >= total.value);
      async function buy() {
        if (S.user.is_guest) return toast(t("guest"));
        if (p.target && !target.value.trim()) return toast(t("target_required"));
        if (!enough.value) { emit("close"); S.tab = "wallet"; return toast(t("insufficient")); }
        S.busy = true;
        const j = await api("/order", { body: { product_id: p.id, quantity: Number(qty.value), target: target.value.trim(), coupon_code: coupon.value.trim(),
          idempotency_key: "o" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7) } });
        S.busy = false;
        if (j.ok) {
          haptic(); toast(j.message || t("ordered"));
          if (j.new_balance_usd != null) S.user.balance_usd = j.new_balance_usd; else refreshBalance();
          emit("close"); S.tab = "orders";
        } else { haptic("error"); toast(j.message || t("error")); refreshBalance(); }
      }
      return { S, t, p, qty, target, coupon, showCoupon, quote, total, subtotal, presets, enough, buy, applyCoupon, money };
    },
    template: `<sheet :title="p.name" @close="$emit('close')">
      <p class="muted" style="margin:6px 0 0" v-if="p.desc">{{p.desc}}</p>
      <div class="row wrapf" style="gap:6px;margin-top:8px">
        <span class="tag">{{money(p.price_usd)}} <span v-if="p.unit==='1k'">/ 1000</span></span>
        <span v-if="p.instant" class="tag ok">⚡ {{t('instant')}}</span>
        <span v-if="p.eta" class="tag">⏱ {{p.eta}}</span><span v-if="p.refill" class="tag info">♻ {{t('refill')}}</span>
      </div>
      <template v-if="p.max>1">
        <label class="lbl">{{t('qty')}} <span class="c3">({{t('min')}} {{p.min}} · {{t('max')}} {{p.max.toLocaleString()}})</span></label>
        <div class="qty"><button class="btn" @click="qty=Math.max(p.min,(+qty)-(p.unit==='1k'?100:1))">−</button>
          <input class="inp" type="number" inputmode="numeric" v-model.number="qty" :min="p.min" :max="p.max">
          <button class="btn" @click="qty=Math.min(p.max,(+qty)+(p.unit==='1k'?100:1))">+</button></div>
        <div class="presets" v-if="presets.length"><button v-for="x in presets" :key="x" class="chip" :class="{on:+qty===x}" @click="qty=x">{{x.toLocaleString()}}</button></div>
      </template>
      <template v-if="p.target"><label class="lbl">{{p.target.label}}</label>
        <input class="inp" v-model="target" :placeholder="p.target.kind==='url'?'https://':(p.target.kind==='username'?'@username':'')" dir="ltr"></template>
      <div class="mt"><a href="#" @click.prevent="showCoupon=!showCoupon" class="tiny">🎟 {{t('coupon')}}</a>
        <div v-if="showCoupon" class="row mt"><input class="inp" v-model="coupon" dir="ltr" style="text-transform:uppercase"><button class="btn sm" @click="applyCoupon">{{t('apply')}}</button></div></div>
      <div class="sum">
        <div class="row sb"><span class="muted">{{t('price')}}</span><span>{{money(subtotal)}}</span></div>
        <div class="row sb" v-if="quote.discount>0"><span class="muted">{{t('discount')}}</span><span class="plus">− {{money(quote.discount)}}</span></div>
        <div class="row sb tot"><span>{{t('total')}}</span><span>{{money(total)}}</span></div>
        <div class="row sb tiny muted"><span>{{t('balance')}}</span><span>{{money(S.user.balance_usd)}}</span></div>
      </div>
      <button class="btn p blk mt" :disabled="S.busy" @click="buy">{{enough?t('buy'):t('need_topup')}}</button>
    </sheet>`,
  };

  async function refreshBalance() {
    const j = await api("/wallet");
    if (j.ok) S.user.balance_usd = j.balance_usd;
  }

  // ───────────── الطلبات ─────────────
  const Orders = {
    setup() {
      const items = ref(null);
      async function load() { const j = await api("/orders"); items.value = j.data || j.orders || []; }
      onMounted(load);
      async function check(o) {
        const j = await api("/sms/check", { body: { order_id: o.order_id } });
        if (j.code) { o.sms_code = j.code; o.status = "completed"; haptic(); } else toast(j.message || "⏳");
      }
      async function cancel(o) {
        if (!confirm(t("cancel_refund") + "?")) return;
        const j = await api("/sms/cancel", { body: { order_id: o.order_id } });
        toast(j.message || ""); if (j.ok) { o.status = "canceled"; refreshBalance(); }
      }
      return { S, t, items, load, check, cancel, copy, money, stLabel, stTag };
    },
    template: `<div class="wrap">
      <div class="h">{{t('orders')}} <button class="btn sm" @click="load">↻</button></div>
      <div v-if="items===null" class="plist"><div class="skel" v-for="i in 4" :key="i"></div></div>
      <div v-else-if="!items.length" class="empty"><div>📦</div>{{t('no_orders')}}<div class="mt"><button class="btn p" @click="S.tab='home'">{{t('browse')}}</button></div></div>
      <div v-else class="plist">
        <div v-for="o in items" :key="o.order_id" class="card">
          <div class="row sb"><b style="font-size:14px">{{o.product_name}}</b><span class="tag" :class="stTag(o.status)">{{stLabel(o.status)}}</span></div>
          <div class="row sb tiny muted mt"><span class="copy" @click="copy(o.order_id)">#{{o.order_id.slice(-8)}}</span><span>{{o.created}}</span><b class="price">{{money(o.total_price)}}</b></div>
          <div v-if="o.target && o.tpl_key!=='sms'" class="tiny muted mt" dir="ltr" style="text-align:start">🎯 {{o.target}}</div>
          <div v-if="o.tpl_key==='sms' && o.phone && o.phone!=='-'" class="sum">
            <div class="row sb"><span>📱 {{t('phone')}}</span><b class="copy" dir="ltr" @click="copy(o.phone)">{{o.phone}}</b></div>
            <div class="row sb" v-if="o.sms_code"><span>🔑 {{t('code')}}</span><b class="copy plus" style="font-size:18px" @click="copy(o.sms_code)">{{o.sms_code}}</b></div>
            <div class="row mt" v-if="o.status==='waiting_sms'"><button class="btn ok sm grow" @click="check(o)">🔄 {{t('check_code')}}</button><button class="btn bad sm grow" @click="cancel(o)">↩ {{t('cancel_refund')}}</button></div>
          </div>
          <div v-else-if="o.delivery_data" class="sum"><div class="row sb"><span>📦 {{t('delivery')}}</span><button class="btn sm" @click="copy(o.delivery_data)">{{t('copy')}}</button></div>
            <div style="white-space:pre-wrap;word-break:break-all;font-family:monospace;font-size:13px">{{o.delivery_data}}</div></div>
          <div v-if="o.rejection_reason" class="tiny mt" style="color:var(--bad)">{{t('refund_note')}}: {{o.rejection_reason}}</div>
        </div>
      </div></div>`,
  };

  // ───────────── المحفظة ─────────────
  const Wallet = {
    components: { Sheet },
    setup() {
      const w = ref(null); const mode = ref("stars"); const amt = ref(null); const pick = ref(null);
      const m = reactive({ id: "", amount: "", ref: "", file: null });
      async function load() {
        const j = await api("/wallet");
        if (j.ok) { w.value = j; S.user.balance_usd = j.balance_usd; if (!j.stars_enabled && j.methods.length) mode.value = j.methods[0].id;
          if (pick.value == null && amt.value == null && j.packages.length) pick.value = j.packages[Math.min(1, j.packages.length - 1)]; }
      }
      onMounted(load);
      const usdAmount = computed(() => (pick.value != null ? pick.value : (Number(amt.value) || 0) / (curInfo.value.rate || 1)));
      const stars = computed(() => Math.max(1, Math.round(usdAmount.value / (w.value ? w.value.star_rate_usd : 0.016))));
      const method = computed(() => (w.value ? w.value.methods.find((x) => x.id === mode.value) : null));
      async function payStars() {
        if (S.user.is_guest) return toast(t("guest"));
        const v = Math.round(usdAmount.value * 100) / 100;
        if (!(v >= w.value.custom_min && v <= w.value.custom_max)) return toast(t("min") + " " + usd(w.value.custom_min) + " · " + t("max") + " " + usd(w.value.custom_max));
        const j = await api("/deposit/stars", { body: { usd: v } });
        if (!j.ok) return toast(j.message || t("error"));
        const done = (st) => { if (st === "paid") { haptic(); toast(t("paid_stars")); setTimeout(load, 1500); setTimeout(load, 5000); } };
        if (tg && tg.openInvoice) tg.openInvoice(j.invoice_link, done); else window.open(j.invoice_link, "_blank");
      }
      async function sendReceipt() {
        if (S.user.is_guest) return toast(t("guest"));
        const fd = new FormData();
        fd.append("method_id", method.value.id); fd.append("amount", String(m.amount || "")); fd.append("ref", m.ref || "");
        if (m.file) fd.append("image", m.file, m.file.name || "proof.jpg");
        S.busy = true; const j = await api("/deposit/receipt", { body: fd }); S.busy = false;
        if (j.ok) { haptic(); toast(t("receipt_sent")); m.amount = ""; m.ref = ""; m.file = null; load(); } else toast(j.message || t("error"));
      }
      return { S, t, w, mode, amt, pick, m, stars, method, payStars, sendReceipt, money, usd, copy, load, stLabel, stTag, curInfo, kindLabel };
    },
    template: `<div class="wrap">
      <div class="balcard"><small>{{t('balance')}}</small><div class="big">{{money(S.user.balance_usd)}}</div><small v-if="S.cur!=='USD'">≈ {{usd(S.user.balance_usd)}}</small></div>
      <template v-if="w">
        <div class="h">{{t('topup_wallet')}}</div>
        <div class="chips"><button v-if="w.stars_enabled" class="chip" :class="{on:mode==='stars'}" @click="mode='stars'">⭐ {{t('stars')}}</button>
          <button v-for="x in w.methods" :key="x.id" class="chip" :class="{on:mode===x.id}" @click="mode=x.id">💳 {{x.name}}</button></div>
        <div class="card" v-if="mode==='stars'">
          <div class="muted tiny">{{t('choose_amount')}}</div>
          <div class="pk mt"><button v-for="p in w.packages" :key="p" class="btn" :class="{on:pick===p}" @click="pick=p;amt=null">{{money(p)}}</button></div>
          <label class="lbl">{{t('custom_amount')}} ({{curInfo.code}})</label>
          <input class="inp" type="number" inputmode="decimal" v-model.number="amt" @input="pick=null" :placeholder="money(w.custom_min)+' – '+money(w.custom_max)">
          <button class="btn p blk mt" @click="payStars">⭐ {{t('pay_stars')}} — {{stars.toLocaleString()}} ⭐</button>
        </div>
        <div class="card" v-else-if="method">
          <div v-if="method.instructions" class="muted" style="white-space:pre-wrap">{{method.instructions}}</div>
          <div v-if="method.account" class="sum row sb"><span>{{t('account_no')}}</span><b class="copy" dir="ltr" @click="copy(method.account)">{{method.account}}</b></div>
          <label class="lbl">{{t('amount')}} ({{method.currency}})</label><input class="inp" type="number" inputmode="decimal" v-model="m.amount">
          <label class="lbl">{{t('ref')}}</label><input class="inp" v-model="m.ref" dir="ltr">
          <label class="lbl">{{t('proof')}}</label><div class="upl"><label class="btn sm">📷 {{m.file?m.file.name.slice(0,22):t('proof')}}<input type="file" accept="image/*" @change="m.file=$event.target.files[0]"></label></div>
          <button class="btn p blk mt" :disabled="S.busy" @click="sendReceipt">{{t('send_receipt')}}</button>
        </div>
        <template v-if="w.receipts.length"><div class="h">{{t('my_receipts')}}</div>
          <div class="card"><div class="tx" v-for="r in w.receipts" :key="r.id"><span>{{r.method}} · {{usd(r.amount_usd)}}</span><span class="tag" :class="stTag(r.status)">{{stLabel(r.status)}}</span></div></div></template>
        <div class="h">{{t('statement')}} <button class="btn sm" @click="load">↻</button></div>
        <div class="card"><div v-if="!w.transactions.length" class="muted tiny">{{t('no_tx')}}</div>
          <div class="tx" v-for="(x,i) in w.transactions" :key="i"><div><div>{{x.kind.startsWith('order_')&&x.kind!=='order_refund'?x.desc:kindLabel(x)}}</div><div class="tiny c3">{{x.at}}</div></div>
            <b :class="x.dir==='credit'?'plus':'minus'">{{x.dir==='credit'?'+':'−'}}{{money(x.amount_usd)}}</b></div></div>
      </template>
      <div v-else class="skel mt"></div></div>`,
  };

  // ───────────── حسابي ─────────────
  const Account = {
    components: { Sheet },
    setup() {
      const a = ref(null); const curOpen = ref(false); const cq = ref("");
      onMounted(async () => { const j = await api("/account"); if (j.ok) a.value = j; });
      const curList = computed(() => S.currencies.filter((c) => !cq.value || (c.code + c.ar + c.en).toLowerCase().includes(cq.value.toLowerCase())));
      const sup = computed(() => S.store.support || {});
      function share() { const l = a.value.referral.link; if (tg && tg.openTelegramLink) tg.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(l)); else copy(l); }
      function open(u) { if (tg && u.startsWith("https://t.me/") && tg.openTelegramLink) tg.openTelegramLink(u); else if (tg && tg.openLink) tg.openLink(u); else window.open(u, "_blank"); }
      return { S, t, a, curOpen, cq, curList, sup, share, open, copy, money, setPref };
    },
    template: `<div class="wrap">
      <div class="card row"><div class="logo">{{(S.user.name||'?').slice(0,1)}}</div><div class="grow"><b>{{S.user.name}}</b><div class="tiny muted" dir="ltr" style="text-align:start">ID {{S.user.uid}}</div></div></div>
      <div class="kpis mt" v-if="a"><div class="kpi"><small>{{t('orders_count')}}</small><b>{{a.orders}}</b></div><div class="kpi"><small>{{t('spent')}}</small><b>{{money(a.spent_usd)}}</b></div></div>
      <div class="card mt">
        <div class="row sb"><span>🌐 {{t('language')}}</span><div class="row"><button class="chip" :class="{on:S.lang==='ar'}" @click="setPref({lang:'ar'})">العربية</button><button class="chip" :class="{on:S.lang==='en'}" @click="setPref({lang:'en'})">English</button></div></div>
        <div class="row sb mt"><span>💱 {{t('currency')}}</span><button class="btn sm" @click="curOpen=true">{{S.cur}} ▾</button></div>
      </div>
      <div class="card mt" v-if="a && a.referral.on"><b>🎁 {{t('referral')}}</b><div class="tiny muted">{{t('ref_desc')}} ({{a.referral.percent}}%)</div>
        <div class="sum row sb"><span class="copy tiny" dir="ltr" @click="copy(a.referral.link)">{{a.referral.link}}</span></div>
        <div class="row mt"><span class="tag">{{t('invited')}}: {{a.referral.count}}</span><span class="tag ok">{{t('earned')}}: {{money(a.referral.earned_usd)}}</span><span class="grow"></span><button class="btn p sm" @click="share">{{t('share')}}</button></div></div>
      <div class="card mt" v-if="sup.username||sup.whatsapp||sup.email||sup.channel||(sup.links&&sup.links.length)"><b>🎧 {{t('support')}}</b>
        <div class="row wrapf mt" style="gap:8px">
          <button v-if="sup.username" class="btn sm" @click="open('https://t.me/'+sup.username)">💬 @{{sup.username}}</button>
          <button v-if="sup.channel" class="btn sm" @click="open('https://t.me/'+sup.channel)">📢 @{{sup.channel}}</button>
          <button v-if="sup.whatsapp" class="btn sm" @click="open('https://wa.me/'+sup.whatsapp.replace(/[^0-9]/g,''))">🟢 WhatsApp</button>
          <button v-if="sup.email" class="btn sm" @click="open('mailto:'+sup.email)">✉️ {{sup.email}}</button>
          <button v-for="l in sup.links" :key="l.url" class="btn sm" @click="open(l.url)">🔗 {{l.label}}</button></div></div>
      <template v-if="S.store.faq && S.store.faq.length"><div class="h">❓ {{t('faq')}}</div>
        <details class="faq" v-for="(f,i) in S.store.faq" :key="i"><summary>{{f.q}}</summary><div class="muted mt" style="white-space:pre-wrap">{{f.a}}</div></details></template>
      <sheet v-if="curOpen" :title="t('currency')" @close="curOpen=false">
        <div class="search mt"><span>🔎</span><input class="inp" v-model="cq"></div>
        <div class="list mt"><div class="it row sb" v-for="c in curList" :key="c.code" @click="setPref({currency:c.code});curOpen=false" style="cursor:pointer">
          <span><b>{{c.code}}</b> <span class="muted tiny">{{S.lang==='ar'?c.ar:c.en}}</span></span><span>{{c.symbol}} <span v-if="S.cur===c.code">✅</span></span></div></div>
      </sheet></div>`,
  };

  // تُكمل لوحتا البائع والمدير في store2_dash.js
  window.__S2 = { S, t, api, toast, haptic, copy, money, usd, stLabel, stTag, Sheet, Toggle, Bars, refreshBalance, setPref, curInfo };
  window.__S2_parts = { Home, BuySheet, Orders, Wallet, Account };

  window.__S2_start = function (Dash, Admin) {
    const Pages = {
      setup() {
        return { S, t };
      },
    };
    const app = createApp({
      components: { Home, Orders, Wallet, Account, Dash, Admin },
      setup() {
        const tabs = computed(() => {
          const x = isAdminApp ? [] : [["home", "🛍"], ["orders", "📦"], ["wallet", "💰"], ["account", "👤"]];
          if (!isAdminApp && (S.user.is_owner || S.user.is_admin)) x.push(["dash", "📊"]);
          if (S.user.is_admin) x.push(["admin", "🛡"]);
          return x;
        });
        const page = ref(null); // help | terms
        onMounted(async () => {
          if (tg) { try { tg.ready(); tg.expand(); } catch (e) {} }
          const j = await api("/boot");
          if (!j.ok) { S.ready = true; S.fatal = j.message || t("error"); return; }
          Object.assign(S, { store: j.store, user: j.user, currencies: j.currencies, lang: j.user.lang || "ar", cur: j.user.currency || j.store.currency || "USD" });
          applyTheme(); S.ready = true;
          if (isAdminApp && !S.user.is_admin) S.fatal = "403";
          const qp = new URLSearchParams(location.search);
          const sp = (qp.get("tab") || startParam || "").toLowerCase();
          if (["wallet", "orders", "account"].includes(sp) || (sp === "dash" && (S.user.is_owner || S.user.is_admin))) S.tab = sp;
        });
        watch(() => S.tab, () => window.scrollTo(0, 0));
        return { S, t, tabs, page, money };
      },
      template: `<div>
        <div v-if="!S.ready" class="wrap"><div class="skel mt" v-for="i in 5" :key="i"></div></div>
        <div v-else-if="S.fatal" class="wrap"><div class="empty"><div>⚠️</div>{{S.fatal}}</div></div>
        <template v-else>
          <header class="top"><div class="wrap">
            <div class="logo"><img v-if="S.store.logo" :src="S.store.logo" alt=""><span v-else>{{(S.store.name||'S').slice(0,1)}}</span></div>
            <div class="ttl" v-if="S.tab==='admin'"><b>🛡 {{S.lang==='ar'?'إدارة المنصة':'Platform admin'}}</b><small>{{S.user.name}}</small></div>
            <div class="ttl" v-else><b>{{S.store.name}}</b><small v-if="S.store.desc">{{S.store.desc}}</small></div>
            <div v-if="!S.user.is_guest && S.tab!=='admin' && S.tab!=='dash'" class="chip-bal" @click="S.tab='wallet'">💰 {{money(S.user.balance_usd)}}</div>
          </div></header>
          <div v-if="S.store.maintenance && !S.user.is_owner && !S.user.is_admin" class="wrap"><div class="empty"><div>🛠</div>{{t('maint')}}</div></div>
          <template v-else>
            <div v-if="S.user.is_guest" class="wrap"><div class="ann">ℹ️ {{t('guest')}}</div></div>
            <home v-if="S.tab==='home'"></home>
            <orders v-else-if="S.tab==='orders'"></orders>
            <wallet v-else-if="S.tab==='wallet'"></wallet>
            <account v-else-if="S.tab==='account'"></account>
            <dash v-else-if="S.tab==='dash'"></dash>
            <admin v-else-if="S.tab==='admin'"></admin>
            <div class="foot" v-if="S.tab!=='dash' && S.tab!=='admin'">
              <a href="#" v-if="S.store.help" @click.prevent="page='help'">{{t('help')}}</a>
              <a href="#" v-if="S.store.terms" @click.prevent="page='terms'">{{t('terms')}}</a>
              <div class="mt">© {{S.store.name}}</div></div>
          </template>
          <nav class="tabs" v-if="tabs.length>1"><div class="in">
            <button v-for="x in tabs" :key="x[0]" class="tab" :class="{on:S.tab===x[0]}" @click="S.tab=x[0]"><span class="ti">{{x[1]}}</span>{{t(x[0])}}</button></div></nav>
          <div class="sheet-bg" v-if="page" @click.self="page=null"><div class="sheet"><div class="grab"></div>
            <div class="row sb"><b>{{t(page)}}</b><button class="btn ghost sm" @click="page=null">✕</button></div>
            <div class="muted mt" style="white-space:pre-wrap">{{S.store[page]}}</div></div></div>
        </template>
        <div class="toast" v-if="S.toast">{{S.toast}}</div>
      </div>`,
    });
    app.component("buy-sheet", BuySheet);
    app.component("sheet", Sheet);
    app.component("toggle", Toggle);
    app.component("bars", Bars);
    app.mount("#app");
  };
})();
