type Label<T> = T extends number ? "a + b" : "Café";
export function brew(beans: number, cups: number): number {
  let total = beans + cups * 2;
  if (beans > 0 && !(cups === 0)) total += 1;
  while (total < 10) total = total + 1;
  for (let cup = 0; cup < cups; cup += 1) total -= cup;
  return beans !== 0 ? total : 0;
}
