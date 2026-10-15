// Apply the saved theme before the stylesheet is parsed, avoiding a flash of
// the wrong palette. This file is intentionally self-hosted and synchronous so
// the strict script-src 'self' CSP does not require inline script.
(function () {
  "use strict";
  var key = "ephemera-theme";
  var saved = null;
  try { saved = window.localStorage.getItem(key); } catch (error) {}
  if (saved === "light" || saved === "dark") {
    document.documentElement.dataset.theme = saved;
  }
})();
