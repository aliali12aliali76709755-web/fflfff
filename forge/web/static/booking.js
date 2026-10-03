/* صفحة الحجز */
(function () {
  "use strict";
  var BF = window.BF, S = BF.S, $ = BF.$, esc = BF.esc, t = BF.t;
  var pick = { svc: null, date: "", time: "" };
  S.svcs = (S.svcs || []).map(function (x) { x.id = parseInt(x.id, 10) || 0; return x; });

  function show(id, on) { $(id).hidden = !on; }
  function drawSvcs() {
    $("#svcs").innerHTML = S.svcs.length ? S.svcs.map(function (x) {
      return '<button class="link' + (pick.svc === x.id ? " on" : "") + '" data-svc="' + x.id + '"' + (pick.svc === x.id ? ' style="border-color:var(--accent);background:var(--accent-soft)"' : "") + '><span>' + esc(x.name) +
        '<span class="muted small" style="display:block;font-weight:400">' + esc(x.mins) + " " + t("دقيقة", "min") + '</span></span><span class="price">' + esc(x.price) + "</span></button>";
    }).join("") : '<p class="muted">' + t("لا توجد خدمات متاحة للحجز الآن.", "No services available right now.") + "</p>";
  }
  function drawDays() {
    $("#days").innerHTML = S.days.map(function (d) {
      return '<button class="day' + (pick.date === d.date ? " on" : "") + '" data-date="' + d.date + '"><span>' + esc(d.dow) + "</span><b>" + d.day + "</b><span>" + d.day + "/" + d.mon + "</span></button>";
    }).join("");
  }
  function drawSlots(list) {
    $("#slots").innerHTML = list.map(function (h) { return '<button class="slot' + (pick.time === h ? " on" : "") + '" data-time="' + h + '">' + h + "</button>"; }).join("");
    show("#noslots", list.length === 0);
  }
  function summary() {
    var svc = S.svcs.filter(function (x) { return x.id === pick.svc; })[0];
    $("#summary").innerHTML = "📌 <b>" + esc(svc ? svc.name : "") + '</b> · <span class="price">' + esc(svc ? svc.price : "") + "</span><br>📅 " + esc(pick.date) + " ⏰ " + esc(pick.time);
    $("#hint").textContent = BF.hasUser ? t("يصل الحجز فوراً، ويصلك التأكيد في تيليجرام.", "Sent right away; the confirmation arrives in Telegram.")
                                        : t("بعد الإرسال تؤكد الحجز بضغطة في تيليجرام.", "After sending, confirm with one tap in Telegram.");
  }
  function loadSlots() {
    $("#slots").innerHTML = '<p class="muted small" style="grid-column:1/-1">' + t("جارٍ التحميل…", "Loading…") + "</p>";
    BF.api("slots", { date: pick.date }).then(function (r) { drawSlots(r.ok ? r.slots : []); });
  }

  document.addEventListener("click", function (ev) {
    var s = ev.target.closest("[data-svc]"), d = ev.target.closest("[data-date]"), h = ev.target.closest("[data-time]");
    if (s) { pick.svc = +s.getAttribute("data-svc"); drawSvcs(); show("#s2", true); if (pick.time) summary(); }
    else if (d) { pick.date = d.getAttribute("data-date"); pick.time = ""; drawDays(); show("#s3", true); show("#s4", false); loadSlots(); }
    else if (h) { pick.time = h.getAttribute("data-time"); loadSlotsKeep(); show("#s4", true); summary(); $("#s4").scrollIntoView({ behavior: "smooth", block: "start" }); }
  });
  function loadSlotsKeep() { Array.prototype.forEach.call(document.querySelectorAll(".slot"), function (b) { b.classList.toggle("on", b.getAttribute("data-time") === pick.time); }); }

  var form = $("#bookForm");
  try { var saved = JSON.parse(localStorage.getItem("bf_me") || "{}"); ["name", "phone"].forEach(function (f) { if (saved[f]) form.elements[f].value = saved[f]; }); } catch (e) {}
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var d = { svc: pick.svc, date: pick.date, time: pick.time, name: form.elements.name.value.trim(), phone: form.elements.phone.value.trim(), note: form.elements.note.value.trim() };
    if (d.name.length < 2 || d.phone.length < 5) { BF.toast(t("أكمل الاسم ورقم الهاتف.", "Please fill in your name and phone.")); return; }
    var btn = $("#bookBtn"); btn.disabled = true;
    BF.api("book", d).then(function (r) {
      btn.disabled = false;
      if (!r.ok) { BF.toast(r.message || t("تعذّر الحجز. حاول مرة أخرى.", "Couldn't book. Try again.")); if (r.error === "taken") { pick.time = ""; show("#s4", false); loadSlots(); } return; }
      try { var me = JSON.parse(localStorage.getItem("bf_me") || "{}"); me.name = d.name; me.phone = d.phone; localStorage.setItem("bf_me", JSON.stringify(me)); } catch (e) {}
      var body = $("#doneBody");
      if (r.placed) {
        body.innerHTML = '<div style="font-size:3rem">✅</div><h2>' + t("وصل طلب الحجز", "Booking request received") + " #" + r.id + '</h2><p class="muted">📅 ' + esc(d.date) + " ⏰ " + esc(d.time) + "<br>" +
          t("سيصلك التأكيد في محادثة البوت.", "The confirmation will arrive in the bot chat.") + "</p>" + BF.doneBtn();
        BF.haptic("success");
      } else {
        body.innerHTML = '<div style="font-size:3rem">📨</div><h2>' + t("خطوة أخيرة", "One last step") + '</h2><p class="muted">' + t("أكّد حجزك في تيليجرام ليصل إلى صاحب الموعد.", "Confirm your booking in Telegram so it reaches the provider.") +
          '</p><a class="btn primary block" id="confirmLink" href="' + esc(r.link) + '">' + t("تأكيد الحجز في تيليجرام", "Confirm in Telegram") + "</a>";
      }
      pick.time = ""; show("#s4", false); loadSlots();
      BF.sheet("doneSheet");
    });
  });
  drawSvcs(); drawDays();
})();
