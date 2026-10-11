const named = () => 0;
const generator = function* internal() { yield 1; };
object.action = function () {};
const holder = { apply: function* () {} };
function outer() { use(() => 0, function () {}, function* () {}, function local() {}); return function () {}; }
