<?php
use Unrelated\Ledger;
function imported(Ledger $ledger) { $ledger->record(); }
function imported_new() { $ledger = new Ledger(); $ledger->record(); }
function imported_direct() { (new Ledger())->record(); }
