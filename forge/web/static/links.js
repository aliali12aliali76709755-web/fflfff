/* صفحة الروابط */
(function () {
  "use strict";
  var BF = window.BF, S = BF.S, $ = BF.$, esc = BF.esc, t = BF.t;
  var nodes = (S.nodes || []).map(function (n) { n.id = parseInt(n.id, 10) || 0; n.p = parseInt(n.p, 10) || 0; return n; }), cur = 0;
  function kids(p) { return nodes.filter(function (n) { return n.p === p; }); }
  function node(id) { return nodes.filter(function (n) { return n.id === id; })[0]; }
  function draw() {
    var n = cur ? node(cur) : null, list = kids(cur);
    $("#crumb").hidden = !n;
    if (n) $("#title").textContent = n.t;
    var c = $("#content");
    c.hidden = !(n && (n.html || n.media));
    if (n && n.media) {
      c.innerHTML = '<p class="muted">' + t("هذا المحتوى صورة أو ملف يُعرض داخل البوت.", "This content is a photo or file shown inside the bot.") + '</p><a class="btn primary block mt" href="' + esc(S.tg + "?start=v" + n.id) + '">' + t("افتحه في تيليجرام", "Open it in Telegram") + "</a>";
    } else if (n) { c.innerHTML = n.html; }
    $("#links").innerHTML = list.map(function (k) {
      var direct = k.url && !kids(k.id).length;
      return direct ? '<a class="link" href="' + esc(k.url) + '" target="_blank" rel="noopener nofollow"><span>' + esc(k.t) + '</span><span class="arr">↗</span></a>'
                    : '<button class="link" data-node="' + k.id + '"><span>' + esc(k.t) + '</span><span class="arr">‹</span></button>';
    }).join("");
    $("#none").hidden = !!(list.length || n);
    BF.back("node", n ? function () { cur = n.p; draw(); } : null);
    window.scrollTo(0, 0);
  }
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-node]");
    if (b) { cur = +b.getAttribute("data-node"); draw(); }
  });
  $("#up").addEventListener("click", function () { var n = node(cur); cur = n ? n.p : 0; draw(); });
  draw();
})();
