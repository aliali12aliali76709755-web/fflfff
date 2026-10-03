/* المصحف على الويب */
(function () {
  "use strict";
  var BF = window.BF, S = BF.S, $ = BF.$, esc = BF.esc, t = BF.t;
  var KEY = "bf_quran_" + S.bot;
  var st = S.state;
  if (!st) { try { st = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { st = null; } }
  st = st || { s: 0, off: 0, hifz: [], rec: 0 };
  st.hifz = st.hifz || [];
  var tab = "all", query = "", cur = 0, ayahs = [], saveTimer;
  // من زر القائمة داخل تيليجرام لا يحمل الرابط رمز العضو: نجلب موضعه المحفوظ أولاً ولا نحفظ شيئاً قبل وصوله
  var ready = !!S.state || !BF.hasUser;

  function persist(now) {
    try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {}
    if (!BF.hasUser || !ready) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () { BF.api("save", { s: st.s || 1, off: st.off || 0, hifz: st.hifz, rec: st.rec || 0 }); }, now ? 0 : 1200);
  }
  function norm(s) { return String(s).replace(/[ً-ْٰـ]/g, "").replace(/[أإآٱ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه"); }

  function drawList() {
    var q = norm(query.trim());
    var list = S.surahs.filter(function (x) { return (tab === "all" || st.hifz.indexOf(x.n) >= 0) && (!q || norm(x.name).indexOf(q) >= 0 || String(x.n) === q); });
    $("#list").innerHTML = list.map(function (x) {
      return '<button class="item" data-s="' + x.n + '"><span class="num">' + x.n + '</span><span class="grow"><b>' + esc(x.name) + '</b><span class="muted small" style="display:block">' +
        (x.madani ? t("مدنية", "Medinan") : t("مكية", "Meccan")) + " · " + x.ayahs + " " + t("آية", "ayahs") + "</span></span>" + (st.hifz.indexOf(x.n) >= 0 ? "<span>❤️</span>" : "") + "</button>";
    }).join("") || '<div class="empty">' + (tab === "hifz" ? t("لم تحدد سوراً بعد. افتح أي سورة واضغط «حفظتها».", "Nothing yet. Open a surah and tap “Memorized”.") : t("لا توجد نتائج.", "No results.")) + "</div>";
    var r = $("#resume");
    if (st.s) {
      var x = S.surahs[st.s - 1];
      r.hidden = false;
      r.innerHTML = '<span><span class="muted small">' + t("تابع القراءة", "Continue reading") + "</span><br><b>" + t("سورة ", "Surah ") + esc(x.name) + "</b> · " + t("الآية ", "ayah ") + ((st.off || 0) + 1) + '</span><span class="btn sm primary">▶</span>';
    } else { r.hidden = true; }
  }

  function strip(first, n) {
    // نص المصدر يضع البسملة في أول آية من كل سورة (عدا الفاتحة والتوبة)؛ نعرضها في سطر مستقل
    if (n === 1 || n === 9) return first;
    var words = first.split(" ");
    return words.length > 4 && norm(words[0]) === "بسم" ? words.slice(4).join(" ") : first;
  }
  function drawText() {
    var html = ayahs.map(function (a, i) {
      return '<span class="ay' + (st.s === cur && st.off === i && i > 0 ? " hl" : "") + '" data-ay="' + (i + 1) + '">' + esc(i === 0 ? strip(a, cur) : a) + '<span class="n">' + (i + 1) + "</span></span> ";
    }).join("");
    $("#text").innerHTML = html;
    $("#loading").hidden = true;
    $("#basmala").hidden = cur === 1 || cur === 9;
  }
  function setAudio() { $("#audio").src = "https://cdn.islamic.network/quran/audio-surah/128/" + S.reciters[st.rec || 0].id + "/" + cur + ".mp3"; }
  function hzBtn() { var on = st.hifz.indexOf(cur) >= 0; $("#hz").textContent = on ? t("❤️ محفوظة", "❤️ Memorized") : t("🤍 حفظتها", "🤍 Mark memorized"); }

  function open(n, off) {
    cur = n; ayahs = [];
    var x = S.surahs[n - 1];
    $("#home").hidden = true; $("#reader").hidden = false;
    $("#sTitle").textContent = t("سورة ", "Surah ") + x.name;
    $("#text").innerHTML = ""; $("#loading").hidden = false; $("#loading").textContent = t("جارٍ تحميل السورة…", "Loading the surah…");
    $("#prev").textContent = n > 1 ? "→ " + S.surahs[n - 2].name : ""; $("#prev").hidden = n <= 1;
    $("#next").textContent = n < 114 ? S.surahs[n].name + " ←" : ""; $("#next").hidden = n >= 114;
    hzBtn(); setAudio();
    BF.back("reader", close);
    window.scrollTo(0, 0);
    st.s = n; st.off = off || 0; persist();
    try { history.replaceState(null, "", "#" + n); } catch (e) {}
    BF.api("surah", { n: n }).then(function (r) {
      if (cur !== n) return;
      if (!r.ok) { $("#loading").textContent = r.message || t("تعذّر تحميل السورة. تحقق من الاتصال وحاول مرة أخرى.", "Couldn't load the surah. Check your connection and retry."); return; }
      ayahs = r.ayahs; drawText();
      if (st.off) { var el = document.querySelector('.ay[data-ay="' + (st.off + 1) + '"]'); if (el) el.scrollIntoView({ block: "center" }); }
    });
  }
  function close() { BF.back("reader", null); $("#reader").hidden = true; $("#home").hidden = false; $("#audio").pause(); cur = 0; drawList(); try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {} }

  document.addEventListener("click", function (ev) {
    var s = ev.target.closest("[data-s]"), tb = ev.target.closest("[data-tab]"), ay = ev.target.closest("[data-ay]"), act = ev.target.closest("[data-act]");
    if (s) { open(+s.getAttribute("data-s"), 0); }
    else if (tb) { tab = tb.getAttribute("data-tab"); BF.$$(".tab").forEach(function (b) { b.classList.toggle("on", b === tb); }); drawList(); }
    else if (ay && !act) {
      var n = +ay.getAttribute("data-ay");
      $("#ayahBody").innerHTML = '<h2>' + t("الآية ", "Ayah ") + n + ' · ' + esc(S.surahs[cur - 1].name) + '</h2><p class="mushaf" style="font-size:1.3rem;line-height:2.2">' + esc(n === 1 ? strip(ayahs[0], cur) : ayahs[n - 1]) + "</p>" +
        '<div class="row"><button class="btn primary grow" data-act="mark" data-n="' + n + '">' + t("🔖 ضع علامة هنا", "🔖 Bookmark here") + '</button><button class="btn grow" data-act="tafsir" data-n="' + n + '">' + t("📚 التفسير", "📚 Tafsir") + '</button></div><div id="tf" class="prose"></div>';
      BF.sheet("ayahSheet");
    } else if (act) {
      var k = +act.getAttribute("data-n");
      if (act.getAttribute("data-act") === "mark") {
        st.s = cur; st.off = k - 1; persist(true); drawText(); BF.sheet("ayahSheet", false);
        BF.toast(BF.hasUser ? t("حُفظ الموضع، وتتابع منه في البوت أيضاً.", "Saved. You can continue from here in the bot too.") : t("حُفظ الموضع على هذا الجهاز.", "Saved on this device."));
      } else {
        $("#tf").innerHTML = '<p class="muted">' + t("جارٍ التحميل…", "Loading…") + "</p>";
        BF.api("tafsir", { s: cur, n: k }).then(function (r) { $("#tf").innerHTML = r.ok ? "<h3>" + t("التفسير الميسّر", "Al-Muyassar tafsir") + '</h3><p class="mt">' + esc(r.text) + "</p>" : '<p class="muted">' + esc(r.message || t("تعذّر جلب التفسير.", "Couldn't load the tafsir.")) + "</p>"; });
      }
    }
  });
  $("#q").addEventListener("input", function (ev) { query = ev.target.value; drawList(); });
  $("#resume").addEventListener("click", function () { open(st.s, st.off || 0); });
  $("#back").addEventListener("click", close);
  $("#prev").addEventListener("click", function () { if (cur > 1) open(cur - 1, 0); });
  $("#next").addEventListener("click", function () { if (cur < 114) open(cur + 1, 0); });
  $("#hz").addEventListener("click", function () {
    var i = st.hifz.indexOf(cur);
    if (i >= 0) st.hifz.splice(i, 1); else st.hifz.push(cur);
    hzBtn(); persist(true);
  });
  var sel = $("#reciter");
  sel.innerHTML = S.reciters.map(function (r, i) { return '<option value="' + i + '"' + (i === (st.rec || 0) ? " selected" : "") + ">" + esc(r.name) + "</option>"; }).join("");
  sel.addEventListener("change", function () { st.rec = +sel.value; setAudio(); persist(); });

  function boot() {
    st.s = parseInt(st.s, 10) || 0; st.off = parseInt(st.off, 10) || 0; st.rec = parseInt(st.rec, 10) || 0;
    st.hifz = (st.hifz || []).map(function (x) { return parseInt(x, 10) || 0; }).filter(function (x) { return x >= 1 && x <= 114; });
    sel.value = String(st.rec);
    drawList();
    var h = parseInt(location.hash.slice(1), 10);
    if (h >= 1 && h <= 114) open(h, st.s === h ? st.off : 0);
  }
  if (ready) { boot(); }
  else {
    drawList();
    BF.api("state").then(function (r) { if (r.ok && r.state) { st = r.state; } ready = true; boot(); });
  }
})();
