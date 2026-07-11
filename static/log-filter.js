// Small, dependency-free query engine shared by the log viewer and its tests.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.EphemeraLogFilter = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function parse(query) {
    if (query.length >= 2 && query.charAt(0) === "/" && query.charAt(query.length - 1) === "/") {
      try {
        return { type: "regex", value: new RegExp(query.slice(1, -1), "gi") };
      } catch (error) {
        return { type: "invalid", error: "invalid regular expression" };
      }
    }
    return { type: "substring", value: query.toLocaleLowerCase() };
  }

  function matches(text, query) {
    if (!query || query.type === "invalid") return [];
    if (query.type === "substring") {
      var found = [];
      var start = 0;
      var lower = text.toLocaleLowerCase();
      while (query.value && start <= text.length) {
        var index = lower.indexOf(query.value, start);
        if (index < 0) break;
        found.push({ start: index, end: index + query.value.length });
        start = index + Math.max(query.value.length, 1);
      }
      return found;
    }

    var result = [];
    var match;
    while ((match = query.value.exec(text)) !== null) {
      result.push({ start: match.index, end: match.index + match[0].length });
      if (match[0] === "") query.value.lastIndex++;
    }
    query.value.lastIndex = 0;
    return result;
  }

  return { parse: parse, matches: matches };
}));
