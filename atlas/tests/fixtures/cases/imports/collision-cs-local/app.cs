class Factory { static int Convert(int x) { return x; } }
class App { void Run(){ context.Select(x).Convert(x); Convert(x); } }