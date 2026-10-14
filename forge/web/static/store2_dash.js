/* لوحة البائع ولوحة المدير داخل التطبيق المصغّر v2 */
(function () {
  "use strict";
  const { reactive, ref, computed, onMounted, watch } = Vue;
  const { S, api, toast, haptic, copy, usd, stLabel, stTag } = window.__S2;
  const AR = (a, e) => (S.lang === "ar" ? a : e);
  const SEC_NAMES = { digital: ["الألعاب والاشتراكات", "Games & subs"], smm: ["زيادة التفاعل", "Social boost"], sms: ["أرقام التفعيل", "Numbers"], tgstars: ["نجوم تيليجرام", "Telegram Stars"] };
  const secName = (k) => AR(...(SEC_NAMES[k] || [k, k]));
  const ask = (m, d) => window.prompt(m, d == null ? "" : d);

  // ═════════════ لوحة البائع ═════════════
  const SellerOverview = {
    setup() {
      const d = ref(null);
      onMounted(async () => { const j = await api("/seller/overview"); if (j.ok) d.value = j; });
      return { d, usd, AR, S };
    },
    template: `<div v-if="d">
      <div class="kpis">
        <div class="kpi"><small>{{AR('مبيعات اليوم','Today')}}</small><b>{{usd(d.today.sales_usd)}}</b><div class="sub">{{d.today.orders}} {{AR('طلب','orders')}}</div></div>
        <div class="kpi"><small>{{AR('ربح اليوم','Profit today')}}</small><b class="plus">{{usd(d.today.profit_usd)}}</b></div>
        <div class="kpi"><small>{{AR('مبيعات 30 يوماً','30 days')}}</small><b>{{usd(d.month.sales_usd)}}</b><div class="sub">{{d.month.orders}} {{AR('طلب','orders')}}</div></div>
        <div class="kpi"><small>{{AR('ربح 30 يوماً','30d profit')}}</small><b class="plus">{{usd(d.month.profit_usd)}}</b></div>
      </div>
      <div class="card mt"><div class="row sb"><b>{{AR('المبيعات آخر 14 يوماً','Sales, last 14 days')}}</b><small class="muted">{{usd(d.week.sales_usd)}} / 7d</small></div><bars :series="d.series"></bars></div>
      <div class="card mt">
        <div class="row sb"><span>💼 {{AR('رصيدك في الصانع (تُخصم منه تكلفة المنصة)','Maker balance (platform cost)')}}</span><b :class="d.maker_balance_usd<5?'minus':''">{{usd(d.maker_balance_usd)}}</b></div>
        <div class="row sb mt"><span>👥 {{AR('الزبائن','Customers')}}</span><b>{{d.customers}}</b></div>
        <div class="row sb mt"><span>💳 {{AR('أرصدة الزبائن','Customers balance')}}</span><b>{{usd(d.customers_balance_usd)}}</b></div>
        <div class="row sb mt"><span>🧾 {{AR('إيصالات بانتظارك','Pending receipts')}}</span><span class="tag" :class="d.pending_receipts?'warn':'ok'">{{d.pending_receipts}}</span></div>
        <div class="row sb mt"><span>⏳ {{AR('طلبات قيد الانتظار','Pending orders')}}</span><span class="tag" :class="d.pending_orders?'warn':'ok'">{{d.pending_orders}}</span></div>
      </div>
      <div v-if="d.maker_balance_usd<5" class="ann mt">⚠️ {{AR('رصيدك في الصانع منخفض، اشحنه من بوت الصانع ← «رصيدي» حتى لا يتوقف البيع.','Low maker balance — top up from the maker bot.')}}</div>
    </div><div v-else class="skel"></div>`,
  };

  const SellerOrders = {
    setup() {
      const st = ref(""), q = ref(""), items = ref(null);
      async function load() { const j = await api("/seller/orders?status=" + st.value + "&q=" + encodeURIComponent(q.value)); items.value = j.orders || []; }
      onMounted(load); watch(st, load);
      async function refund(o) {
        const r = ask(AR("سبب الإلغاء (يصل للزبون):", "Reason:"), "");
        if (r === null) return;
        const j = await api("/seller/orders", { body: { order_id: o.order_id, action: "refund", reason: r } });
        toast(j.message || (j.ok ? "✅" : "⚠️")); if (j.ok) load();
      }
      const F = [["", AR("الكل", "All")], ["queued,pending", AR("بالانتظار", "Pending")], ["processing,waiting_sms", AR("قيد التنفيذ", "Processing")], ["completed", AR("مكتمل", "Done")], ["refunded,canceled", AR("مسترجع", "Refunded")]];
      return { st, q, items, load, refund, F, usd, stLabel, stTag, copy, AR, secName };
    },
    template: `<div>
      <div class="chips"><button v-for="f in F" :key="f[0]" class="chip" :class="{on:st===f[0]}" @click="st=f[0]">{{f[1]}}</button></div>
      <div class="search"><span>🔎</span><input class="inp" v-model="q" @keyup.enter="load" :placeholder="AR('رقم الطلب أو الهدف','Order id or target')"></div>
      <div v-if="items===null" class="skel mt"></div>
      <div v-else-if="!items.length" class="empty"><div>📭</div>{{AR('لا طلبات','No orders')}}</div>
      <div class="plist mt" v-else><div class="card" v-for="o in items" :key="o.order_id">
        <div class="row sb"><b style="font-size:14px">{{o.service}}</b><span class="tag" :class="stTag(o.status)">{{stLabel(o.status)}}</span></div>
        <div class="row sb tiny muted mt"><span class="copy" @click="copy(o.order_id)">#{{o.order_id.slice(-8)}}</span><span>{{secName(o.sec)}}</span><span>{{o.at}}</span></div>
        <div class="row sb tiny mt"><span>👤 {{o.user_id}}</span><span>{{AR('البيع','Sale')}} <b>{{usd(o.price_usd)}}</b></span><span>{{AR('التكلفة','Cost')}} {{usd(o.cost_usd)}}</span><span class="plus">{{usd(o.price_usd-o.cost_usd)}}</span></div>
        <div class="tiny muted mt" dir="ltr" style="text-align:start" v-if="o.target">🎯 {{o.target}}</div>
        <div class="tiny mt" v-if="o.delivery" style="white-space:pre-wrap">📦 {{o.delivery}}</div>
        <div class="row mt" v-if="['queued','pending'].includes(o.status)"><button class="btn bad sm" @click="refund(o)">↩ {{AR('إلغاء واسترجاع','Cancel & refund')}}</button></div>
      </div></div></div>`,
  };

  const SellerPricing = {
    setup() {
      const d = ref(null), sec = ref(""), q = ref("");
      async function load(body) {
        const j = await api("/seller/pricing", body ? { body } : {});
        if (j.ok) { d.value = j; if (!sec.value) sec.value = Object.keys(j.margins)[0] || ""; } else toast(j.message);
      }
      onMounted(() => load());
      const items = computed(() => (d.value ? d.value.items.filter((x) => x.sec === sec.value && (!q.value || x.name.includes(q.value))) : []));
      async function saveMargin() { const m = d.value.margins[sec.value]; await load({ sec: sec.value, margin: { type: m.type, val: Number(m.val) } }); toast("✅"); }
      async function setPrice(x) {
        const v = ask(AR("سعر البيع بالدولار (فارغ = حسب الهامش):", "Price in USD (empty = margin):"), x.price_usd);
        if (v === null) return; await load({ sec: x.sec, product_id: x.id, price_usd: v.trim() === "" ? null : Number(v) });
      }
      async function hide(x) { await load({ sec: x.sec, product_id: x.id, hidden: !x.hidden }); }
      return { d, sec, q, items, saveMargin, setPrice, hide, usd, AR, secName };
    },
    template: `<div v-if="d">
      <div class="chips"><button v-for="(m,k) in d.margins" :key="k" class="chip" :class="{on:sec===k}" @click="sec=k">{{secName(k)}}</button></div>
      <div class="card" v-if="d.margins[sec]"><b>📈 {{AR('هامش ربحك في هذا القسم','Your margin in this section')}}</b>
        <div class="tiny muted">{{AR('سعر البيع = تكلفة المنتج + هامشك، ولا يقل أبداً عن سعر المنصة.','Price = cost + margin, never below platform price.')}}
          <span v-if="d.platform_margins[sec]">{{AR('هامش المنصة','Platform margin')}}: {{d.platform_margins[sec].val}}{{d.platform_margins[sec].type==='percent'?'%':'$'}}</span></div>
        <div class="row mt"><select class="inp" style="width:auto" v-model="d.margins[sec].type"><option value="percent">%</option><option value="fixed">$</option></select>
          <input class="inp" type="number" v-model="d.margins[sec].val"><button class="btn p" @click="saveMargin">{{AR('حفظ','Save')}}</button></div></div>
      <div class="search mt"><span>🔎</span><input class="inp" v-model="q"></div>
      <div class="card mt" style="padding:6px 10px"><table class="t"><tr><th>{{AR('المنتج','Product')}}</th><th>{{AR('التكلفة','Cost')}}</th><th>{{AR('سعرك','Price')}}</th><th>{{AR('ربحك','Profit')}}</th><th></th></tr>
        <tr v-for="x in items" :key="x.id" :style="{opacity:x.hidden?.45:1}"><td style="font-size:12px">{{x.name}}<span v-if="x.unit==='1k'" class="c3"> /1k</span></td><td>{{usd(x.cost_usd)}}</td>
          <td><a href="#" @click.prevent="setPrice(x)">{{usd(x.price_usd)}} ✏️</a></td><td class="plus">{{usd(x.profit_usd)}}</td>
          <td><button class="btn sm" @click="hide(x)">{{x.hidden?AR('إظهار','Show'):AR('إخفاء','Hide')}}</button></td></tr></table></div>
    </div><div v-else class="skel"></div>`,
  };

  const SellerCustomers = {
    setup() {
      const q = ref(""), items = ref(null);
      async function load() { const j = await api("/seller/customers?q=" + encodeURIComponent(q.value)); items.value = j.customers || []; }
      onMounted(load);
      async function act(c, action) {
        const body = { uid: c.uid, action };
        if (action === "credit" || action === "debit") { const v = ask(AR("المبلغ بالدولار:", "Amount (USD):")); if (!v) return; body.amount_usd = Number(v); body.note = ask(AR("ملاحظة (اختياري):", "Note:")) || ""; }
        if (action === "message") { const v = ask(AR("نص الرسالة:", "Message:")); if (!v) return; body.text = v; }
        const j = await api("/seller/customers", { body }); toast(j.ok ? "✅" : (j.message || "⚠️")); if (j.ok) load();
      }
      return { q, items, load, act, usd, AR };
    },
    template: `<div>
      <div class="search"><span>🔎</span><input class="inp" v-model="q" @keyup.enter="load" :placeholder="AR('اسم، يوزر أو آيدي','Name, username or id')"></div>
      <div v-if="items===null" class="skel mt"></div>
      <div class="plist mt"><div class="card" v-for="c in items" :key="c.uid">
        <div class="row sb"><div><b>{{c.name||c.uid}}</b> <span class="tiny muted" v-if="c.username">@{{c.username}}</span><div class="tiny c3">{{c.uid}} · {{c.last_seen}}</div></div><b>{{usd(c.balance_usd)}}</b></div>
        <div class="row wrapf mt" style="gap:6px"><button class="btn sm" @click="act(c,'credit')">➕ {{AR('رصيد','Credit')}}</button><button class="btn sm" @click="act(c,'debit')">➖ {{AR('خصم','Debit')}}</button>
          <button class="btn sm" @click="act(c,'message')">✉️ {{AR('رسالة','Message')}}</button>
          <button class="btn sm" :class="c.banned?'ok':'bad'" @click="act(c,c.banned?'unban':'ban')">{{c.banned?AR('رفع الحظر','Unban'):AR('حظر','Ban')}}</button></div>
      </div></div></div>`,
  };

  const SellerPayments = {
    setup() {
      const d = ref(null), rc = ref([]), pk = ref("");
      async function load(body) {
        const j = await api("/seller/payments", body ? { body } : {});
        if (j.ok) { d.value = j; pk.value = j.packages.join(", "); }
        const r = await api("/seller/receipts"); rc.value = r.receipts || [];
      }
      onMounted(() => load());
      async function saveAll() {
        await load({ methods: d.value.methods, packages: pk.value.split(/[,،\s]+/).filter(Boolean).map(Number), custom_min: Number(d.value.custom_min),
          custom_max: Number(d.value.custom_max), stars_enabled: d.value.stars_enabled, store_currency: d.value.store_currency });
        haptic(); toast("✅");
      }
      function addMethod() { d.value.methods.push({ id: "", name: "", account: "", instructions: "", currency: "USD", on: true, min: 1, max: 1000 }); }
      async function rcAct(r, action) {
        const body = { receipt_id: r.id, action };
        if (action === "approve") { const v = ask(AR("المبلغ الواصل بالدولار (اتركه كما هو للموافقة):", "Received USD:"), r.amount_usd); if (v === null) return; body.amount_usd = Number(v); }
        else { const v = ask(AR("سبب الرفض:", "Reason:")); if (v === null) return; body.reason = v; }
        const j = await api("/seller/receipts", { body }); toast(j.ok ? "✅" : (j.message || "⚠️")); load();
      }
      return { d, rc, pk, saveAll, addMethod, rcAct, usd, AR };
    },
    template: `<div v-if="d">
      <div class="h">🧾 {{AR('إيصالات الشحن بانتظارك','Pending top-up receipts')}} <span class="tag" :class="rc.length?'warn':'ok'">{{rc.length}}</span></div>
      <div class="card" v-if="!rc.length"><span class="muted tiny">{{AR('لا إيصالات معلقة ✅','No pending receipts ✅')}}</span></div>
      <div class="card" v-for="r in rc" :key="r.id"><div class="row sb"><b>{{r.name}} <span class="tiny muted" v-if="r.username">@{{r.username}}</span></b><b>{{r.amount}} {{r.currency}}</b></div>
        <div class="tiny muted">{{r.method}} · ≈ {{usd(r.amount_usd)}}</div><div class="tiny mt" style="white-space:pre-wrap;word-break:break-all">{{r.proof}}</div>
        <div class="row mt"><button class="btn ok sm grow" @click="rcAct(r,'approve')">✅ {{AR('قبول','Approve')}}</button><button class="btn bad sm grow" @click="rcAct(r,'reject')">❌ {{AR('رفض','Reject')}}</button></div></div>
      <div class="h">💳 {{AR('طرق الدفع اليدوية','Manual payment methods')}} <button class="btn sm" @click="addMethod">＋</button></div>
      <div class="card" v-for="(m,i) in d.methods" :key="i">
        <div class="row sb"><input class="inp" v-model="m.name" :placeholder="AR('اسم الطريقة (مثال: شام كاش)','Method name')"><toggle v-model="m.on"></toggle></div>
        <label class="lbl">{{AR('رقم الحساب / العنوان','Account / address')}}</label><input class="inp" v-model="m.account" dir="ltr">
        <label class="lbl">{{AR('التعليمات للزبون','Instructions')}}</label><textarea class="inp" v-model="m.instructions"></textarea>
        <div class="row mt"><div class="grow"><label class="lbl">{{AR('عملة الطريقة','Currency')}}</label><select class="inp" v-model="m.currency"><option v-for="c in d.currencies" :key="c.code" :value="c.code">{{c.code}} — {{c.ar}}</option></select></div>
          <div style="width:90px"><label class="lbl">{{AR('أدنى $','Min $')}}</label><input class="inp" type="number" v-model.number="m.min"></div><div style="width:90px"><label class="lbl">{{AR('أقصى $','Max $')}}</label><input class="inp" type="number" v-model.number="m.max"></div></div>
        <button class="btn sm bad mt" @click="d.methods.splice(i,1)">🗑 {{AR('حذف','Delete')}}</button></div>
      <div class="h">⭐ {{AR('الشحن والباقات','Top-up & packs')}}</div>
      <div class="card"><div class="row sb"><span>{{AR('الشحن بنجوم تيليجرام','Telegram Stars top-up')}}</span><toggle v-model="d.stars_enabled"></toggle></div>
        <label class="lbl">{{AR('الباقات بالدولار (افصل بفاصلة)','Packs in USD (comma separated)')}}</label><input class="inp" v-model="pk" dir="ltr">
        <div class="row"><div class="grow"><label class="lbl">{{AR('أقل مبلغ مخصص $','Custom min $')}}</label><input class="inp" type="number" v-model="d.custom_min"></div>
          <div class="grow"><label class="lbl">{{AR('أكبر مبلغ مخصص $','Custom max $')}}</label><input class="inp" type="number" v-model="d.custom_max"></div></div>
        <label class="lbl">{{AR('عملة المتجر الافتراضية','Default store currency')}}</label>
        <select class="inp" v-model="d.store_currency"><option v-for="c in d.currencies" :key="c.code" :value="c.code">{{c.code}} — {{c.ar}} ({{c.rate}})</option></select></div>
      <button class="btn p blk mt" @click="saveAll">💾 {{AR('حفظ إعدادات الدفع','Save payment settings')}}</button>
    </div><div v-else class="skel"></div>`,
  };

  const SellerMarketing = {
    setup() {
      const d = ref(null), nc = reactive({ code: "", type: "percent", value: 10, max_uses: 100, per_user: 1, min_order: 0, expires: "" }), bc = ref("");
      async function load(body) { const j = await api("/seller/marketing", body ? { body } : {}); if (j.ok) d.value = j; else toast(j.message); return j; }
      onMounted(() => load());
      async function addCoupon() { const j = await load(Object.assign({ action: "coupon_save" }, nc)); if (j.ok) { toast("✅"); nc.code = ""; } }
      async function delCoupon(c) { if (confirm(c.code + " ?")) await load({ action: "coupon_delete", code: c.code }); }
      async function saveRef() { await load(Object.assign({ action: "referral" }, d.value.referral)); toast("✅"); }
      async function send() { if (!bc.value.trim() || !confirm(AR("إرسال لكل الزبائن؟", "Send to all customers?"))) return; const j = await load({ action: "broadcast", text: bc.value }); toast(j.message || (j.ok ? "✅" : "⚠️")); if (j.ok) bc.value = ""; }
      return { d, nc, bc, addCoupon, delCoupon, saveRef, send, AR };
    },
    template: `<div v-if="d">
      <div class="h">🎟 {{AR('أكواد الخصم','Promo codes')}}</div>
      <div class="card"><div class="row"><input class="inp" v-model="nc.code" :placeholder="AR('الكود','Code')" dir="ltr" style="text-transform:uppercase">
        <select class="inp" style="width:auto" v-model="nc.type"><option value="percent">%</option><option value="fixed">$</option></select><input class="inp" style="width:90px" type="number" v-model.number="nc.value"></div>
        <div class="row"><div class="grow"><label class="lbl">{{AR('عدد الاستخدامات','Max uses')}}</label><input class="inp" type="number" v-model.number="nc.max_uses"></div>
          <div class="grow"><label class="lbl">{{AR('أقل طلب $','Min order $')}}</label><input class="inp" type="number" v-model.number="nc.min_order"></div>
          <div class="grow"><label class="lbl">{{AR('ينتهي','Expires')}}</label><input class="inp" type="date" v-model="nc.expires"></div></div>
        <button class="btn p blk mt" @click="addCoupon">＋ {{AR('إضافة الكود','Add code')}}</button></div>
      <div class="card" v-if="d.coupons.length"><div class="tx" v-for="c in d.coupons" :key="c.code"><span><b dir="ltr">{{c.code}}</b> · {{c.value}}{{c.type==='percent'?'%':'$'}} · {{c.used}}/{{c.max_uses}}</span><button class="btn sm ghost" @click="delCoupon(c)">🗑</button></div></div>
      <div class="h">👥 {{AR('نظام الإحالة','Referrals')}}</div>
      <div class="card"><div class="row sb"><span>{{AR('تفعيل الإحالة','Enable')}}</span><toggle v-model="d.referral.on"></toggle></div>
        <div class="row"><div class="grow"><label class="lbl">{{AR('نسبة من مشتريات المدعو %','Purchase share %')}}</label><input class="inp" type="number" v-model.number="d.referral.percent"></div>
          <div class="grow"><label class="lbl">{{AR('مكافأة الدخول $','Signup bonus $')}}</label><input class="inp" type="number" step="0.01" v-model.number="d.referral.signup_bonus"></div></div>
        <button class="btn p blk mt" @click="saveRef">{{AR('حفظ','Save')}}</button></div>
      <div class="h">📣 {{AR('رسالة لكل الزبائن','Broadcast to customers')}}</div>
      <div class="card"><textarea class="inp" v-model="bc" :placeholder="AR('عرض اليوم: خصم 20% على…','Today: 20% off…')"></textarea><button class="btn p blk mt" @click="send">{{AR('إرسال','Send')}}</button></div>
    </div><div v-else class="skel"></div>`,
  };

  const SellerStore = {
    setup() {
      const d = ref(null);
      const COLORS = ["#6d5dfc", "#2563eb", "#0ea5e9", "#10b981", "#16a34a", "#f59e0b", "#ef4444", "#ec4899", "#8b5cf6", "#111827"];
      async function load(body) { const j = await api("/seller/store", body ? { body } : {}); if (j.ok) { d.value = j.store; if (body) { Object.assign(S.store, { name: j.store.name || S.store.name, desc: j.store.desc, logo: j.store.logo, banner: j.store.banner, accent: j.store.accent, announcement: j.store.announcement, support: j.store.support, faq: j.store.faq_enabled ? j.store.faq : [], terms: j.store.terms, help: j.store.help }); document.documentElement.style.setProperty("--accent", j.store.accent); } } }
      onMounted(() => load());
      async function save() { await load(d.value); haptic(); toast("✅"); }
      async function upload(e, key) {
        const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append("file", f, f.name);
        const j = await api("/seller/upload", { body: fd }); if (j.ok) { d.value[key] = j.url; toast("✅"); } else toast(j.message || "⚠️");
      }
      return { d, COLORS, save, upload, AR };
    },
    template: `<div v-if="d">
      <div class="h">🎨 {{AR('مظهر المتجر','Appearance')}}</div>
      <div class="card"><label class="lbl">{{AR('اسم المتجر','Store name')}}</label><input class="inp" v-model="d.name">
        <label class="lbl">{{AR('وصف قصير','Short description')}}</label><input class="inp" v-model="d.desc">
        <label class="lbl">{{AR('شريط إعلان أعلى المتجر (اختياري)','Announcement (optional)')}}</label><input class="inp" v-model="d.announcement">
        <label class="lbl">{{AR('الشعار','Logo')}}</label><div class="upl"><img v-if="d.logo" :src="d.logo"><label class="btn sm">📷 {{AR('رفع صورة','Upload')}}<input type="file" accept="image/*" @change="upload($event,'logo')"></label><button v-if="d.logo" class="btn sm ghost" @click="d.logo=''">🗑</button></div>
        <label class="lbl">{{AR('صورة الواجهة (بانر)','Banner')}}</label><div class="upl"><img v-if="d.banner" :src="d.banner" style="width:90px"><label class="btn sm">🖼 {{AR('رفع صورة','Upload')}}<input type="file" accept="image/*" @change="upload($event,'banner')"></label><button v-if="d.banner" class="btn sm ghost" @click="d.banner=''">🗑</button></div>
        <label class="lbl">{{AR('لون المتجر','Accent color')}}</label><div class="swatches"><span v-for="c in COLORS" :key="c" class="sw" :class="{on:d.accent===c}" :style="{background:c}" @click="d.accent=c"></span></div>
        <label class="lbl">{{AR('الوضع','Theme')}}</label><div class="chips"><button v-for="m in [['auto',AR('تلقائي','Auto')],['light',AR('فاتح','Light')],['dark',AR('داكن','Dark')]]" :key="m[0]" class="chip" :class="{on:d.theme===m[0]}" @click="d.theme=m[0]">{{m[1]}}</button></div></div>
      <div class="h">🎧 {{AR('الدعم الفني','Support')}}</div>
      <div class="card"><label class="lbl">{{AR('يوزر حساب الدعم','Support username')}}</label><input class="inp" v-model="d.support.username" placeholder="@support" dir="ltr">
        <label class="lbl">{{AR('قناة المتجر','Store channel')}}</label><input class="inp" v-model="d.support.channel" placeholder="@channel" dir="ltr">
        <label class="lbl">WhatsApp</label><input class="inp" v-model="d.support.whatsapp" placeholder="+963…" dir="ltr">
        <label class="lbl">Email</label><input class="inp" v-model="d.support.email" dir="ltr">
        <label class="lbl">{{AR('روابط إضافية','Extra links')}} <a href="#" @click.prevent="d.support.links.push({label:'',url:''})">＋</a></label>
        <div class="row mt" v-for="(l,i) in d.support.links" :key="i"><input class="inp" v-model="l.label" :placeholder="AR('الاسم','Label')"><input class="inp" v-model="l.url" placeholder="https://" dir="ltr"><button class="btn sm ghost" @click="d.support.links.splice(i,1)">🗑</button></div></div>
      <div class="h">❓ {{AR('الأسئلة الشائعة (اختيارية)','FAQ (optional)')}} <toggle v-model="d.faq_enabled"></toggle></div>
      <div class="card" v-if="d.faq_enabled"><div v-for="(f,i) in d.faq" :key="i" class="mt"><input class="inp" v-model="f.q" :placeholder="AR('السؤال','Question')"><textarea class="inp mt" v-model="f.a" :placeholder="AR('الجواب','Answer')"></textarea>
          <button class="btn sm ghost" @click="d.faq.splice(i,1)">🗑</button></div><button class="btn sm mt" @click="d.faq.push({q:'',a:''})">＋ {{AR('سؤال','Question')}}</button></div>
      <div class="h">📄 {{AR('صفحات أسفل المتجر','Footer pages')}}</div>
      <div class="card"><label class="lbl">{{AR('المساعدة','Help')}}</label><textarea class="inp" v-model="d.help"></textarea><label class="lbl">{{AR('شروط الاستخدام','Terms of use')}}</label><textarea class="inp" v-model="d.terms"></textarea></div>
      <button class="btn p blk mt" @click="save">💾 {{AR('حفظ','Save')}}</button>
    </div><div v-else class="skel"></div>`,
  };

  const Dash = {
    components: { SellerOverview, SellerOrders, SellerPricing, SellerCustomers, SellerPayments, SellerMarketing, SellerStore },
    setup() {
      const want = new URLSearchParams(location.search).get("sec");
      const sec = ref(["ov", "orders", "pricing", "cust", "pay", "mkt", "store"].includes(want) ? want : "ov");
      const NAV = computed(() => [["ov", "📊", AR("نظرة عامة", "Overview")], ["orders", "📦", AR("الطلبات", "Orders")], ["pricing", "🏷", AR("الأسعار", "Pricing")],
        ["cust", "👥", AR("الزبائن", "Customers")], ["pay", "💳", AR("الدفع", "Payments")], ["mkt", "📣", AR("التسويق", "Marketing")], ["store", "🎨", AR("المتجر", "Store")]]);
      return { sec, NAV };
    },
    template: `<div class="wrap"><div class="dashnav"><div class="chips"><button v-for="n in NAV" :key="n[0]" class="chip" :class="{on:sec===n[0]}" @click="sec=n[0]">{{n[1]}} {{n[2]}}</button></div></div>
      <seller-overview v-if="sec==='ov'"></seller-overview><seller-orders v-else-if="sec==='orders'"></seller-orders><seller-pricing v-else-if="sec==='pricing'"></seller-pricing>
      <seller-customers v-else-if="sec==='cust'"></seller-customers><seller-payments v-else-if="sec==='pay'"></seller-payments>
      <seller-marketing v-else-if="sec==='mkt'"></seller-marketing><seller-store v-else-if="sec==='store'"></seller-store></div>`,
  };

  // ═════════════ لوحة المدير ═════════════
  const AdminOverview = {
    setup() {
      const d = ref(null);
      async function load(body) { const j = body ? await api("/admin/settings", { body }) : null; const o = await api("/admin/overview"); if (o.ok) d.value = o; }
      onMounted(() => load());
      async function maint(v) { if (!confirm(v ? AR("تفعيل الصيانة لكل المستخدمين؟", "Enable maintenance?") : AR("فتح المنصة للجميع؟", "Open the platform?"))) return; await load({ maintenance: v }); toast("✅"); }
      return { d, maint, usd, AR };
    },
    template: `<div v-if="d">
      <div class="card row sb" :style="{borderColor:d.maintenance?'var(--warn)':'var(--ok)'}"><span>{{d.maintenance?'🛠 '+AR('المنصة في وضع الصيانة','Maintenance mode ON'):'🟢 '+AR('المنصة مفتوحة للجميع','Platform is live')}}</span><toggle :model-value="!d.maintenance" @update:model-value="maint(!$event)"></toggle></div>
      <div class="kpis mt">
        <div class="kpi"><small>{{AR('مبيعات اليوم','Sales today')}}</small><b>{{usd(d.today.sales_usd)}}</b><div class="sub">{{d.today.orders}}</div></div>
        <div class="kpi"><small>{{AR('تحصيل المنصة اليوم','Platform intake today')}}</small><b class="plus">{{usd(d.today.cost_usd)}}</b></div>
        <div class="kpi"><small>{{AR('مبيعات 30 يوماً','Sales 30d')}}</small><b>{{usd(d.month.sales_usd)}}</b><div class="sub">{{d.month.orders}}</div></div>
        <div class="kpi"><small>{{AR('تحصيل المنصة 30 يوماً','Platform intake 30d')}}</small><b class="plus">{{usd(d.month.cost_usd)}}</b></div></div>
      <div class="card mt"><b>{{AR('المبيعات آخر 14 يوماً','Sales, 14 days')}}</b><bars :series="d.series"></bars></div>
      <div class="card mt"><div class="row sb"><span>🤖 {{AR('البوتات','Bots')}}</span><b>{{d.active_bots}} / {{d.bots}}</b></div>
        <div class="row sb mt"><span>👤 {{AR('البائعون','Sellers')}}</span><b>{{d.sellers}}</b></div>
        <div class="row sb mt"><span>🏦 {{AR('أرصدة البائعين','Sellers balances')}}</span><b>{{usd(d.sellers_balance_usd)}}</b></div>
        <div class="row sb mt"><span>🧾 {{AR('شحنات بائعين بانتظارك','Pending seller top-ups')}}</span><span class="tag" :class="d.pending_topups?'warn':'ok'">{{d.pending_topups}}</span></div>
        <div class="row sb mt"><span>📦 {{AR('طلبات تحتاج تنفيذاً','Orders to fulfil')}}</span><span class="tag" :class="d.queued_orders?'warn':'ok'">{{d.queued_orders}}</span></div></div>
    </div><div v-else class="skel"></div>`,
  };

  const AdminOrders = {
    setup() {
      const items = ref(null), st = ref("queued,pending");
      async function load() { const j = await api("/admin/orders?status=" + st.value); items.value = j.orders || []; }
      onMounted(load); watch(st, load);
      async function deliver(o) { const v = ask(AR("بيانات التسليم (كود، حساب، ملاحظة) — تصل للزبون:", "Delivery data:")); if (!v) return; const j = await api("/admin/orders", { body: { order_id: o.order_id, action: "deliver", text: v } }); toast(j.ok ? "✅" : j.message); load(); }
      async function refund(o) { const v = ask(AR("سبب الاسترجاع:", "Reason:")); if (v === null) return; const j = await api("/admin/orders", { body: { order_id: o.order_id, action: "refund", reason: v } }); toast(j.message || "✅"); load(); }
      return { items, st, load, deliver, refund, usd, stLabel, stTag, copy, AR, secName };
    },
    template: `<div><div class="chips"><button v-for="f in [['queued,pending',AR('تحتاج تنفيذاً','To fulfil')],['processing,waiting_sms',AR('قيد التنفيذ','Processing')],['completed',AR('مكتملة','Done')],['refunded,canceled',AR('مسترجعة','Refunded')]]" :key="f[0]" class="chip" :class="{on:st===f[0]}" @click="st=f[0]">{{f[1]}}</button></div>
      <div v-if="items===null" class="skel"></div><div v-else-if="!items.length" class="empty"><div>✅</div>{{AR('لا شيء هنا','Nothing here')}}</div>
      <div class="plist" v-else><div class="card" v-for="o in items" :key="o.order_id">
        <div class="row sb"><b style="font-size:14px">{{o.service}}</b><span class="tag" :class="stTag(o.status)">{{stLabel(o.status)}}</span></div>
        <div class="row sb tiny muted mt"><span class="copy" @click="copy(o.order_id)">#{{o.order_id.slice(-8)}}</span><span>{{secName(o.sec)}} · bot {{o.bot_id}}</span><span>{{o.at}}</span></div>
        <div class="row sb tiny mt"><span>{{AR('البيع','Sale')}} {{usd(o.price_usd)}}</span><span>{{AR('تكلفة المنصة','Platform')}} <b class="plus">{{usd(o.cost_usd)}}</b></span><span>×{{o.qty}}</span></div>
        <div class="sum tiny" dir="ltr" style="text-align:start" v-if="o.target">🎯 <span class="copy" @click="copy(o.target)">{{o.target}}</span></div>
        <div class="row mt" v-if="['queued','pending'].includes(o.status)"><button class="btn ok sm grow" @click="deliver(o)">📦 {{AR('تسليم','Deliver')}}</button><button class="btn bad sm grow" @click="refund(o)">↩ {{AR('استرجاع','Refund')}}</button></div>
      </div></div></div>`,
  };

  const AdminSellers = {
    setup() {
      const q = ref(""), items = ref(null);
      async function load() { const j = await api("/admin/sellers?q=" + encodeURIComponent(q.value)); items.value = j.bots || []; }
      onMounted(load);
      async function adj(b, action) { const v = ask(AR("المبلغ بالدولار:", "Amount USD:")); if (!v) return; const j = await api("/admin/sellers", { body: { owner_id: b.owner_id, amount_usd: Number(v), action } }); toast(j.ok ? "✅ " + usd(j.balance_usd) : j.message); load(); }
      return { q, items, load, adj, usd, AR };
    },
    template: `<div><div class="search"><span>🔎</span><input class="inp" v-model="q" @keyup.enter="load" :placeholder="AR('يوزر البوت أو آيدي البائع','Bot username or owner id')"></div>
      <div v-if="items===null" class="skel mt"></div>
      <div class="plist mt"><div class="card" v-for="b in items" :key="b.bot_id">
        <div class="row sb"><b>@{{b.username}}</b><span class="tag" :class="b.status==='active'?'ok':'bad'">{{b.tpl}}</span></div>
        <div class="row sb tiny mt"><span>👤 {{b.owner_id}}</span><span>{{AR('رصيد البائع','Balance')}} <b>{{usd(b.owner_balance_usd)}}</b></span><span>30d {{usd(b.sales_30d)}}</span></div>
        <div class="row mt"><button class="btn sm" @click="adj(b,'credit')">➕ {{AR('شحن البائع','Credit')}}</button><button class="btn sm" @click="adj(b,'debit')">➖ {{AR('خصم','Debit')}}</button></div>
      </div></div></div>`,
  };

  const AdminTopups = {
    setup() {
      const items = ref(null), st = ref(null);
      async function load() { const j = await api("/admin/topups"); items.value = j.receipts || []; const s = await api("/admin/settings"); st.value = s; }
      onMounted(load);
      async function act(r, action) {
        const body = { receipt_id: r.id, action };
        if (action === "approve") { const v = ask(AR("المبلغ الواصل بالدولار:", "Received USD:"), r.amount_usd); if (v === null) return; body.amount_usd = Number(v); }
        else { const v = ask(AR("سبب الرفض:", "Reason:")); if (v === null) return; body.reason = v; }
        const j = await api("/admin/topups", { body }); toast(j.ok ? "✅" : j.message); load();
      }
      async function saveMethods() { const j = await api("/admin/settings", { body: { seller_methods: st.value.seller_methods } }); toast(j.ok ? "✅" : j.message); }
      return { items, st, act, saveMethods, usd, AR };
    },
    template: `<div><div class="h">🧾 {{AR('إيصالات شحن البائعين','Seller top-up receipts')}}</div>
      <div v-if="items && !items.length" class="card"><span class="muted tiny">{{AR('لا إيصالات معلقة ✅','None pending ✅')}}</span></div>
      <div class="card" v-for="r in items" :key="r.id"><div class="row sb"><b>{{r.name}} ({{r.uid}})</b><b>{{usd(r.amount_usd)}}</b></div><div class="tiny muted">{{r.method}}</div>
        <div class="tiny mt" style="white-space:pre-wrap;word-break:break-all">{{r.proof}}</div>
        <div class="row mt"><button class="btn ok sm grow" @click="act(r,'approve')">✅ {{AR('قبول','Approve')}}</button><button class="btn bad sm grow" @click="act(r,'reject')">❌ {{AR('رفض','Reject')}}</button></div></div>
      <template v-if="st"><div class="h">💳 {{AR('طرق شحن البائعين','Seller payment methods')}} <button class="btn sm" @click="st.seller_methods.push({name:'',account:'',instructions:''})">＋</button></div>
        <div class="card" v-for="(m,i) in st.seller_methods" :key="i"><input class="inp" v-model="m.name" :placeholder="AR('الاسم','Name')"><input class="inp mt" v-model="m.account" dir="ltr" :placeholder="AR('الحساب','Account')">
          <textarea class="inp mt" v-model="m.instructions" :placeholder="AR('التعليمات','Instructions')"></textarea><button class="btn sm ghost" @click="st.seller_methods.splice(i,1)">🗑</button></div>
        <button class="btn p blk mt" @click="saveMethods">💾 {{AR('حفظ','Save')}}</button></template></div>`,
  };

  const AdminCatalog = {
    setup() {
      const d = ref(null), sec = ref("smm"), q = ref(""), mg = reactive({ key: "global", type: "percent", val: 10 });
      async function load(body) { const j = await api("/admin/catalog", body ? { body } : {}); if (j.ok) d.value = j; else toast(j.message); }
      onMounted(() => load());
      const items = computed(() => (d.value ? (d.value.catalog[sec.value] || []).filter((x) => !q.value || (x.id + x.name).includes(q.value)) : []));
      async function edit(x) {
        const ps = ask(AR("رقم الخدمة لدى المزود:", "Provider service id:"), x.ps); if (ps === null) return;
        const cost = ask(AR("التكلفة الحقيقية بالدولار" + (sec.value === "smm" ? " لكل 1000:" : ":"), "Real cost USD:"), x.cost); if (cost === null) return;
        await load({ sec: sec.value, item_id: x.id, ps, cost: cost === "" ? null : Number(cost) }); toast("✅");
      }
      async function toggle(x) { await load({ sec: sec.value, item_id: x.id, off: !x.off }); }
      async function saveMargin() { await load({ margin_key: mg.key, margin_type: mg.type, margin_val: Number(mg.val) }); toast("✅"); }
      const mlabel = (k) => (k === "global" ? AR("عام", "Global") : k.replace("tpl:", ""));
      return { d, sec, q, items, mg, edit, toggle, saveMargin, mlabel, usd, AR, secName };
    },
    template: `<div v-if="d">
      <div class="h">📈 {{AR('هوامش المنصة','Platform margins')}}</div>
      <div class="card"><div class="row wrapf" style="gap:6px"><span class="tag" v-for="(v,k) in d.margins" :key="k">{{mlabel(k)}}: {{v.val}}{{v.type==='percent'?'%':'$'}}</span></div>
        <div class="row mt"><select class="inp" v-model="mg.key"><option value="global">{{AR('عام','Global')}}</option><option v-for="s in ['digital','smm','sms','tgstars']" :key="s" :value="'tpl:'+s">{{secName(s)}}</option></select>
          <select class="inp" style="width:auto" v-model="mg.type"><option value="percent">%</option><option value="fixed">$</option></select><input class="inp" style="width:80px" type="number" v-model="mg.val"><button class="btn p" @click="saveMargin">✓</button></div></div>
      <div class="h">🧩 {{AR('كتالوج المنصة وربط المزودين','Catalog & provider mapping')}}</div>
      <div class="chips"><button v-for="s in ['smm','sms','tgstars','digital']" :key="s" class="chip" :class="{on:sec===s}" @click="sec=s">{{secName(s)}}</button></div>
      <div class="search"><span>🔎</span><input class="inp" v-model="q"></div>
      <div class="card mt" style="padding:6px 10px"><table class="t"><tr><th>{{AR('المنتج','Item')}}</th><th>{{AR('التكلفة','Cost')}}</th><th>{{AR('رقم المزود','Prov. id')}}</th><th></th></tr>
        <tr v-for="x in items" :key="x.id" :style="{opacity:x.off?.45:1}"><td style="font-size:12px">{{x.name}}<div class="c3 tiny" dir="ltr">{{x.id}}</div></td><td><a href="#" @click.prevent="edit(x)">{{usd(x.cost)}}</a></td>
          <td dir="ltr"><a href="#" @click.prevent="edit(x)">{{x.ps||'—'}}</a></td><td><button class="btn sm" @click="toggle(x)">{{x.off?AR('إظهار','Show'):AR('إخفاء','Hide')}}</button></td></tr></table></div>
    </div><div v-else class="skel"></div>`,
  };

  const AdminProviders = {
    setup() {
      const d = ref(null), sec = ref("smm"), n = reactive({ name: "", api_url: "", api_key: "" }), bal = ref(null);
      async function load(body) { const j = await api("/admin/providers", body ? { body } : {}); if (j.ok) d.value = j.providers; else toast(j.message); return j; }
      onMounted(() => load());
      async function add() { const j = await load(Object.assign({ sec: sec.value, action: "add" }, n)); if (j.ok) { n.name = n.api_url = n.api_key = ""; toast("✅"); } }
      async function check() { bal.value = null; const j = await api("/admin/provider_balance?sec=" + sec.value); bal.value = j.results || []; }
      return { d, sec, n, bal, add, check, load, AR, secName };
    },
    template: `<div v-if="d"><div class="chips"><button v-for="s in ['smm','sms','tgstars']" :key="s" class="chip" :class="{on:sec===s}" @click="sec=s;bal=null">{{secName(s)}}</button></div>
      <div class="card"><div v-if="!d[sec].length" class="muted tiny">{{AR('لا مزودين — لن يُباع هذا القسم حتى تضيف مزوداً','No providers — this section will not sell')}}</div>
        <div class="tx" v-for="(p,i) in d[sec]" :key="i"><span><b>{{p.name}}</b><div class="tiny c3" dir="ltr">{{p.api_url}} · {{p.key_hint}}</div></span>
          <span class="row"><toggle :model-value="p.on" @update:model-value="load({sec,action:'toggle',index:i})"></toggle><button class="btn sm ghost" @click="load({sec,action:'delete',index:i})">🗑</button></span></div>
        <button class="btn sm mt" @click="check" v-if="d[sec].length">🧪 {{AR('فحص رصيد المزودين','Check balances')}}</button>
        <div v-if="bal" class="sum tiny"><div v-for="b in bal" :key="b.name">{{b.name}}: <b v-if="b.balance!=null">\${{b.balance}}</b><span v-else class="minus">{{b.error}}</span></div></div></div>
      <div class="h">＋ {{AR('إضافة مزود','Add provider')}}</div>
      <div class="card"><input class="inp" v-model="n.name" :placeholder="AR('الاسم','Name')"><input class="inp mt" v-model="n.api_url" placeholder="https://panel.com/api/v2" dir="ltr">
        <input class="inp mt" v-model="n.api_key" placeholder="API key" dir="ltr"><button class="btn p blk mt" @click="add">{{AR('إضافة','Add')}}</button></div></div><div v-else class="skel"></div>`,
  };

  const Admin = {
    components: { AdminOverview, AdminOrders, AdminSellers, AdminTopups, AdminCatalog, AdminProviders },
    setup() {
      const sec = ref("ov");
      const NAV = computed(() => [["ov", "📊", AR("نظرة عامة", "Overview")], ["orders", "📦", AR("طلبات التنفيذ", "Fulfilment")], ["sellers", "🤖", AR("البائعون", "Sellers")],
        ["topups", "🧾", AR("شحن البائعين", "Top-ups")], ["catalog", "🧩", AR("الكتالوج والهوامش", "Catalog")], ["prov", "🔌", AR("المزودون", "Providers")]]);
      return { sec, NAV };
    },
    template: `<div class="wrap"><div class="dashnav"><div class="chips"><button v-for="n in NAV" :key="n[0]" class="chip" :class="{on:sec===n[0]}" @click="sec=n[0]">{{n[1]}} {{n[2]}}</button></div></div>
      <admin-overview v-if="sec==='ov'"></admin-overview><admin-orders v-else-if="sec==='orders'"></admin-orders><admin-sellers v-else-if="sec==='sellers'"></admin-sellers>
      <admin-topups v-else-if="sec==='topups'"></admin-topups><admin-catalog v-else-if="sec==='catalog'"></admin-catalog><admin-providers v-else-if="sec==='prov'"></admin-providers></div>`,
  };

  window.__S2_start(Dash, Admin);
})();
