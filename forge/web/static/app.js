/* BotForge web — أدوات مشتركة بين صفحات مواقع البوتات */
(function () {
  "use strict";
  var tg = (window.Telegram && window.Telegram.WebApp) || null;
  var inTg = !!(tg && tg.initData);
  var S = window.SITE || {};

  // هوية العضو: رمز موقّع يضعه البوت في الرابط، أو بيانات تيليجرام حين تُفتح الصفحة داخله
  var qs = new URLSearchParams(location.search);
  var store = { get: function (k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
                set: function (k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} } };
  var keyName = "bf_k_" + (S.bot || "");
  var k = qs.get("k");
  if (k) {
    store.set(keyName, k);
    // الرمز شخصي: نزيله من شريط العنوان كي لا يُنسخ مع الرابط عند مشاركته
    try { qs.delete("k"); history.replaceState(null, "", location.pathname + (qs.toString() ? "?" + qs.toString() : "") + location.hash); } catch (e) {}
  } else { k = store.get(keyName) || ""; }

  // داخل تيليجرام: ألوان المستخدم نفسها، شاشة كاملة، وزر الرجوع الأصلي
  function theme() {
    try {
      var tp = tg.themeParams || {}, st = document.documentElement.style;
      document.documentElement.setAttribute("data-theme", tg.colorScheme === "dark" ? "dark" : "light");
      var map = { "--bg": tp.secondary_bg_color || tp.bg_color, "--card": tp.section_bg_color || tp.bg_color, "--text": tp.text_color,
                  "--muted": tp.subtitle_text_color || tp.hint_color, "--line": tp.section_separator_color };
      Object.keys(map).forEach(function (v) { if (map[v]) st.setProperty(v, map[v]); });
      if (tp.bg_color && tp.secondary_bg_color && tp.bg_color === tp.secondary_bg_color && !tp.section_bg_color) st.removeProperty("--card");
      if (tg.setHeaderColor && (tp.secondary_bg_color || tp.bg_color)) tg.setHeaderColor(tp.secondary_bg_color || tp.bg_color);
      if (tg.setBackgroundColor && (tp.secondary_bg_color || tp.bg_color)) tg.setBackgroundColor(tp.secondary_bg_color || tp.bg_color);
    } catch (e) {}
  }
  if (inTg) {
    try { tg.ready(); tg.expand(); } catch (e) {}
    document.documentElement.classList.add("in-tg");
    theme();
    try { tg.onEvent("themeChanged", theme); } catch (e) {}
  }

  // زر الرجوع: كل شاشة فرعية أو ورقة تسجّل دالة إغلاقها، وزر تيليجرام ينفّذ آخرها
  var backs = [];
  function syncBack() {
    if (!inTg || !tg.BackButton) return;
    try { if (backs.length) tg.BackButton.show(); else tg.BackButton.hide(); } catch (e) {}
  }
  function back(key, fn) {
    backs = backs.filter(function (b) { return b.key !== key; });
    if (fn) backs.push({ key: key, fn: fn });
    syncBack();
  }
  if (inTg && tg.BackButton) { try { tg.BackButton.onClick(function () { var b = backs[backs.length - 1]; if (b) b.fn(); }); } catch (e) {} }

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function t(ar, en) { return S.lang === "en" ? en : ar; }

  var toastTimer;
  function toast(msg) {
    var el = $("#toast");
    if (!el) { el = document.createElement("div"); el.id = "toast"; el.className = "toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.textContent = msg; el.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { el.classList.remove("show"); }, 2200);
    if (inTg && tg.HapticFeedback) { try { tg.HapticFeedback.impactOccurred("light"); } catch (e) {} }
  }

  function sheet(id, open) {
    var el = document.getElementById(id);
    if (!el) return;
    var on = open !== false;
    el.classList.toggle("open", on);
    document.body.style.overflow = document.querySelector(".scrim.open") ? "hidden" : "";
    back("sheet:" + id, on ? function () { sheet(id, false); } : null);
  }
  function closeApp() { if (inTg) { try { tg.close(); return true; } catch (e) {} } return false; }
  document.addEventListener("click", function (ev) {
    if (!ev.target.closest) return;
    var sc = ev.target.classList && ev.target.classList.contains("scrim") ? ev.target : null;
    if (sc) { sheet(sc.id, false); }
    var cl = ev.target.closest("[data-close]");
    if (cl) { var p = cl.closest(".scrim"); if (p) sheet(p.id, false); }
    if (ev.target.closest("[data-tgclose]")) { closeApp(); }
    var a = ev.target.closest('a[href^="https://t.me/"]');      // روابط تيليجرام تُفتح داخل التطبيق نفسه
    if (a && inTg) { ev.preventDefault(); try { tg.openTelegramLink(a.getAttribute("href")); } catch (e) { location.href = a.getAttribute("href"); } }
  });

  function api(path, body) {
    var headers = { "Content-Type": "application/json" };
    if (k) headers["X-User-Key"] = k;
    if (inTg) headers["X-Init-Data"] = tg.initData;
    return fetch((S.root || "") + "/api/" + path, {
      method: body === undefined ? "GET" : "POST", headers: headers,
      body: body === undefined ? undefined : JSON.stringify(body)
    }).then(function (r) { return r.json().catch(function () { return { ok: false, error: "bad" }; }); })
      .catch(function () { return { ok: false, error: "net" }; });
  }

  function openLink(url) {
    if (inTg && /^https:\/\/t\.me\//.test(url)) { try { tg.openTelegramLink(url); return; } catch (e) {} }
    location.href = url;
  }

  var top = $(".top");
  if (top) { window.addEventListener("scroll", function () { top.classList.toggle("stuck", window.scrollY > 4); }, { passive: true }); }

  function haptic(kind) { if (inTg && tg.HapticFeedback) { try { tg.HapticFeedback.notificationOccurred(kind || "success"); } catch (e) {} } }
  // زر «تم» بعد إتمام طلب: داخل تيليجرام يغلق الشاشة ليعود العضو إلى المحادثة حيث وصله التأكيد
  function doneBtn() {
    return inTg ? '<button class="btn primary block" data-tgclose>' + t("العودة إلى المحادثة", "Back to the chat") + "</button>"
                : '<button class="btn primary block" data-close>' + t("تم", "Done") + "</button>";
  }

  window.BF = { $: $, $$: $$, esc: esc, t: t, toast: toast, sheet: sheet, api: api, openLink: openLink, tg: tg, inTg: inTg, hasUser: !!k || inTg, S: S,
                back: back, closeApp: closeApp, haptic: haptic, doneBtn: doneBtn };
})();
