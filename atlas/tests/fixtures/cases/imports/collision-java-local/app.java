class Factory { static int from(int x) { return x; } }
class App { void run() { context.select(X).from(X); from(X); } }