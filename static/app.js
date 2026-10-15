// Progressive enhancement only: copy-to-clipboard, per-kind view controls, the
// log issue-ribbon, and the minimap gutter. Loaded with `defer` and served from
// 'self' so the page CSP can forbid inline and third-party scripts.
(function () {
  "use strict";

  // Save/restore innerHTML so buttons that contain an inline SVG icon keep it
  // after the transient "Copied" label.
  function flash(btn, label) {
    if (btn.dataset.flashing) return;
    btn.dataset.flashing = "1";
    var html = btn.innerHTML;
    btn.textContent = label;
    btn.classList.add("is-copied");
    window.setTimeout(function () {
      btn.innerHTML = html;
      btn.classList.remove("is-copied");
      delete btn.dataset.flashing;
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

  // ---- theme ------------------------------------------------------------

  var THEME_KEY = "ephemera-theme";

  function preferredTheme() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light" : "dark";
  }

  function currentTheme() {
    return document.documentElement.dataset.theme || preferredTheme();
  }

  function savedTheme() {
    var saved = null;
    try { saved = window.localStorage.getItem(THEME_KEY); } catch (error) {}
    return saved === "light" || saved === "dark" ? saved : null;
  }

  function updateThemeControl() {
    var theme = currentTheme();
    var controls = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < controls.length; i++) {
      var control = controls[i];
      var next = theme === "dark" ? "light" : "dark";
      control.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
      control.setAttribute("aria-label", "Switch to " + next + " mode");
    }
  }

  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try { window.localStorage.setItem(THEME_KEY, theme); } catch (error) {}
    updateThemeControl();
  }

  var colorScheme = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)");
  function followSystemTheme() {
    if (savedTheme() !== null) return;
    delete document.documentElement.dataset.theme;
    updateThemeControl();
  }
  if (colorScheme) {
    if (colorScheme.addEventListener) {
      colorScheme.addEventListener("change", followSystemTheme);
    } else if (colorScheme.addListener) {
      colorScheme.addListener(followSystemTheme);
    }
  }

  // ---- log issues: ribbon + minimap --------------------------------------

  var WARN_RE = /\bWARN(?:ING)?\b/i;
  var ERROR_RE = /\b(?:ERROR|FATAL|FAILED|FAILURE)\b/i;

  // Tag each WARN/ERROR line and collect their positions for ribbon + minimap.
  function scanLog(body) {
    var lines = body.querySelectorAll(".ln");
    var issues = [];
    var errors = 0;
    var warnings = 0;
    for (var i = 0; i < lines.length; i++) {
      var text = lines[i].textContent;
      if (ERROR_RE.test(text)) {
        lines[i].classList.add("ln-error", "ln-issue");
        issues.push({ el: lines[i], idx: i, type: "error" });
        errors++;
      } else if (WARN_RE.test(text)) {
        lines[i].classList.add("ln-warn", "ln-issue");
        issues.push({ el: lines[i], idx: i, type: "warn" });
        warnings++;
      }
    }
    return { total: lines.length, issues: issues, errors: errors, warnings: warnings };
  }

  function jumpTo(el) {
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    el.classList.add("ln-flash");
    window.setTimeout(function () { el.classList.remove("ln-flash"); }, 1200);
  }

  function makeChip(body, kind, count) {
    var label = count + " " + (kind === "error" ? "error" : "warning") + (count === 1 ? "" : "s");
    var filterClass = kind === "error" ? "filter-error" : "filter-warn";
    var chip = document.createElement("button");
    chip.type = "button";
    chip.className = "ichip ichip-" + (kind === "error" ? "error" : "warn");
    chip.setAttribute("aria-pressed", "false");
    chip.innerHTML = '<span class="idot" aria-hidden="true"></span>' + label;
    chip.addEventListener("click", function () {
      var wasOn = chip.getAttribute("aria-pressed") === "true";
      var ribbon = chip.parentNode;
      var chips = ribbon.querySelectorAll(".ichip");
      for (var i = 0; i < chips.length; i++) chips[i].setAttribute("aria-pressed", "false");
      body.classList.remove("filter-error", "filter-warn");
      if (wasOn) return;                       // toggle off → show everything
      chip.setAttribute("aria-pressed", "true");
      body.classList.add(filterClass);
      // Land on the first matching issue so the filter feels like a jump too.
      var first = body.querySelector(kind === "error" ? ".ln-error" : ".ln-warn");
      if (first) jumpTo(first);
    });
    return chip;
  }

  function buildRibbon(ribbon, body, scan) {
    if (scan.errors) ribbon.appendChild(makeChip(body, "error", scan.errors));
    if (scan.warnings) ribbon.appendChild(makeChip(body, "warn", scan.warnings));
  }

  function buildMinimap(map, scan) {
    if (!scan.issues.length) return;
    for (var i = 0; i < scan.issues.length; i++) {
      var issue = scan.issues[i];
      var tick = document.createElement("span");
      tick.className = "tick tick-" + (issue.type === "error" ? "error" : "warn");
      tick.style.top = ((issue.idx + 0.5) / scan.total * 100).toFixed(2) + "%";
      tick.title = "Line " + (issue.idx + 1);
      (function (el) {
        tick.addEventListener("click", function () { jumpTo(el); });
      })(issue.el);
      map.appendChild(tick);
    }
  }

  // ---- view controls -----------------------------------------------------

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
      case "zoom":
        var img = root.querySelector(".image-frame img");
        if (img) setPressed(btn, img.classList.toggle("is-zoomed"));
        break;
      case "print":
        window.print();
        break;
    }
  }

  // ---- overflow (export) menu --------------------------------------------

  function closeMenus(except) {
    var menus = document.querySelectorAll("[data-overflow-menu]");
    for (var i = 0; i < menus.length; i++) {
      if (menus[i] === except) continue;
      menus[i].hidden = true;
      var toggle = menus[i].parentNode.querySelector("[data-overflow-toggle]");
      if (toggle) toggle.setAttribute("aria-expanded", "false");
    }
  }

  // ---- wiring ------------------------------------------------------------

  document.addEventListener("click", function (event) {
    var themeToggle = event.target.closest("[data-theme-toggle]");
    if (themeToggle) {
      event.preventDefault();
      setTheme(currentTheme() === "dark" ? "light" : "dark");
      return;
    }
    var toggle = event.target.closest("[data-overflow-toggle]");
    if (toggle) {
      event.preventDefault();
      var menu = toggle.parentNode.querySelector("[data-overflow-menu]");
      var open = menu.hidden;
      closeMenus(menu);
      menu.hidden = !open;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      return;
    }
    if (!event.target.closest("[data-overflow-menu]")) closeMenus();

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
      function () { flash(btn, btn.classList.contains("meta-id") ? "copied ✓" : "Copied"); },
      function () { flash(btn, "Press Ctrl+C"); }
    );
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeMenus();
  });

  function init() {
    updateThemeControl();
    var logs = document.querySelectorAll(".code-body[data-log]");
    for (var i = 0; i < logs.length; i++) {
      var body = logs[i];
      var scan = scanLog(body);
      var pane = body.closest(".code-pane") || body.parentNode;
      var view = body.closest(".code-view");
      var ribbon = view && view.querySelector("[data-ribbon]");
      if (ribbon) buildRibbon(ribbon, body, scan);
      var map = pane.querySelector("[data-minimap]");
      if (map) buildMinimap(map, scan);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
