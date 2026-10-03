/* موقع المتجر والمنيو */
(function () {
  "use strict";
  var BF = window.BF, S = BF.S, $ = BF.$, esc = BF.esc, t = BF.t;
  var items = S.items || [], byId = {};
  items.forEach(function (x) { x.id = parseInt(x.id, 10) || 0; byId[x.id] = x; });
  var KEY = "bf_cart_" + S.bot, cat = "", query = "";
  var cart = {};
  try { cart = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { cart = {}; }
  Object.keys(cart).forEach(function (k) { if (!byId[k] || !(cart[k] > 0)) delete cart[k]; });

  function save() { try { localStorage.setItem(KEY, JSON.stringify(cart)); } catch (e) {} }
  function money(v) {
    var s = (Math.round(v * 100) / 100).toLocaleString("en-US", { maximumFractionDigits: 2 });
    return S.unit ? (S.unit.length <= 1 ? s + S.unit : s + " " + S.unit) : s;
  }
  function count() { return Object.keys(cart).reduce(function (n, k) { return n + cart[k]; }, 0); }
  function total() { return Object.keys(cart).reduce(function (n, k) { return n + cart[k] * byId[k].num; }, 0); }
  function pic(x, cls) {
    return '<div class="' + cls + '">' + (x.img ? '<img src="' + esc(x.img) + '" alt="" loading="lazy" onerror="this.remove()">' : "") + (x.img ? "" : esc(S.emoji)) + "</div>";
  }
  function stepper(id) {
    var q = cart[id] || 0;
    if (!q) return '<button class="btn sm soft" data-add="' + id + '">' + t("أضف", "Add") + "</button>";
    return '<span class="qty"><button data-sub="' + id + '" aria-label="-">−</button><span>' + q + '</span><button data-add="' + id + '" aria-label="+">+</button></span>';
  }

  function drawChips() {
    var el = $("#chips");
    if (!S.cats || S.cats.length < 2) { el.hidden = true; return; }
    el.innerHTML = ['<button class="chip' + (cat === "" ? " on" : "") + '" data-cat="">' + t("الكل", "All") + "</button>"].concat(
      S.cats.map(function (c) { return '<button class="chip' + (cat === c ? " on" : "") + '" data-cat="' + esc(c) + '">' + esc(c) + "</button>"; })).join("");
  }
  function drawGrid() {
    var q = query.trim().toLowerCase();
    var list = items.filter(function (x) {
      return (!cat || x.cat === cat) && (!q || (x.name + " " + x.desc + " " + x.cat).toLowerCase().indexOf(q) >= 0);
    });
    $("#grid").innerHTML = list.map(function (x) {
      return '<article class="prod" data-open="' + x.id + '">' + pic(x, "ph") + '<div class="bd"><div class="nm">' + esc(x.name) + "</div>" +
        (x.desc ? '<div class="ds">' + esc(x.desc) + "</div>" : "") + '<div class="ft"><span class="price">' + esc(x.price) + "</span>" + stepper(x.id) + "</div></div></article>";
    }).join("");
    $("#none").hidden = list.length > 0;
  }
  function drawBar() {
    var n = count();
    $("#bar").hidden = n === 0;
    $("#cartDot").hidden = n === 0;
    $("#cartDot").textContent = n;
    $("#barTxt").textContent = t("عرض السلة", "View cart") + " · " + n + " · " + money(total());
  }
  function drawCart() {
    var ids = Object.keys(cart);
    $("#cartLines").innerHTML = ids.length ? ids.map(function (k) {
      var x = byId[k];
      return '<div class="line-item">' + pic(x, "th") + '<div class="grow"><div style="font-weight:600">' + esc(x.name) + '</div><div class="price small">' + esc(x.price) + "</div></div>" + stepper(x.id) + "</div>";
    }).join("") : '<div class="empty"><div class="big">🛒</div>' + t("سلتك فارغة.", "Your cart is empty.") + "</div>";
    $("#cartTotal").textContent = money(total());
    $("#orderForm").hidden = ids.length === 0;
    $("#hint").textContent = BF.hasUser ? t("يصل الطلب إلى البائع فوراً، وتتابع حالته في تيليجرام.", "The seller gets it right away; track it in Telegram.")
                                        : t("بعد الإرسال تؤكد الطلب بضغطة في تيليجرام ليتواصل معك البائع.", "After sending, confirm with one tap in Telegram so the seller can reach you.");
  }
  function drawProd(id) {
    var x = byId[id];
    if (!x) return;
    $("#prodBody").innerHTML = (x.img ? '<div class="prod" style="border:0"><div class="ph" style="border-radius:16px">' + '<img src="' + esc(x.img) + '" alt=""></div></div>' : "") +
      '<div class="stack mt"><div class="row between"><h2>' + esc(x.name) + '</h2><span class="price" style="font-size:1.2rem">' + esc(x.price) + "</span></div>" +
      (x.cat ? '<div><span class="badge">' + esc(x.cat) + "</span></div>" : "") + (x.desc ? '<p class="muted prose">' + esc(x.desc) + "</p>" : "") +
      '<div class="row between mt">' + stepper(x.id) + '<button class="btn" data-close>' + t("متابعة التصفّح", "Keep browsing") + "</button></div></div>";
    $("#prodBody").dataset.id = id;
  }
  function refresh() {
    save(); drawGrid(); drawBar();
    if ($("#cartSheet").classList.contains("open")) drawCart();
    if ($("#prodSheet").classList.contains("open")) drawProd($("#prodBody").dataset.id);
  }

  document.addEventListener("click", function (ev) {
    var a = ev.target.closest("[data-add]"), s = ev.target.closest("[data-sub]"), c = ev.target.closest("[data-cat]"), o = ev.target.closest("[data-open]");
    if (a || s) {
      ev.stopPropagation();
      var id = (a || s).getAttribute(a ? "data-add" : "data-sub");
      var q = Math.max(0, Math.min(99, (cart[id] || 0) + (a ? 1 : -1)));
      if (q) cart[id] = q; else delete cart[id];
      if (a && q === 1) BF.toast(t("أضيف إلى السلة", "Added to cart"));
      refresh();
    } else if (c) {
      cat = c.getAttribute("data-cat"); drawChips(); drawGrid();
    } else if (o) {
      drawProd(o.getAttribute("data-open")); BF.sheet("prodSheet");
    }
  });
  $("#q").addEventListener("input", function (ev) { query = ev.target.value; drawGrid(); });
  function openCart() { BF.sheet("prodSheet", false); drawCart(); BF.sheet("cartSheet"); }
  $("#cartBtn").addEventListener("click", openCart);
  $("#barBtn").addEventListener("click", openCart);

  var form = $("#orderForm");
  try { var saved = JSON.parse(localStorage.getItem("bf_me") || "{}"); ["name", "phone", "where"].forEach(function (f) { if (saved[f]) form.elements[f].value = saved[f]; }); } catch (e) {}
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var d = { cart: cart, name: form.elements.name.value.trim(), phone: form.elements.phone.value.trim(), where: form.elements.where.value.trim(), note: form.elements.note.value.trim() };
    if (d.name.length < 2 || d.phone.length < 5 || !d.where) { BF.toast(t("أكمل الاسم ورقم الهاتف والعنوان.", "Please fill in name, phone and address.")); return; }
    var btn = $("#sendBtn"); btn.disabled = true; btn.textContent = t("جارٍ الإرسال…", "Sending…");
    BF.api("order", d).then(function (r) {
      btn.disabled = false; btn.textContent = t("إرسال الطلب", "Place order");
      if (!r.ok) {
        BF.toast(r.message || t("تعذّر إرسال الطلب. حاول مرة أخرى.", "Couldn't place the order. Try again."));
        if (r.error === "changed") { setTimeout(function () { location.reload(); }, 1800); }
        return;
      }
      try { localStorage.setItem("bf_me", JSON.stringify({ name: d.name, phone: d.phone, where: d.where })); } catch (e) {}
      cart = {}; refresh(); BF.sheet("cartSheet", false);
      var body = $("#doneBody");
      if (r.placed) {
        body.innerHTML = '<div style="font-size:3rem">✅</div><h2>' + t("وصل طلبك", "Order received") + " #" + r.id + '</h2><p class="muted">' +
          t("يراجعه البائع الآن، وتصلك الإشعارات في محادثة البوت.", "The seller is reviewing it. Updates arrive in the bot chat.") + "</p>" + BF.doneBtn();
        BF.haptic("success");
      } else {
        body.innerHTML = '<div style="font-size:3rem">📨</div><h2>' + t("خطوة أخيرة", "One last step") + '</h2><p class="muted">' +
          t("أكّد طلبك في تيليجرام ليصل إلى البائع ويتواصل معك.", "Confirm your order in Telegram so it reaches the seller.") +
          '</p><a class="btn primary block" id="confirmLink" href="' + esc(r.link) + '">' + t("تأكيد الطلب في تيليجرام", "Confirm in Telegram") + "</a>";
      }
      BF.sheet("doneSheet");
    });
  });

  drawChips(); drawGrid(); drawBar();
  if (!items.length) { $("#none").hidden = false; $("#none").innerHTML = '<div class="big">🕊</div>' + t("لا توجد أصناف معروضة الآن.", "Nothing is listed right now."); }
})();
