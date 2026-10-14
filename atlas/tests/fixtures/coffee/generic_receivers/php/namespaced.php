<?php
namespace Intake;
function namespaced(Ledger $ledger) { $ledger->record(); }
function namespaced_new() { $ledger = new Ledger(); $ledger->record(); }
function namespaced_direct() { (new Ledger())->record(); }
