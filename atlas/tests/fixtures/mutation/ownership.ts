class C {
  f = (x: number) => { const unused = 1; return x > 0; };
  g = (x: number) => x > 2;
}

abstract class A {
  f(x: number) { const unused = 2; return x > 0; }
}

abstract class B {
  f(x: number) { return x > 2; }
}
