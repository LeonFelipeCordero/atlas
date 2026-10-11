interface Transformer {
  transform: <T>(input: T) => T;
  optional?: ((((value: string) => number)));
  "quoted": () => void;
  [Symbol.iterator]: () => Iterator<string>;
  transform(value: string): string;
  transform(value: number): number;
  count: number;
  nested: { callback: () => void };
  factory: new () => Transformer;
}
