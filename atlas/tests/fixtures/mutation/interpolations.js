function describe(x) {
  const text = "literal x > 100 && x < 200";
  return `literal x > 99: ${x > 0}, ${x < 10 && x !== 3 ? "yes" : "no"}`;
}
