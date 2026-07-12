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
      if (query.length === 2) return { type: "empty", value: "" };
      try {
        return { type: "regex", value: new RegExp(query.slice(1, -1), "gi") };
      } catch (error) {
        return { type: "invalid", error: "invalid regular expression" };
      }
    }
    return { type: "substring", value: query.toLocaleLowerCase() };
  }

  function folded(text) {
    var value = "";
    var offsets = [];
    var codePoints = Array.from(text);
    var originalOffset = 0;
    for (var i = 0; i < codePoints.length; i++) {
      var point = codePoints[i];
      var lower = point.toLocaleLowerCase();
      value += lower;
      for (var j = 0; j < lower.length; j++) {
        offsets.push({ start: originalOffset, end: originalOffset + point.length });
      }
      originalOffset += point.length;
    }
    return { value: value, offsets: offsets };
  }

  function matches(text, query) {
    if (!query || query.type === "invalid" || query.type === "empty") return [];
    if (query.type === "substring") {
      var found = [];
      var start = 0;
      var lower = folded(text);
      while (query.value && start <= lower.value.length) {
        var index = lower.value.indexOf(query.value, start);
        if (index < 0) break;
        var end = index + query.value.length;
        found.push({ start: lower.offsets[index].start, end: lower.offsets[end - 1].end });
        start = index + Math.max(query.value.length, 1);
      }
      return found;
    }

    var result = [];
    var match;
    while ((match = query.value.exec(text)) !== null) {
      if (match[0].length) result.push({ start: match.index, end: match.index + match[0].length });
      else query.value.lastIndex++;
    }
    query.value.lastIndex = 0;
    return result;
  }

  return { parse: parse, matches: matches };
}));
