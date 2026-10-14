// if (fake && fake > 3) {}
const label = "café 🫘 &&";
function brew(amount, ready) {
  if (ready && amount > 0 || amount === 3) {
    while (amount !== 0) amount--;
  }
  for (let i = 0; i < amount; i++) {}
  for (;;) { break; }
  do { amount--; } while (amount >= 0);
  return ready ? "hot" : "cold";
}
class Machine {
  serve(ready) {
    function nested(value) { return value > 2 && ready; }
    const accepts = value => value == 3 || ready;
    return accepts(3);
  }
}
const anonymous = function(value) { return value in {x: 1}; };
const generator = function*() { yield label instanceof String; };
switch (label) { case "tea": break; }
