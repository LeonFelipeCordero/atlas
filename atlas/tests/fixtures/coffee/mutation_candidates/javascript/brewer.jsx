export function brew(beans, cups) {
  const label = "Café + >=";
  let total = beans + cups * 2;
  if (beans > 0 && !(cups === 0)) total += 1;
  while (total < 10) total = total + 1;
  for (let cup = 0; cup < cups; cup += 1) total -= cup;
  return <span title={label}>{beans !== 0 ? total : 0}</span>;
}
