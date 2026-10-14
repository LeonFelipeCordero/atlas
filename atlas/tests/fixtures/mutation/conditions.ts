type Choice<T> = T extends string ? true : false;
type Check = (left: string) => boolean;
interface Contract { accepts(value: number): value is number; }
declare function external(value: number): boolean;
const label: Choice<string> = true;
class Machine implements Contract {
  accepts(value: number): value is number {
    const check = (amount: number): boolean => amount > 0 && amount < 10;
    return check(value) || value === 12;
  }
}
function generic<T extends string>(value: T) {
  if (value.length > 0) return value;
  return value ? value : "";
}
