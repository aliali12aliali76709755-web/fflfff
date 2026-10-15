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
        if (action === "agent") { const v = ask(AR("نسبة خصم الوكيل % (0 لإلغائه):", "Agent discount % (0 to remove):"), c.agent_pct || 10); if (v === null) return; body.pct = Number(v); }
        const j = await api("/seller/customers", { body }); toast(j.ok ? "✅" : (j.message || "⚠️")); if (j.ok) load();
      }
      return { q, items, load, act, usd, AR };
    },
    template: `<div>
      <div class="search"><span>🔎</span><input class="inp" v-model="q" @keyup.enter="load" :placeholder="AR('اسم، يوزر أو آيدي','Name, username or id')"></div>
      <div v-if="items===null" class="skel mt"></div>
      <div class="plist mt"><div class="card" v-for="c in items" :key="c.uid">
        <div class="row sb"><div><b>{{c.name||c.uid}}</b> <span v-if="c.agent_pct" class="tag info">🤝 {{c.agent_pct}}%</span> <span class="tiny muted" v-if="c.username">@{{c.username}}</span><div class="tiny c3">{{c.uid}} · {{c.last_seen}}</div></div><b>{{usd(c.balance_usd)}}</b></div>
        <div class="row wrapf mt" style="gap:6px"><button class="btn sm" @click="act(c,'credit')">➕ {{AR('رصيد','Credit')}}</button><button class="btn sm" @click="act(c,'debit')">➖ {{AR('خصم','Debit')}}</button>
          <button class="btn sm" @click="act(c,'message')">✉️ {{AR('رسالة','Message')}}</button>
          <button class="btn sm" :class="{ok:c.agent_pct}" @click="act(c,'agent')">🤝 {{c.agent_pct?AR('وكيل','Agent')+' '+c.agent_pct+'%':AR('اجعله وكيلاً','Make agent')}}</button>
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
      const ns = reactive({ title: AR("عرض اليوم", "Today's deal"), pct: 10, hours: 24, scope: "all", target: "" });
      async function addSale() { const j = await load(Object.assign({ action: "sale_create" }, ns)); if (j.ok) toast("🔥 ✅"); }
      async function endSale(x) { if (confirm(AR("إنهاء العرض الآن؟", "End now?"))) await load({ action: "sale_end", id: x.id }); }
      async function saveRep() { await load(Object.assign({ action: "reports" }, d.value.reports)); toast("✅"); }
      const ina = ref(null);
      async function loadIna() { const j = await api("/seller/marketing", { body: { action: "inactive" } }); ina.value = j.inactive || []; }
      async function wb(c) { const j = await api("/seller/customers", { body: { uid: c.uid, action: "winback" } }); toast(j.message || (j.ok ? "✅" : "⚠️")); if (j.ok) c.sent = true; }
      const left = (e) => { const s = Math.max(0, Math.floor(e - S.now / 1000)); return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m"; };
      return { d, nc, bc, addCoupon, delCoupon, saveRef, send, AR, ns, addSale, endSale, saveRep, ina, loadIna, wb, left, secName };
    },
    template: `<div v-if="d">
      <div class="h">🔥 {{AR('عروض بوقت محدود','Limited-time offers')}}</div>
      <div class="card"><div class="muted tiny">{{AR('يظهر للزبائن شريط العرض مع عداد تنازلي والسعر قبل وبعد. السعر لا ينزل أبداً تحت سعر المنصة.','Customers see a countdown banner and slashed prices.')}}</div>
        <input class="inp mt" v-model="ns.title" :placeholder="AR('اسم العرض','Offer title')">
        <div class="row"><div class="grow"><label class="lbl">{{AR('الخصم %','Discount %')}}</label><input class="inp" type="number" v-model.number="ns.pct"></div>
          <div class="grow"><label class="lbl">{{AR('المدة (ساعات)','Hours')}}</label><input class="inp" type="number" v-model.number="ns.hours"></div></div>
        <label class="lbl">{{AR('على','Applies to')}}</label>
        <div class="chips"><button class="chip" :class="{on:ns.scope==='all'}" @click="ns.scope='all'">{{AR('كل المتجر','Whole store')}}</button>
          <button v-for="s in ['smm','sms','digital','tgstars']" :key="s" class="chip" :class="{on:ns.scope==='sec'&&ns.target===s}" @click="ns.scope='sec';ns.target=s">{{secName(s)}}</button></div>
        <button class="btn p blk mt" @click="addSale">🔥 {{AR('ابدأ العرض','Start offer')}}</button>
        <div class="tx mt" v-for="x in d.sales" :key="x.id"><span><b>{{x.title}}</b> · {{x.pct}}% · {{x.scope==='all'?AR('كل المتجر','all'):secName(x.target)}}<div class="tiny c3">⏳ {{left(x.ends)}}</div></span><button class="btn sm bad" @click="endSale(x)">{{AR('إنهاء','End')}}</button></div></div>
      <div class="h">📬 {{AR('التقارير واسترجاع الزبائن','Reports & win-back')}}</div>
      <div class="card"><div class="tx"><span>{{AR('تقرير يومي على تيليجرام (9 مساءً)','Daily Telegram report (9pm)')}}</span><toggle v-model="d.reports.daily"></toggle></div>
        <div class="tx"><span>{{AR('تنبيه الزبائن المتوقفين عن الشراء','Alert me about inactive customers')}}</span><toggle v-model="d.reports.winback"></toggle></div>
        <div class="row"><div class="grow"><label class="lbl">{{AR('متوقف منذ (يوم)','Inactive for (days)')}}</label><input class="inp" type="number" v-model.number="d.reports.wb_days"></div>
          <div class="grow"><label class="lbl">{{AR('خصم الاسترجاع %','Win-back %')}}</label><input class="inp" type="number" v-model.number="d.reports.wb_pct"></div></div>
        <button class="btn p blk mt" @click="saveRep">{{AR('حفظ','Save')}}</button>
        <button class="btn blk mt" @click="loadIna">💤 {{AR('اعرض الزبائن المتوقفين الآن','Show inactive customers')}}</button>
        <div v-if="ina" class="mt"><div v-if="!ina.length" class="muted tiny">{{AR('لا يوجد زبائن متوقفون 👌','Nobody inactive 👌')}}</div>
          <div class="tx" v-for="c in ina" :key="c.uid"><span><b>{{c.username?'@'+c.username:c.name}}</b><div class="tiny c3">{{AR('آخر طلب قبل','Last order')}} {{c.days}} {{AR('يوم','days')}} · {{c.orders}} · \${{c.total}}</div></span>
            <button class="btn sm ok" :disabled="c.sent" @click="wb(c)">{{c.sent?'✅':'🎁 '+d.reports.wb_pct+'%'}}</button></div></div></div>
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
      async function load(body) { const j = await api("/seller/store", body ? { body } : {}); if (j.ok) { d.value = j.store; if (body) { Object.assign(S.store, { name: j.store.name || S.store.name, desc: j.store.desc, logo: j.store.logo, banner: j.store.banner, accent: j.store.accent, announcement: j.store.announcement, support: j.store.support, faq: j.store.faq_enabled ? j.store.faq : [], terms: j.store.terms, help: j.store.help, ads: j.store.ads, ticker: j.store.ticker, bg: j.store.bg }); document.documentElement.style.setProperty("--accent", j.store.accent); } } }
      onMounted(() => load());
      async function save() { await load(d.value); haptic(); toast("✅"); }
      async function upload(e, key) {
        const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append("file", f, f.name);
        const j = await api("/seller/upload", { body: fd }); if (j.ok) { d.value[key] = j.url; toast("✅"); } else toast(j.message || "⚠️");
      }
      async function addAds(e) {
        for (const f of Array.from(e.target.files || []).slice(0, 10)) {
          const fd = new FormData(); fd.append("file", f, f.name);
          const j = await api("/seller/upload", { body: fd });
          if (j.ok) d.value.ads.push({ img: j.url, text: "", url: "" }); else toast(j.message || "⚠️");
        }
        e.target.value = "";
      }
      return { d, COLORS, save, upload, addAds, AR };
    },
    template: `<div v-if="d">
      <div class="h">🎨 {{AR('مظهر المتجر','Appearance')}}</div>
      <div class="card"><label class="lbl">{{AR('اسم المتجر','Store name')}}</label><input class="inp" v-model="d.name">
        <label class="lbl">{{AR('وصف قصير','Short description')}}</label><input class="inp" v-model="d.desc">
        <label class="lbl">{{AR('شريط إعلان أعلى المتجر (اختياري)','Announcement (optional)')}}</label><input class="inp" v-model="d.announcement">
        <label class="lbl">{{AR('الشعار','Logo')}}</label><div class="upl"><img v-if="d.logo" :src="d.logo"><label class="btn sm">📷 {{AR('رفع صورة','Upload')}}<input type="file" accept="image/*" @change="upload($event,'logo')"></label><button v-if="d.logo" class="btn sm ghost" @click="d.logo=''">🗑</button></div>
        <label class="lbl">{{AR('صورة الواجهة (بانر)','Banner')}}</label><div class="upl"><img v-if="d.banner" :src="d.banner" style="width:90px"><label class="btn sm">🖼 {{AR('رفع صورة','Upload')}}<input type="file" accept="image/*" @change="upload($event,'banner')"></label><button v-if="d.banner" class="btn sm ghost" @click="d.banner=''">🗑</button></div>
        <label class="lbl">{{AR('خلفية المتجر (اختيارية)','Store background (optional)')}}</label><div class="upl"><img v-if="d.bg" :src="d.bg" style="width:70px"><label class="btn sm">🖼 {{AR('رفع صورة','Upload')}}<input type="file" accept="image/*" @change="upload($event,'bg')"></label><button v-if="d.bg" class="btn sm ghost" @click="d.bg=''">🗑</button></div>
        <label class="lbl">{{AR('لون المتجر','Accent color')}}</label><div class="swatches"><span v-for="c in COLORS" :key="c" class="sw" :class="{on:d.accent===c}" :style="{background:c}" @click="d.accent=c"></span></div>
        <label class="lbl">{{AR('الوضع','Theme')}}</label><div class="chips"><button v-for="m in [['auto',AR('تلقائي','Auto')],['light',AR('فاتح','Light')],['dark',AR('داكن','Dark')]]" :key="m[0]" class="chip" :class="{on:d.theme===m[0]}" @click="d.theme=m[0]">{{m[1]}}</button></div></div>
      <div class="h">🖼 {{AR('شريط الإعلانات','Ads carousel')}}</div>
      <div class="card"><div class="tiny muted">{{AR('أضف صوراً بقدر ما تريد، تتبدل تلقائياً أعلى المتجر. لكل صورة نص ورابط اختياريان.','Add as many images as you like; they rotate at the top of the store.')}}</div>
        <div v-for="(a,i) in d.ads" :key="i" class="sum"><div class="row"><img :src="a.img" style="width:96px;height:40px;object-fit:cover;border-radius:8px">
          <div class="grow"><input class="inp" v-model="a.text" :placeholder="AR('نص على الصورة (اختياري)','Caption (optional)')"><input class="inp mt" v-model="a.url" placeholder="https://t.me/..." dir="ltr"></div>
          <button class="btn sm ghost" @click="d.ads.splice(i,1)">🗑</button></div></div>
        <div class="upl mt"><label class="btn sm">＋ {{AR('إضافة صورة إعلان','Add ad image')}}<input type="file" accept="image/*" multiple @change="addAds"></label></div></div>
      <div class="h">📣 {{AR('النص الإعلاني','Promo text')}}</div>
      <div class="card"><input class="inp" v-model="d.ticker.text" :placeholder="AR('مثال: خصم 10% على كل الشدات اليوم 🔥','e.g. 10% off today 🔥')">
        <div class="chips mt"><button class="chip" :class="{on:d.ticker.mode!=='static'}" @click="d.ticker.mode='scroll'">↔ {{AR('متحرك','Scrolling')}}</button>
          <button class="chip" :class="{on:d.ticker.mode==='static'}" @click="d.ticker.mode='static'">▭ {{AR('ثابت','Static')}}</button></div></div>
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

  const AdminHold = {
    setup() {
      const d = ref(null), busy = ref(false);
      async function load(body) { busy.value = !!body; const j = await api("/admin/hold", body ? { body } : {}); busy.value = false; if (j.ok) { d.value = j; if (j.message) toast(j.message); } else toast(j.message); }
      onMounted(() => load());
      const approve = (o) => load({ action: "approve", id: o.id });
      function reject(o) { const v = ask(AR("سبب الرفض (يُسترجع المبلغ للزبون والبائع):", "Reason (full refund):"), ""); if (v === null) return; load({ action: "reject", id: o.id, reason: v }); }
      function all(p) { if (confirm(AR("إرسال كل طلبات " + (p || "كل المواقع") + " الآن؟", "Send all now?"))) load({ action: "approve_all", provider: p || "" }); }
      const toggle = (sec, on) => load({ action: "toggle", sec, on });
      return { d, busy, approve, reject, all, toggle, usd, AR, secName, copy };
    },
    template: `<div v-if="d">
      <div class="card"><div class="tx"><span><b>{{AR('موافقتي قبل إرسال طلبات التفاعل','Approve social orders first')}}</b></span><toggle :model-value="d.settings.smm" @update:model-value="toggle('smm',$event)"></toggle></div>
        <div class="tx"><span><b>{{AR('موافقتي قبل إرسال طلبات الأرقام','Approve number orders first')}}</b></span><toggle :model-value="d.settings.sms" @update:model-value="toggle('sms',$event)"></toggle></div>
        <div class="muted tiny">{{AR('الطلب يبقى عندك ولا يُرسل للموقع حتى توافق. الزبون والبائع يرونه «قيد التنفيذ».','Orders wait for you; customers see “processing”.')}}</div></div>
      <template v-if="d.orders.length"><div class="h">💳 {{AR('اشحن قبل الموافقة','Top up before approving')}} — <b dir="ltr">{{usd(d.total)}}</b></div>
        <div class="card"><div class="tx" v-for="(v,k) in d.need" :key="k"><span><b>{{k}}</b></span><span class="row"><b dir="ltr">{{usd(v)}}</b><button class="btn sm ok" :disabled="busy" @click="all(k)">✅ {{AR('أرسل الكل','Send all')}}</button></span></div></div></template>
      <div v-if="!d.orders.length" class="empty"><div>✅</div>{{AR('لا طلبات بانتظار موافقتك','Nothing waiting')}}</div>
      <div class="plist" v-else><div class="card" v-for="o in d.orders" :key="o.id">
        <div class="row sb"><b style="font-size:14px">{{o.name}}</b><span class="tag">{{secName(o.sec)}}</span></div>
        <div class="row sb tiny muted mt"><span class="copy" @click="copy(o.order_id)">#{{o.order_id.slice(-8)}}</span><span>×{{o.qty}}</span><span>{{o.created}}</span></div>
        <div class="row sb tiny mt"><span>{{AR('دفع الزبون','Paid')}} {{usd(o.price_usd)}}</span><span>{{AR('التكلفة','Cost')}} <b dir="ltr">{{usd(o.cost)}}</b> · {{o.provider||'—'}}</span></div>
        <div class="sum tiny" dir="ltr" style="text-align:start" v-if="o.target && o.target!=='-'">🎯 <span class="copy" @click="copy(o.target)">{{o.target}}</span></div>
        <div class="row mt"><button class="btn ok sm grow" :disabled="busy||o.busy" @click="approve(o)">{{o.busy?'⏳':'✅'}} {{AR('موافقة وإرسال','Approve & send')}}</button><button class="btn bad sm grow" :disabled="busy||o.busy" @click="reject(o)">↩ {{AR('رفض واسترجاع','Reject')}}</button></div>
      </div></div></div><div v-else class="skel"></div>`,
  };

  const AdminOrders = {
    setup() {
      const items = ref(null), st = ref("hold");
      async function load() { if (st.value === "hold") return; items.value = null; const j = await api("/admin/orders?status=" + st.value); items.value = j.orders || []; }
      onMounted(load); watch(st, load);
      async function deliver(o) { const v = ask(AR("بيانات التسليم (كود، حساب، ملاحظة) — تصل للزبون:", "Delivery data:")); if (!v) return; const j = await api("/admin/orders", { body: { order_id: o.order_id, action: "deliver", text: v } }); toast(j.ok ? "✅" : j.message); load(); }
      async function refund(o) { const v = ask(AR("سبب الاسترجاع:", "Reason:")); if (v === null) return; const j = await api("/admin/orders", { body: { order_id: o.order_id, action: "refund", reason: v } }); toast(j.message || "✅"); load(); }
      return { items, st, load, deliver, refund, usd, stLabel, stTag, copy, AR, secName };
    },
    components: { AdminHold },
    template: `<div><div class="chips"><button v-for="f in [['hold',AR('🕒 بانتظار موافقتك','🕒 Awaiting you')],['queued,pending',AR('تحتاج تنفيذاً','To fulfil')],['processing,waiting_sms',AR('قيد التنفيذ','Processing')],['completed',AR('مكتملة','Done')],['refunded,canceled',AR('مسترجعة','Refunded')]]" :key="f[0]" class="chip" :class="{on:st===f[0]}" @click="st=f[0]">{{f[1]}}</button></div>
      <admin-hold v-if="st==='hold'"></admin-hold>
      <div v-else-if="items===null" class="skel"></div><div v-else-if="!items.length" class="empty"><div>✅</div>{{AR('لا شيء هنا','Nothing here')}}</div>
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
      const sync = ref(null), imp = ref("");
      async function loadSync(body) { const j = await api("/admin/smm_sync", body ? { body } : {}); if (j.ok) sync.value = j; else toast(j.message); return j; }
      onMounted(() => loadSync());
      async function doImport() { const j = await loadSync({ action: "import", text: imp.value }); if (j.ok) { imp.value = ""; toast("✅ +" + (j.added || 0) + " · ↻" + (j.updated || 0)); load(); } }
      async function refresh() { await loadSync({ action: "refresh" }); toast(AR("بدأت المقارنة… تأخذ دقيقة تقريباً", "Comparing… about a minute")); setTimeout(() => loadSync(), 20000); }
      const when = (ts) => ts ? new Date(ts * 1000).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "—";
      return { d, sec, n, bal, add, check, load, AR, secName, sync, imp, doImport, refresh, when };
    },
    template: `<div v-if="d"><div class="chips"><button v-for="s in ['smm','sms','tgstars']" :key="s" class="chip" :class="{on:sec===s}" @click="sec=s;bal=null">{{secName(s)}}</button></div>
      <div class="card"><div v-if="!d[sec].length" class="muted tiny">{{AR('لا مزودين — لن يُباع هذا القسم حتى تضيف مزوداً','No providers — this section will not sell')}}</div>
        <div class="tx" v-for="(p,i) in d[sec]" :key="i"><span><b>{{p.name}}</b><div class="tiny c3" dir="ltr">{{p.api_url}} · {{p.key_hint}}</div></span>
          <span class="row"><toggle :model-value="p.on" @update:model-value="load({sec,action:'toggle',index:i})"></toggle><button class="btn sm ghost" @click="load({sec,action:'delete',index:i})">🗑</button></span></div>
        <button class="btn sm mt" @click="check" v-if="d[sec].length">🧪 {{AR('فحص رصيد المزودين','Check balances')}}</button>
        <div v-if="bal" class="sum tiny"><div v-for="b in bal" :key="b.name">{{b.name}}: <b v-if="b.balance!=null">\${{b.balance}}</b><span v-else class="minus">{{b.error}}</span></div></div></div>
      <template v-if="sec==='smm' && sync"><div class="h">⚖️ {{AR('مقارنة الأسعار التلقائية','Automatic price comparison')}}</div>
        <div class="card"><div class="tx"><span>{{AR('آخر تحديث','Last update')}}</span><b dir="ltr">{{when(sync.status.ts)}}</b></div>
          <div class="tx"><span>{{AR('عدد الخدمات المعروضة','Products')}}</span><b>{{sync.status.items}}</b></div>
          <div class="tx" v-if="sync.status.new"><span>{{AR('خدمات جديدة بآخر تحديث','New in last update')}}</span><b>{{sync.status.new}}</b></div>
          <div class="muted tiny">{{AR('كل 24 ساعة: يسحب خدمات كل المواقع، يجمع المتشابه ويعرض الأرخص، وإن فشل الطلب يحوّله للموقع التالي.','Every 24h: pulls all panels, groups similar services, shows the cheapest and fails over to the next.')}}</div>
          <button class="btn sm mt" :disabled="sync.status.running" @click="refresh">🔄 {{sync.status.running?AR('جارٍ التحديث…','Updating…'):AR('قارن الآن','Compare now')}}</button>
          <div class="sum tiny" v-if="Object.keys(sync.status.provs).length"><div v-for="(v,k) in sync.status.provs" :key="k">{{v.ok?'✅':'❌'}} <b>{{k}}</b> · {{v.count}} {{AR('خدمة','svc')}}<span v-if="v.cur!=='USD'"> · {{v.cur}}</span><span v-if="v.err" class="minus"> · {{v.err}}</span></div></div>
          <div class="sum tiny" v-if="sync.items.length"><div v-for="x in sync.items.slice(0,15)" :key="x.id">{{x.name}} — <b dir="ltr">\${{x.rate}}</b>/1k · {{x.best}}<span class="c3" v-if="x.n>1"> ({{AR('من','of')}} {{x.n}})</span></div></div></div>
        <div class="h">📥 {{AR('استيراد مواقع بالجملة','Bulk import panels')}}</div>
        <div class="card"><textarea class="inp" rows="5" v-model="imp" dir="ltr" placeholder="site.com | apikey&#10;site2.com&#10;apikey2"></textarea>
          <button class="btn p blk mt" :disabled="!imp.trim()" @click="doImport">{{AR('استيراد وربط','Import & link')}}</button></div></template>
      <div class="h">＋ {{AR('إضافة مزود','Add provider')}}</div>
      <div class="card"><input class="inp" v-model="n.name" :placeholder="AR('الاسم','Name')"><input class="inp mt" v-model="n.api_url" placeholder="https://panel.com/api/v2" dir="ltr">
        <input class="inp mt" v-model="n.api_key" placeholder="API key" dir="ltr"><button class="btn p blk mt" @click="add">{{AR('إضافة','Add')}}</button></div></div><div v-else class="skel"></div>`,
  };

  const AdminProfits = {
    setup() {
      const d = ref(null), days = ref(30), tab = ref("by_provider");
      async function load() { d.value = null; const j = await api("/admin/profits?days=" + days.value); if (j.ok) d.value = j; }
      onMounted(load); watch(days, load);
      return { d, days, tab, usd, AR, secName };
    },
    template: `<div><div class="chips"><button v-for="x in [1,7,30,90]" :key="x" class="chip" :class="{on:days===x}" @click="days=x">{{x===1?AR('اليوم','Today'):x+' '+AR('يوم','days')}}</button></div>
      <div v-if="!d" class="skel"></div><template v-else>
      <div class="kpis"><div class="kpi"><small>{{AR('صافي ربحك','Your net profit')}}</small><b class="plus">{{usd(d.total)}}</b></div>
        <div class="kpi"><small>{{AR('ربح الطلبات','Orders profit')}}</small><b>{{usd(d.profit)}}</b><div class="sub">{{d.orders}} {{AR('طلب','orders')}}</div></div>
        <div class="kpi"><small>{{AR('الاشتراكات','Subscriptions')}}</small><b>{{usd(d.subs)}}</b></div>
        <div class="kpi"><small>{{AR('تحصيل من البائعين','Intake')}}</small><b>{{usd(d.intake)}}</b><div class="sub">{{AR('تكلفة المواقع','Cost')}} {{usd(d.cost)}}</div></div></div>
      <div class="chips mt"><button v-for="x in [['by_provider',AR('حسب الموقع','By provider')],['by_store',AR('حسب المتجر','By store')],['by_section',AR('حسب القسم','By section')]]" :key="x[0]" class="chip" :class="{on:tab===x[0]}" @click="tab=x[0]">{{x[1]}}</button></div>
      <div class="card"><div v-if="!d[tab].length" class="muted tiny">{{AR('لا بيانات بعد','No data yet')}}</div>
        <div class="tx" v-for="r in d[tab]" :key="r.name"><span><b>{{tab==='by_section'?secName(r.name):r.name}}</b><div class="tiny c3">{{r.orders}} {{AR('طلب','orders')}} · {{AR('تحصيل','in')}} {{usd(r.intake)}} · {{AR('تكلفة','cost')}} {{usd(r.cost)}}</div></span><b :class="r.profit>=0?'plus':'minus'">{{usd(r.profit)}}</b></div></div>
      <div class="muted tiny mt">{{AR('الربح = ما يدفعه البائع للمنصة − تكلفة الموقع. منتجات الألعاب التي تسلّمها يدوياً تكلفتها غير معروفة للنظام فتظهر كربح كامل.','Profit = what sellers pay − provider cost.')}}</div>
      </template></div>`,
  };

  const AdminBroadcast = {
    setup() {
      const f = reactive({ bot: "", text: "", photo: "", btn_text: "", btn_url: "" }), info = ref(null), jobs = ref([]);
      async function loadJobs() { const j = await api("/admin/broadcast"); jobs.value = j.jobs || []; }
      onMounted(loadJobs);
      let tm = null;
      async function check() { info.value = null; if (!f.bot.trim()) return; const j = await api("/admin/broadcast", { body: Object.assign({ preview: 1 }, f) }); if (j.ok) info.value = j.bot; else toast(j.message); }
      async function upload(e) {
        const file = e.target.files[0]; if (!file) return;
        const fd = new FormData(); fd.append("file", file);
        const j = await api("/seller/upload", { body: fd }); if (j.ok && j.url) { f.photo = j.url; toast("✅"); } else toast(j.message || "⚠️");
      }
      async function send() {
        if (!info.value) return toast(AR("تحقق من البوت أولاً", "Check the bot first"));
        if (!confirm(AR("إرسال لـ " + info.value.users + " مستخدم في @" + info.value.username + "؟", "Send to " + info.value.users + " users?"))) return;
        const j = await api("/admin/broadcast", { body: f }); toast(j.message || (j.ok ? "✅" : "⚠️"));
        if (j.ok) { jobs.value = j.jobs; f.text = ""; f.photo = ""; clearInterval(tm); tm = setInterval(loadJobs, 3000); setTimeout(() => clearInterval(tm), 600000); }
      }
      return { f, info, jobs, check, send, upload, loadJobs, AR };
    },
    template: `<div>
      <div class="card"><label class="lbl" style="margin-top:0">{{AR('معرّف البوت','Bot username')}}</label>
        <div class="row"><input class="inp" v-model="f.bot" placeholder="@my_store_bot" dir="ltr" @change="check"><button class="btn sm" @click="check">🔎</button></div>
        <div v-if="info" class="sum tiny">🤖 <bdi dir="ltr"><b>@{{info.username}}</b></bdi> · {{info.name}} · 👥 <b>{{info.users}}</b> {{AR('مستخدم سيصلهم','recipients')}}</div>
        <label class="lbl">{{AR('الرسالة (يدعم <b> و <i> والروابط)','Message (HTML allowed)')}}</label>
        <textarea class="inp" rows="5" v-model="f.text"></textarea>
        <div class="upl mt"><label class="btn sm">🖼 {{f.photo?AR('تغيير الصورة','Change image'):AR('إرفاق صورة (اختياري)','Attach image')}}<input type="file" accept="image/*" @change="upload"></label>
          <button v-if="f.photo" class="btn sm ghost" @click="f.photo=''">✖</button></div>
        <div class="row"><input class="inp" v-model="f.btn_text" :placeholder="AR('نص الزر (اختياري)','Button text')"><input class="inp" v-model="f.btn_url" placeholder="https://" dir="ltr"></div>
        <button class="btn p blk mt" :disabled="!info" @click="send">📣 {{AR('إرسال الإذاعة','Send broadcast')}}</button></div>
      <div class="h" v-if="jobs.length">📊 {{AR('آخر الإذاعات','Recent broadcasts')}} <button class="btn sm" @click="loadJobs">↻</button></div>
      <div class="card" v-if="jobs.length"><div class="tx" v-for="j in jobs" :key="j.id"><span><b>@{{j.username}}</b> <span class="tag" :class="j.state==='done'?'ok':'warn'">{{j.state==='done'?AR('انتهت','done'):AR('جارية','running')}}</span>
        <div class="tiny c3">✅ {{j.sent}} · 🚫 {{j.blocked}} · ⚠️ {{j.failed}} / {{j.total}}</div></span></div></div></div>`,
  };

  const AdminSubs = {
    setup() {
      const d = ref(null);
      async function load(body) { const j = await api("/admin/subs", body ? { body } : {}); if (j.ok) d.value = j; else toast(j.message); return j; }
      onMounted(() => load());
      const save = async () => { const j = await load(Object.assign({}, d.value.conf)); if (j.ok) toast("✅"); };
      async function grant(s) { const v = ask(AR("كم يوماً مجانياً تمنحه؟", "Free days to grant?"), 30); if (!v) return; await load({ action: "grant", uid: s.uid, days: Number(v) }); toast("✅"); }
      return { d, save, grant, AR, usd };
    },
    template: `<div v-if="d">
      <div class="card"><div class="tx"><span><b>{{AR('الاشتراك مطلوب لإنشاء وتشغيل المتاجر','Subscription required for stores')}}</b></span><toggle v-model="d.conf.on"></toggle></div>
        <div class="row"><div class="grow"><label class="lbl">{{AR('السعر $','Price $')}}</label><input class="inp" type="number" step="0.01" v-model.number="d.conf.price"></div>
          <div class="grow"><label class="lbl">{{AR('المدة (يوم)','Days')}}</label><input class="inp" type="number" v-model.number="d.conf.days"></div>
          <div class="grow"><label class="lbl">{{AR('تجربة مجانية (يوم)','Free trial days')}}</label><input class="inp" type="number" v-model.number="d.conf.trial_days"></div></div>
        <div class="muted tiny">{{AR('يدفع البائع من رصيده في الصانع، ويتجدد تلقائياً. عند الانتهاء تتوقف متاجره عن البيع حتى يجدد (أرصدة الزبائن محفوظة).','Paid from seller balance, auto-renews; stores pause when expired.')}}</div>
        <button class="btn p blk mt" @click="save">{{AR('حفظ','Save')}}</button></div>
      <div class="h">💎 {{AR('البائعون','Sellers')}} — {{d.active}} / {{d.sellers.length}} {{AR('فعّال','active')}}</div>
      <div class="card"><div v-if="!d.sellers.length" class="muted tiny">{{AR('لا يوجد أصحاب متاجر بعد','No store owners yet')}}</div>
        <div class="tx" v-for="s in d.sellers" :key="s.uid"><span><b>{{s.username?'@'+s.username:s.name}}</b> <span class="tag" :class="s.active?'ok':'bad'">{{s.active?AR('فعّال','active'):AR('منتهٍ','expired')}}</span>
          <div class="tiny c3">{{s.until?AR('حتى','until')+' '+s.until:'—'}} · {{AR('دفعات','paid')}} {{s.paid}}{{s.trial?' · '+AR('جرّب','trial'):''}}</div></span>
          <button class="btn sm" @click="grant(s)">🎁 {{AR('منح أيام','Grant')}}</button></div></div>
    </div><div v-else class="skel"></div>`,
  };

  const AdminGuard = {
    setup() {
      const r = ref(null), b = ref(null);
      async function load() { const j = await api("/admin/risk"); if (j.ok) r.value = j; const k = await api("/admin/balances"); if (k.ok) b.value = k; }
      onMounted(load);
      async function saveAlert() { const k = await api("/admin/balances", { body: b.value.conf }); if (k.ok) toast("✅"); }
      return { r, b, load, saveAlert, AR, usd };
    },
    template: `<div>
      <div class="h">💳 {{AR('رصيد المواقع الآن','Provider balances')}} <button class="btn sm" @click="load">↻</button></div>
      <div v-if="!b" class="skel"></div><div v-else class="card">
        <div v-if="!b.results.length" class="muted tiny">{{AR('لا مواقع مربوطة','No providers')}}</div>
        <div class="tx" v-for="x in b.results" :key="x.sec+x.name"><span><b>{{x.name}}</b> <span class="tiny c3">{{x.sec==='sms'?AR('أرقام','numbers'):AR('تفاعل','social')}}</span></span>
          <b v-if="x.balance!=null" :class="x.balance<b.conf.min?'minus':'plus'" dir="ltr">\${{x.balance}}</b><span v-else class="minus tiny">{{x.error}}</span></div>
        <div class="tx mt"><span>{{AR('نبّهني عندما ينزل رصيد أي موقع تحت','Alert me when a balance drops below')}}</span><span class="row"><input class="inp" style="width:80px" type="number" v-model.number="b.conf.min"><toggle v-model="b.conf.on"></toggle></span></div>
        <button class="btn sm mt" @click="saveAlert">{{AR('حفظ','Save')}}</button></div>
      <div class="h">🕵️ {{AR('زبائن مشبوهون (استرجاع كثير)','Suspicious customers')}}</div>
      <div v-if="!r" class="skel"></div><div v-else class="card"><div v-if="!r.customers.length" class="muted tiny">{{AR('لا شيء مريب 👌','All clear 👌')}}</div>
        <div class="tx" v-for="c in r.customers" :key="c.bot_id+'_'+c.uid"><span><b>{{c.username?'@'+c.username:c.name}}</b> <span class="tiny c3">{{c.store}} · {{c.uid}}</span></span><span class="tag bad">↩ {{c.refunds}}/{{c.orders}}</span></div></div>
      <div class="h">⚠️ {{AR('متاجر عليها شكاوى','Stores with complaints')}}</div>
      <div v-if="r" class="card"><div v-if="!r.stores.length" class="muted tiny">{{AR('لا شكاوى خلال 30 يوماً','No complaints in 30 days')}}</div>
        <div class="tx" v-for="s in r.stores" :key="s.bot_id"><span><b>{{s.store}}</b> <span class="tiny c3">{{AR('المالك','owner')}} {{s.owner}}</span></span><span class="tag bad">{{s.complaints}}</span></div></div></div>`,
  };

  const Admin = {
    components: { AdminOverview, AdminOrders, AdminSellers, AdminTopups, AdminCatalog, AdminProviders, AdminProfits, AdminBroadcast, AdminSubs, AdminGuard },
    setup() {
      const sec = ref("ov");
      const NAV = computed(() => [["ov", "📊", AR("نظرة عامة", "Overview")], ["orders", "📦", AR("طلبات التنفيذ", "Fulfilment")], ["sellers", "🤖", AR("البائعون", "Sellers")],
        ["profits", "💹", AR("الأرباح", "Profits")], ["bc", "📣", AR("الإذاعة", "Broadcast")], ["subs", "💎", AR("الاشتراكات", "Subscriptions")],
        ["topups", "🧾", AR("شحن البائعين", "Top-ups")], ["catalog", "🧩", AR("الكتالوج والهوامش", "Catalog")], ["prov", "🔌", AR("المزودون", "Providers")],
        ["guard", "🛡", AR("الحماية", "Guard")]]);
      return { sec, NAV };
    },
    template: `<div class="wrap"><div class="dashnav"><div class="chips"><button v-for="n in NAV" :key="n[0]" class="chip" :class="{on:sec===n[0]}" @click="sec=n[0]">{{n[1]}} {{n[2]}}</button></div></div>
      <admin-overview v-if="sec==='ov'"></admin-overview><admin-orders v-else-if="sec==='orders'"></admin-orders><admin-sellers v-else-if="sec==='sellers'"></admin-sellers>
      <admin-topups v-else-if="sec==='topups'"></admin-topups><admin-catalog v-else-if="sec==='catalog'"></admin-catalog><admin-providers v-else-if="sec==='prov'"></admin-providers>
      <admin-profits v-else-if="sec==='profits'"></admin-profits><admin-broadcast v-else-if="sec==='bc'"></admin-broadcast><admin-subs v-else-if="sec==='subs'"></admin-subs>
      <admin-guard v-else-if="sec==='guard'"></admin-guard></div>`,
  };

  window.__S2_start(Dash, Admin);
})();
