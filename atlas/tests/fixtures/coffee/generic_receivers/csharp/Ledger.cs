class Ledger {
    public void Record() {}
}
class OtherLedger {
    public void Record() {}
}
class Intake {
    void Annotated(Ledger ledger) { ledger.Record(); }
    void Local() { Ledger ledger = new Ledger(); ledger.Record(); }
    void Inferred() { var ledger = new Ledger(); ledger.Record(); }
    void Direct() { new Ledger().Record(); }
    void Unknown(dynamic unknown) { unknown.Record(); }
    void Factory() { var ledger = MakeLedger(); ledger.Record(); }
    void Reassigned() { var ledger = new Ledger(); ledger = MakeLedger(); ledger.Record(); }
    void Other() { var ledger = new OtherLedger(); ledger.Record(); }
    Ledger MakeLedger() { return new Ledger(); }
    void GenericMethod<Ledger>(Ledger ledger) { ledger.Record(); }
    void GenericLocal<Ledger>(Ledger input) { Ledger ledger = input; ledger.Record(); }
    void Constrained<Ledger>(Ledger ledger) where Ledger : OtherLedger { ledger.Record(); }
}
class GenericIntake<Ledger> {
    void GenericClass(Ledger ledger) { ledger.Record(); }
    class Nested {
        void GenericNested(Ledger ledger) { ledger.Record(); }
    }
}
