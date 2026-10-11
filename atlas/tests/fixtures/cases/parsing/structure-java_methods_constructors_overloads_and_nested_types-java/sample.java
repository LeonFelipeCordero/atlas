package demo;
import demo.Other;
interface Runner { void run(); }
class Service implements Runner {
    public Service() {}
    @Deprecated private void run() {}
    void run(int value) {}
    class Nested { public Nested() {} void work() {} }
}
