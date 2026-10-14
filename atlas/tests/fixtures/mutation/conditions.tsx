type Choice<T> = T extends string ? true : false;
const label = "café 🫘";
export function Panel({ready}: {ready: boolean}) {
  const render = (amount: number) => amount > 0 ? <span>{label}</span> : null;
  return <section title="x > y && z">{ready && render(3)}</section>;
}
