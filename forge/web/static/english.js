/* دورة الإنجليزية على الويب */
(function () {
  "use strict";
  var BF = window.BF, S = BF.S, $ = BF.$, esc = BF.esc, t = BF.t;
  var KEY = "bf_en_" + S.bot, DAY = S.today, GAPS = S.gaps;
  var u = S.state;
  if (!u) { try { u = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { u = null; } }
  u = u || { lvl: 0, xp: 0, done: [], box: {} };
  var tab = "lessons", timer, sess = null;
  // حين تُفتح الصفحة من زر القائمة داخل تيليجرام لا يحمل الرابط رمز العضو، فنجلب تقدّمه أولاً ولا نحفظ شيئاً قبل وصوله
  var ready = !!S.state || !BF.hasUser;

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(u)); } catch (e) {}
    stats();
    if (!BF.hasUser || !ready) return;
    clearTimeout(timer);
    timer = setTimeout(function () { BF.api("sync", { u: u }); }, 600);
  }
  function due() { return Object.keys(u.box).filter(function (k) { return u.box[k][1] <= DAY; }); }
  function stats() {
    $("#kLvl").textContent = u.lvl ? S.levels[u.lvl] : t("غير محدد", "Not set");
    $("#kXp").textContent = u.xp;
    $("#kDue").textContent = due().length;
  }
  function shuffle(a) { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var x = a[i]; a[i] = a[j]; a[j] = x; } return a; }
  function view(html) { $("#view").innerHTML = html; }
  function opts(list, attr, rtl) { return '<div class="stack">' + list.map(function (o, i) { return '<button class="opt' + (rtl ? " rtl" : "") + '" ' + attr + '="' + i + '">' + esc(o) + "</button>"; }).join("") + "</div>"; }

  // ── الدروس ──
  function lessons() {
    var maxLv = Math.max(1, u.lvl);
    view('<section class="card pad0"><div class="list">' + S.lessons.map(function (l, i) {
      var mark = u.done.indexOf(i) >= 0 ? "✅" : (l.lv <= maxLv ? "📖" : "🔓");
      return '<button class="item" data-lesson="' + i + '"><span class="num">' + (i + 1) + '</span><span class="grow"><b>' + esc(l.title) + '</b><span class="muted small" style="display:block">' + esc(S.levels[l.lv]) + "</span></span><span>" + mark + "</span></button>";
    }).join("") + "</div></section>" + (u.lvl ? "" : '<div class="notice mt">' + t("لا تعرف من أين تبدأ؟ ", "Not sure where to start? ") + '<a href="#" data-go="placement">' + t("اختبر مستواك في دقيقتين", "Take the 2-minute placement test") + "</a></div>"));
  }
  function lesson(i) {
    var l = S.lessons[i];
    view('<section class="card stack"><div class="row between"><h2>' + esc(l.title) + '</h2><span class="badge">' + esc(S.levels[l.lv]) + '</span></div><div class="prose rich">' + l.body + "</div><h3>" + t("أمثلة", "Examples") +
      '</h3><div class="stack">' + l.ex.map(function (x) { return '<div class="notice" dir="auto">' + esc(x) + "</div>"; }).join("") + '</div><button class="btn primary block" data-quiz="' + i + '">' + t("اختبر نفسك", "Quiz me") +
      '</button><button class="btn block" data-go="lessons">' + t("رجوع إلى الدروس", "Back to lessons") + "</button></section>");
    window.scrollTo(0, 0);
  }
  function quiz(i, n, score) {
    var l = S.lessons[i];
    if (n >= l.quiz.length) {
      var full = score === l.quiz.length;
      if (full && u.done.indexOf(i) < 0) { u.done.push(i); u.xp += 10; save(); }
      view('<section class="card flash"><div style="font-size:3rem">' + (full ? "🎉" : "💪") + "</div><h2>" + score + " / " + l.quiz.length + '</h2><p class="muted">' +
        (full ? t("أتممت الدرس! +10 نقاط", "Lesson completed! +10 XP") : t("راجع الشرح وحاول مرة أخرى.", "Review the lesson and try again.")) + '</p></section><div class="stack mt">' +
        (i + 1 < S.lessons.length ? '<button class="btn primary block" data-lesson="' + (i + 1) + '">' + t("الدرس التالي", "Next lesson") + "</button>" : "") +
        '<button class="btn block" data-lesson="' + i + '">' + t("إعادة الدرس", "Repeat the lesson") + "</button></div>");
      return;
    }
    sess = { kind: "quiz", i: i, n: n, score: score, a: l.quiz[n].a };
    view('<p class="muted small">' + (n + 1) + " / " + l.quiz.length + '</p><section class="card flash"><div class="w" style="font-size:1.35rem">' + esc(l.quiz[n].q) + "</div></section><div class=\"mt\">" + opts(l.quiz[n].o, "data-ans") + "</div>");
  }

  // ── الكلمات ──
  function words() {
    var n = Object.keys(u.box).length;
    view('<section class="card stack"><div class="row between"><h2>' + t("مفرداتك", "Your vocabulary") + '</h2><span class="badge">' + n + " / " + S.words.length + '</span></div><div class="progress"><i style="width:' + (100 * n / S.words.length) + '%"></i></div>' +
      '<p class="muted">' + t("تتعلم الكلمات على دفعات من خمس، ثم تثبّتها بالمراجعة المتباعدة.", "Learn words in batches of five, then lock them in with spaced review.") + '</p><button class="btn primary block" data-go="new">' + t("تعلّم 5 كلمات جديدة", "Learn 5 new words") + "</button></section>" +
      (n ? '<section class="card pad0 mt"><div class="list">' + Object.keys(u.box).slice(-12).reverse().map(function (k) { var w = S.words[k]; return '<div class="item"><span class="grow" dir="ltr" style="text-align:start"><b>' + esc(w.w) + '</b></span><span class="muted">' + esc(w.m) + "</span></div>"; }).join("") + "</div></section>" : ""));
  }
  function fresh() {
    var lvl = Math.max(1, u.lvl);
    var pool = S.words.map(function (w, i) { return i; }).filter(function (i) { return !u.box[i]; });
    var pick = pool.filter(function (i) { return S.words[i].lv <= lvl; }).slice(0, 5);
    if (!pick.length) pick = pool.slice(0, 5);
    if (!pick.length) { view('<section class="card flash"><div style="font-size:3rem">🎉</div><h2>' + t("تعلمت كل الكلمات!", "You've learned every word!") + '</h2><p class="muted">' + t("واصل المراجعة لتثبيتها.", "Keep reviewing to lock them in.") + "</p></section>"); return; }
    pick.forEach(function (i) { u.box[i] = [0, DAY]; });
    u.xp += pick.length; save();
    view('<section class="card pad0"><div class="list">' + pick.map(function (i) { var w = S.words[i]; return '<div class="item"><span class="grow" dir="ltr" style="text-align:start;font-size:1.15rem"><b>' + esc(w.w) + '</b></span><span>' + esc(w.m) + "</span></div>"; }).join("") +
      '</div></section><div class="stack mt"><button class="btn primary block" data-go="review">' + t("راجعها الآن", "Review them now") + '</button><button class="btn block" data-go="new">' + t("5 كلمات أخرى", "5 more words") + "</button></div>");
  }

  // ── المراجعة ──
  function review(skip) {
    var d = due().filter(function (k) { return k !== skip; });
    if (!d.length) d = due();      // الكلمة الوحيدة المتبقية تُعاد حتى تُجاب صحيحة
    if (!d.length) {
      view('<section class="card flash"><div style="font-size:3rem">✅</div><h2>' + t("لا توجد كلمات للمراجعة الآن", "Nothing to review right now") + '</h2><p class="muted">' + t("تعلّم كلمات جديدة أو عد غداً.", "Learn new words or come back tomorrow.") +
        '</p></section><button class="btn primary block mt" data-go="new">' + t("تعلّم 5 كلمات جديدة", "Learn 5 new words") + "</button>");
      return;
    }
    var k = d[Math.floor(Math.random() * d.length)], w = S.words[k];
    var wrong = shuffle(S.words.filter(function (x, i) { return String(i) !== String(k) && x.m !== w.m; }).map(function (x) { return x.m; })).slice(0, 3);
    var list = shuffle(wrong.concat([w.m]));
    sess = { kind: "review", k: k, a: list.indexOf(w.m) };
    view('<p class="muted small">' + t("المتبقي: ", "Left: ") + d.length + '</p><section class="card flash"><span class="muted small">' + t("ما معنى", "What does this mean?") + '</span><div class="w">' + esc(w.w) + '</div></section><div class="mt">' + opts(list, "data-ans", true) + "</div>");
  }

  // ── تقدّمي واختبار المستوى ──
  function me() {
    var learned = Object.keys(u.box).filter(function (k) { return u.box[k][0] >= 3; }).length;
    view('<section class="kpis"><div class="kpi"><div class="v">' + u.done.length + " / " + S.lessons.length + '</div><div class="l">' + t("دروس مكتملة", "Lessons completed") + '</div></div><div class="kpi"><div class="v">' + Object.keys(u.box).length + " / " + S.words.length +
      '</div><div class="l">' + t("كلمات بدأت تعلّمها", "Words started") + '</div></div><div class="kpi"><div class="v">' + learned + '</div><div class="l">' + t("كلمات ثبتت", "Words mastered") + '</div></div><div class="kpi"><div class="v">' + u.xp + '</div><div class="l">' + t("نقاط", "XP") +
      '</div></div></section><button class="btn primary block mt" data-go="placement">' + (u.lvl ? t("أعد اختبار المستوى", "Retake the placement test") : t("اختبر مستواك", "Take the placement test")) + "</button>");
  }
  function placement(n, answers) {
    var P = S.placement;
    if (n >= P.length) {
      var sc = { 1: 0, 2: 0, 3: 0 };
      P.forEach(function (q, i) { if (answers[i] === q.a) sc[q.lv]++; });
      var lvl = sc[1] < 3 ? 1 : (sc[2] < 3 ? 2 : 3), total = sc[1] + sc[2] + sc[3];
      u.lvl = lvl; u.xp += total * 2; save();
      view('<section class="card flash"><div style="font-size:3rem">🎯</div><h2>' + total + " / " + P.length + '</h2><p>' + t("مستواك: ", "Your level: ") + "<b>" + esc(S.levels[lvl]) + '</b></p></section><button class="btn primary block mt" data-go="lessons">' + t("ابدأ الدروس", "Start the lessons") + "</button>");
      return;
    }
    sess = { kind: "placement", n: n, answers: answers };
    view('<div class="progress"><i style="width:' + (100 * n / P.length) + '%"></i></div><p class="muted small mt">' + (n + 1) + " / " + P.length + '</p><section class="card flash"><div class="w" style="font-size:1.35rem">' + esc(P[n].q) + '</div></section><div class="mt">' + opts(P[n].o, "data-ans") + "</div>");
  }

  function go(name) {
    sess = null;
    BF.back("view", null);
    if (name === "new") { tab = "words"; fresh(); }
    else if (name === "placement") { tab = "me"; placement(0, []); }
    else { tab = name; ({ lessons: lessons, words: words, review: review, me: me })[name](); }
    BF.$$(".tab").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-tab") === tab); });
  }

  document.addEventListener("click", function (ev) {
    var tb = ev.target.closest("[data-tab]"), g = ev.target.closest("[data-go]"), l = ev.target.closest("[data-lesson]"), qz = ev.target.closest("[data-quiz]"), an = ev.target.closest("[data-ans]");
    if (tb) { go(tb.getAttribute("data-tab")); }
    else if (g) { ev.preventDefault(); go(g.getAttribute("data-go")); }
    else if (l) { sess = null; lesson(+l.getAttribute("data-lesson")); BF.back("view", function () { go("lessons"); }); }
    else if (qz) { quiz(+qz.getAttribute("data-quiz"), 0, 0); BF.back("view", function () { go("lessons"); }); }
    else if (an && sess && !sess.locked) {
      var i = +an.getAttribute("data-ans"), s = sess;
      if (s.kind === "placement") { placement(s.n + 1, s.answers.concat([i])); return; }
      s.locked = true;
      var ok = i === s.a;
      an.classList.add(ok ? "good" : "bad");
      if (!ok) { var right = document.querySelector('[data-ans="' + s.a + '"]'); if (right) right.classList.add("good"); }
      if (s.kind === "review") {
        var b = u.box[s.k] ? u.box[s.k][0] : 0;
        b = ok ? Math.min(b + 1, GAPS.length - 1) : 0;
        u.box[s.k] = [b, DAY + (ok ? GAPS[b] : 0)];
        if (ok) u.xp += 2;
        save();
      }
      setTimeout(function () {
        if (sess !== s) return;      // انتقل المتعلّم إلى تبويب آخر أثناء الانتظار
        if (s.kind === "quiz") quiz(s.i, s.n + 1, s.score + (ok ? 1 : 0)); else review(ok ? null : s.k);
      }, ok ? 550 : 1300);
    }
  });

  $("#syncNote").textContent = BF.hasUser ? t("تقدّمك محفوظ في حسابك ويظهر في البوت أيضاً.", "Your progress is saved to your account and shows in the bot too.")
                                          : t("تقدّمك محفوظ على هذا الجهاز. افتح الصفحة من داخل البوت ليتزامن مع حسابك.", "Progress is saved on this device. Open the page from the bot to sync it with your account.");
  u.lvl = parseInt(u.lvl, 10) || 0; u.xp = parseInt(u.xp, 10) || 0;
  stats(); lessons();
  if (!ready) {
    BF.api("state").then(function (r) {
      if (r.ok && r.state) { u = r.state; }
      ready = true; stats(); go(tab);
      if (r.ok && r.user && !r.state && (u.xp || Object.keys(u.box).length)) save();      // تقدّم محلي سابق لعضو بلا سجل: نرفعه
    });
  }
})();
