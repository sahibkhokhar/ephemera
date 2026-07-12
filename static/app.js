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

  // ---- log issues: ribbon + minimap --------------------------------------

  var WARN_RE = /\bWARN(?:ING)?\b/i;
  var ERROR_RE = /\b(?:ERROR|FATAL|FAILED|FAILURE)\b/i;

  function highlight(textEl, ranges) {
    var text = textEl.textContent;
    textEl.textContent = "";
    var cursor = 0;
    for (var i = 0; i < ranges.length; i++) {
      var range = ranges[i];
      if (range.start > cursor) textEl.appendChild(document.createTextNode(text.slice(cursor, range.start)));
      var mark = document.createElement("mark");
      mark.className = "log-match";
      mark.textContent = text.slice(range.start, range.end);
      textEl.appendChild(mark);
      cursor = range.end;
    }
    if (cursor < text.length) textEl.appendChild(document.createTextNode(text.slice(cursor)));
  }

  function isVisibleLine(line) {
    if (line.hidden) return false;
    var body = line.closest(".code-body");
    if (body && ((body.classList.contains("filter-error") && !line.classList.contains("ln-error")) ||
        (body.classList.contains("filter-warn") && !line.classList.contains("ln-warn")) ||
        (body.classList.contains("is-filtered") && !line.classList.contains("ln-issue")))) return false;
    return !window.getComputedStyle || window.getComputedStyle(line).display !== "none";
  }

  function initLogFilter(body) {
    var view = body.closest(".code-view");
    var filter = view && view.querySelector("[data-log-filter]");
    if (!filter || !window.EphemeraLogFilter) return;
    var input = filter.querySelector("[data-filter-input]");
    var status = filter.querySelector("[data-filter-status]");
    var clear = filter.querySelector("[data-filter-clear]");
    var previous = filter.querySelector("[data-filter-prev]");
    var next = filter.querySelector("[data-filter-next]");
    var lines = Array.prototype.slice.call(body.querySelectorAll(".ln"));
    var current = -1;
    var matchingLines = [];
    var totalOccurrences = 0;

    function resetHighlights() {
      for (var i = 0; i < lines.length; i++) {
        var textEl = lines[i].querySelector(".ln-text");
        var text = textEl.textContent;
        textEl.textContent = text;
        lines[i].classList.remove("ln-search-match");
        lines[i].removeAttribute("aria-current");
      }
    }

    function updateStatus(label) {
      status.textContent = label;
      var enabled = matchingLines.length > 0;
      previous.disabled = !enabled;
      next.disabled = !enabled;
      clear.hidden = !input.value;
    }

    function apply() {
      var queryText = input.value;
      var query = window.EphemeraLogFilter.parse(queryText);
      resetHighlights();
      matchingLines = [];
      current = -1;
      totalOccurrences = 0;
      if (!queryText || query.type === "empty") {
        for (var i = 0; i < lines.length; i++) lines[i].hidden = false;
        updateStatus("all lines");
        return;
      }
      if (query.type === "invalid") {
        for (var j = 0; j < lines.length; j++) lines[j].hidden = false;
        updateStatus(query.error);
        return;
      }
      for (var k = 0; k < lines.length; k++) {
        var textEl = lines[k].querySelector(".ln-text");
        var ranges = window.EphemeraLogFilter.matches(textEl.textContent, query);
        lines[k].hidden = false;
        var visible = isVisibleLine(lines[k]);
        lines[k].hidden = !ranges.length;
        if (ranges.length && visible) {
          lines[k].classList.add("ln-search-match");
          highlight(textEl, ranges);
          matchingLines.push({ el: lines[k], ranges: ranges });
          totalOccurrences += ranges.length;
        }
      }
      updateStatus(totalOccurrences + " match" + (totalOccurrences === 1 ? "" : "es") +
        " · " + matchingLines.length + " line" + (matchingLines.length === 1 ? "" : "s"));
    }

    function move(step) {
      if (!matchingLines.length) return;
      current = (current + step + matchingLines.length) % matchingLines.length;
      for (var i = 0; i < matchingLines.length; i++) matchingLines[i].el.removeAttribute("aria-current");
      matchingLines[current].el.setAttribute("aria-current", "true");
      status.textContent = "match " + (current + 1) + " of " + matchingLines.length +
        " · " + totalOccurrences + " total";
      jumpTo(matchingLines[current].el);
    }

    input.addEventListener("input", apply);
    previous.addEventListener("click", function () { move(-1); });
    next.addEventListener("click", function () { move(1); });
    clear.addEventListener("click", function () {
      input.value = "";
      input.focus();
      apply();
    });
    body.addEventListener("keydown", function (event) {
      if ((event.key === "n" || event.key === "N") && document.activeElement !== input && matchingLines.length) {
        event.preventDefault();
        move(event.key === "n" ? 1 : -1);
      }
    });
    body.addEventListener("log-filter-visibility-change", apply);
    apply();
  }

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
    if (!isVisibleLine(el)) return;
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
      if (!wasOn) {
        chip.setAttribute("aria-pressed", "true");
        body.classList.add(filterClass);
      }
      body.dispatchEvent(new CustomEvent("log-filter-visibility-change"));
      // Land on the first matching issue so the filter feels like a jump too.
      var candidates = body.querySelectorAll(kind === "error" ? ".ln-error" : ".ln-warn");
      for (var i = 0; i < candidates.length; i++) {
        if (isVisibleLine(candidates[i])) { jumpTo(candidates[i]); break; }
      }
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
    var logs = document.querySelectorAll(".code-body[data-log]");
    for (var i = 0; i < logs.length; i++) {
      var body = logs[i];
      var scan = scanLog(body);
      initLogFilter(body);
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
