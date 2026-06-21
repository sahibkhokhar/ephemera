// Live expiry countdown — progressive enhancement only. Served from 'self' so
// the strict CSP can keep forbidding inline and third-party scripts.
//
// Any element with a data-expires="<ISO 8601 UTC>" attribute has its text
// updated to a live "time remaining" string, ticking every second. Add an
// optional data-suffix to append a word, e.g. data-suffix=" left".
//
//   <span class="recent-ttl"
//         data-expires="{{ item.expires_at.isoformat() }}"
//         data-suffix=" left">{{ item.expires_at | remaining }} left</span>
//
// If JS is off or the attribute is absent, the server-rendered text stands.
(function () {
  "use strict";

  function fmt(ms) {
    if (ms <= 0) return "expired";
    var s = Math.floor(ms / 1000);
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    if (d > 0) return d + "d " + h + "h";
    if (h > 0) return h + "h " + m + "m";
    if (m > 0) return m + "m " + String(sec).padStart(2, "0") + "s";
    return sec + "s";
  }

  var nodes = [];

  function collect() {
    var els = document.querySelectorAll("[data-expires]");
    for (var i = 0; i < els.length; i++) {
      var t = Date.parse(els[i].getAttribute("data-expires"));
      if (!isNaN(t)) {
        nodes.push({ el: els[i], at: t, suffix: els[i].dataset.suffix || "" });
      }
    }
  }

  function tick() {
    var now = Date.now();
    var live = false;
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      var remaining = n.at - now;
      n.el.textContent = fmt(remaining) + (remaining > 0 ? n.suffix : "");
      if (remaining > 0) {
        live = true;
        n.el.classList.remove("is-expired");
      } else {
        n.el.classList.add("is-expired");
      }
    }
    if (live) window.setTimeout(tick, 1000);
  }

  // Decorative loop countdown for the hero terminal: data-countdown="<seconds>".
  // Ticks down once a second and loops back to its start value. No server data.
  function startDecorative() {
    var els = document.querySelectorAll("[data-countdown]");
    if (!els.length) return;
    var items = [];
    for (var i = 0; i < els.length; i++) {
      var start = parseInt(els[i].getAttribute("data-countdown"), 10);
      if (!isNaN(start) && start > 0) items.push({ el: els[i], start: start, secs: start });
    }
    if (!items.length) return;
    function fmtMs(secs) {
      var m = Math.floor(secs / 60), s = secs % 60;
      return m + "m " + String(s).padStart(2, "0") + "s";
    }
    function loop() {
      for (var j = 0; j < items.length; j++) {
        var it = items[j];
        it.secs = it.secs > 0 ? it.secs - 1 : it.start;
        it.el.textContent = fmtMs(it.secs);
      }
      window.setTimeout(loop, 1000);
    }
    loop();
  }

  function init() {
    collect();
    if (nodes.length) tick();
    startDecorative();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
