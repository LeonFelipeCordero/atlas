# Mutation experiment ledger

Session: `<session_id>`

Root: <project>

Scope: folder; folders: .

Base: none → none

Results are agent-reported, not independently verified. Survivors are candidate testing gaps, not proof of missing required behavior.

## Agent-reported trial counts

killed: 0; survived: 0; invalid: 0; timeout: 0; error: 0; skipped: 0

Unexplored sites (no recorded trial): 2

## Source snapshot status

| Path | Current source | Snapshot SHA-256 |
| --- | --- | --- |
| payments.py | matches-session | 4ac7a13d648d1f24ec5e948f5b31d3d818f3f45836ce05dfe59f64963b741a22 |

## Opportunities

### `71bdd0b5fb00e46ed24af11d92366e3dd986fee2f37bd18c20d58908956d39fa`

payments.py:5:8 — python / comparison

Expression: amount >= minimum

Callable: payments.py::accept_payment@65; selection: folder-scope

Bytes: [109, 126); coordinates are one-based lines and byte columns.

Context:

    def accept_payment(amount, minimum):
        if amount >= minimum:
            return True
        return False

Unexplored: no recorded trial.

### `14501cba3fcd0df0246c36e908a8434ce595db6b817a7d4c5663c4a5fd8d2306`

payments.py:5:8 — python / predicate

Expression: amount >= minimum

Callable: payments.py::accept_payment@65; selection: folder-scope

Bytes: [109, 126); coordinates are one-based lines and byte columns.

Context:

    def accept_payment(amount, minimum):
        if amount >= minimum:
            return True
        return False

Unexplored: no recorded trial.

## Limitations

None reported; this is not a claim of complete mutation coverage.

