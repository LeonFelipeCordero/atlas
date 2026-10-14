<?php
class Ledger {
    function record() {}
}
class OtherLedger {
    function record() {}
}
function annotated(Ledger $ledger) { $ledger->record(); }
function inferred() { $ledger = new Ledger(); $ledger->record(); }
function direct() { (new Ledger())->record(); }
function unknown($ledger) { $ledger->record(); }
function reassigned() { $ledger = new Ledger(); $ledger = factory(); $ledger->record(); }
function other() { $ledger = new OtherLedger(); $ledger->record(); }
function nullable(?Ledger $ledger) { $ledger->record(); }
function union_type(Ledger|OtherLedger $ledger) { $ledger->record(); }
function intersection_type(Ledger&OtherLedger $ledger) { $ledger->record(); }
