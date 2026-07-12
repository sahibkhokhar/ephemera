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

  function topLevelAlternatives(source) {
    var alternatives = [];
    var start = 0;
    var depth = 0;
    var inClass = false;
    var escaped = false;
    for (var i = 0; i < source.length; i++) {
      var character = source.charAt(i);
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === "[" && !inClass) {
        inClass = true;
      } else if (character === "]" && inClass) {
        inClass = false;
      } else if (!inClass && character === "(") {
        depth++;
      } else if (!inClass && character === ")") {
        depth--;
      } else if (!inClass && depth === 0 && character === "|") {
        alternatives.push(source.slice(start, i));
        start = i + 1;
      }
    }
    if (!alternatives.length) return [source];
    alternatives.push(source.slice(start));
    return alternatives;
  }

  function nextConsumingMatch(regex, text, from) {
    var match;
    var position = from;
    while (position <= text.length && (match = regex.exec(text)) !== null) {
      if (match[0].length) return match;
      position = match.index + 1;
      regex.lastIndex = position;
    }
    return null;
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
    var alternatives = topLevelAlternatives(query.value.source);
    var position = 0;
    while (position <= text.length) {
      var next = null;
      for (var i = 0; i < alternatives.length; i++) {
        var regex = new RegExp(alternatives[i], "gi");
        regex.lastIndex = position;
        var candidate = nextConsumingMatch(regex, text, position);
        if (candidate && (!next || candidate.index < next.index)) next = candidate;
      }
      if (!next) break;
      result.push({ start: next.index, end: next.index + next[0].length });
      position = next.index + next[0].length;
    }
    query.value.lastIndex = 0;
    return result;
  }

  return { parse: parse, matches: matches };
}));
