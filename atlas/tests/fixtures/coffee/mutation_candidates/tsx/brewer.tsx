type Label<T> = T extends number ? "a + b" : "Café";
export function Brew({beans, cups}: {beans: number; cups: number}) {
  let total = beans + cups * 2;
  if (beans > 0 && !(cups === 0)) total += 1;
  while (total < 10) total = total + 1;
  return <span>{beans !== 0 ? total : 0}</span>;
}
