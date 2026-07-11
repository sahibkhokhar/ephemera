const assert = require("assert");
const filter = require("../static/log-filter.js");

assert.deepStrictEqual(filter.matches("INFO ready", filter.parse("ready")), [{start: 5, end: 10}]);
assert.deepStrictEqual(filter.matches("warn WARN", filter.parse("warn")), [
  {start: 0, end: 4}, {start: 5, end: 9}
]);
assert.deepStrictEqual(filter.matches("INFO ready\nERROR failed", filter.parse("/error/")), [{start: 11, end: 16}]);
assert.strictEqual(filter.parse("/[unclosed/").type, "invalid");
console.log("log filter core: ok");
