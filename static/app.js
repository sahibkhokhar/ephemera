// Progressive enhancement only: copy-to-clipboard and per-kind artifact
// actions. Loaded with `defer` and served from 'self' so the page CSP can
// forbid inline and third-party scripts.
(function () {
  "use strict";

  function flash(btn, label) {
    var original = btn.dataset.label || btn.textContent;
    btn.dataset.label = original;
    btn.textContent = label;
    btn.classList.add("is-copied");
    window.setTimeout(function () {
      btn.textContent = original;
      btn.classList.remove("is-copied");
    }, 1400);
  }

  function decodeSource(source) {
    if (source.dataset.encoded === "base64") {
      var bytes = Uint8Array.from(atob(source.value), function (c) { return c.charCodeAt(0); });
      return new TextDecoder().decode(bytes);
    }
    return source.value;
  }

  function sourceFor(btn) {
    if (btn.dataset.copyText !== undefined) {
      return btn.dataset.copyText;
    }
    var root = btn.closest("[data-copy-root]");
    if (!root) return null;
    var format = btn.dataset.copyFormat || "default";
    var source = root.querySelector('.copy-source[data-format="' + format + '"]');
    if (!source && format !== "default") {
      source = root.querySelector('.copy-source[data-format="default"]');
    }
    if (!source) {
      source = root.querySelector(".copy-source");
    }
    if (!source) return null;
    return decodeSource(source);
  }

  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback for non-secure contexts (e.g. plain-HTTP LAN access).
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy") ? resolve() : reject();
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(ta);
      }
    });
  }

  // ---- per-kind actions --------------------------------------------------

  var WARN_RE = /\bWARN(?:ING)?\b/i;
  var ERROR_RE = /\b(?:ERROR|FATAL|FAILED|FAILURE)\b/i;

  // Tag log lines so the highlight/filter/jump actions have something to act on.
  function markLog(body) {
    var lines = body.querySelectorAll(".ln");
    for (var i = 0; i < lines.length; i++) {
      var text = lines[i].textContent;
      if (ERROR_RE.test(text)) {
        lines[i].classList.add("ln-error", "ln-issue");
      } else if (WARN_RE.test(text)) {
        lines[i].classList.add("ln-warn", "ln-issue");
      }
    }
  }

  function setPressed(btn, on) {
    if (btn.hasAttribute("aria-pressed")) {
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    }
  }

  function fillSource(source) {
    var target = source.querySelector("[data-source-target]");
    if (target && !target.dataset.filled) {
      var raw = source.querySelector(".copy-source");
      if (raw) {
        target.textContent = decodeSource(raw);
        target.dataset.filled = "1";
      }
    }
  }

  function selectView(tab) {
    var root = tab.closest(".artifact");
    if (!root) return;
    var selected = tab.dataset.tab;
    var views = root.querySelectorAll("[data-view]");
    for (var i = 0; i < views.length; i++) {
      var isSelected = views[i].dataset.view === selected;
      views[i].toggleAttribute("hidden", !isSelected);
      if (isSelected && selected === "source") {
        fillSource(views[i]);
      }
    }

    var tabs = root.querySelectorAll("[data-tab]");
    for (var j = 0; j < tabs.length; j++) {
      tabs[j].classList.toggle("is-active", tabs[j] === tab);
    }
  }

  function jumpToIssue(root, btn) {
    var body = root.querySelector(".code-body");
    if (!body) return;
    body.classList.add("is-highlighted");
    var first = body.querySelector(".ln-issue");
    if (!first) {
      flash(btn, "No issues");
      return;
    }
    first.scrollIntoView({ block: "center" });
    first.classList.add("ln-flash");
    window.setTimeout(function () { first.classList.remove("ln-flash"); }, 1200);
  }

  function handleAction(btn) {
    var action = btn.dataset.action;
    var root = btn.closest(".artifact");
    if (!root) return;
    var body = root.querySelector(".code-body");
    switch (action) {
      case "toggle-wrap":
        if (body) setPressed(btn, body.classList.toggle("is-wrapped"));
        break;
      case "toggle-numbers":
        if (body) setPressed(btn, body.classList.toggle("numbered"));
        break;
      case "log-highlight":
        if (body) setPressed(btn, body.classList.toggle("is-highlighted"));
        break;
      case "log-filter":
        if (body) setPressed(btn, body.classList.toggle("is-filtered"));
        break;
      case "log-jump":
        jumpToIssue(root, btn);
        break;
      case "zoom":
        var img = root.querySelector(".image-frame img");
        if (img) setPressed(btn, img.classList.toggle("is-zoomed"));
        break;
      case "print":
        window.print();
        break;
    }
  }

  // ---- wiring ------------------------------------------------------------

  document.addEventListener("click", function (event) {
    var tabBtn = event.target.closest("[data-tab]");
    if (tabBtn) {
      event.preventDefault();
      selectView(tabBtn);
      return;
    }

    var actionBtn = event.target.closest("[data-action]");
    if (actionBtn) {
      event.preventDefault();
      handleAction(actionBtn);
      return;
    }
    var btn = event.target.closest("[data-copy]");
    if (!btn) return;
    var text = sourceFor(btn);
    if (text == null) return;
    event.preventDefault();
    copy(text).then(
      function () { flash(btn, "Copied"); },
      function () { flash(btn, "Press Ctrl+C"); }
    );
  });

  function init() {
    var logs = document.querySelectorAll(".code-body[data-log]");
    for (var i = 0; i < logs.length; i++) {
      markLog(logs[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
