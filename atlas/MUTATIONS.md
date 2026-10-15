# Deterministic mutation manifests (phase two)

`atlas mutations -f PROJECT` analyzes current sources without saving, then emits JSON
single-edit manifests. `atlas mutations -f PROJECT --saved` derives the same output
from that folder's indexed candidates, verifying against current source; it never
refreshes the index. `atlas mutations --rules` prints versioned language/token
coverage without analyzing files or opening SQLite.

Only phase-one candidates are persisted, in `graph_mutation_candidates`. Manifests
are derived data: no mutation tables, sessions, ledger or extra persistence lifecycle.
Disabling a rule does not remove candidates. The report API is
`atlas.mutations.report.build_mutation_report(root, report, config)`, accepting either
`build_artifact_report(...)` or `RepositoryService.report(...)` output.

## Configuration

The analyzed folder's existing `atlas.json` accepts an optional `mutations` section
alongside the flat quantitative check limits. No parent-folder search. Missing
configuration, omitted rules, and empty replacement lists select no mutations.
Unknown rule IDs, unsupported replacements and unknown configuration keys fail.
Replacement lists select catalog tokens, never arbitrary generated source.

```json
{
  "maxFunctionLines": 100,
  "mutations": {
    "rules": {
      "arithmetic.add-to-subtract": ["-"],
      "arithmetic.multiply-to-divide": ["/"],
      "comparison.equal-to-not-equal": ["!="],
      "comparison.less-to-less-equal": ["<="],
      "comparison.strict-equal-to-strict-not-equal": ["!=="],
      "logical.and-to-or": ["or", "||"],
      "logical.strict-and-to-or": ["or"],
      "logical.truthy-and-to-or": ["||"],
      "assignment.add-to-subtract": ["-="]
    }
  }
}
```

## Version-one coverage

Binary `+` → `-`, `*` → `/`, comparison `==` → `!=`, and `<` → `<=` cover
JavaScript/JSX, TypeScript, TSX, Java, Kotlin, Python, Rust, Go and Elixir.
JSX uses the JavaScript adapter. Unary signs and pointer dereferences are excluded.
Compound assignment `+=` → `-=` covers the same languages except Elixir (whose
assignment/match semantics are not compound arithmetic assignment).

`===` → `!==` is a separate rule for JavaScript, TypeScript, TSX and Elixir;
it does not turn strict equality into loose equality. Kotlin referential equality
is deliberately not selected. Python `and` → `or` and the other non-Elixir
languages' `&&` → `||` use `logical.and-to-or`. Elixir has separate rules for
strict `and` → `or` and truthy `&&` → `||`; neither crosses those families.

Python chained comparisons change exactly one operator per independent manifest.
Multiword comparisons (`is not`, `not in`), membership, identity,
null-coalescing and all other unlisted operators
are excluded, not silently normalized. Condition candidates remain inspectable but
have no replacement rule: no whole-expression true/false literals, no iterable-for
conversion, and no language-agnostic boolean substitution. Phase-one conservative
Rust macro/token-tree and pattern exclusions remain in force.

Syntax support is **not** proof of type validity, successful compilation, changed
behavior or safety to execute. For example `/` may change numeric types, `+` may
concatenate, overloaded operators may differ, and logical changes may alter
short-circuit evaluation. There is no type inference, macro expansion or execution.

## Manifest contract

Each manifest carries `candidateId`, `sourceHash` (SHA-256 of the entire original
file), `ruleId`, `ruleVersion`, language/path, exact half-open UTF-8 byte `span`,
`originalText`, `replacement`, plus standard-base64 `originalBytes` and
`replacementBytes`. `id` is SHA-256 of canonical UTF-8 JSON of every other manifest
field (sorted keys, compact separators, non-ASCII preserved). Thus identity includes
source, candidate, versioned rule and replacement; filesystem root is not included.
The report envelope has `schemaVersion: 1` and a `mutations` list.

For Python `x = a + b\n`, the add rule yields a manifest with
`span.startByte: 6`, `span.endByte: 7`, `originalText: "+"`,
`originalBytes: "Kw=="`, `replacement: "-"`, `replacementBytes: "LQ=="`,
plus the exact hashes/identity and one-based UTF-8 byte line/column coordinates.

Every input candidate is re-verified using the phase-one extractor, even when its
rule is disabled: source hashes, candidate identity, text/spans, callable context
and syntax provenance must match. Each proposed replacement is reparsed in memory;
its replacement must remain one exact operator token of the same family in valid
syntax, rejecting lexical collisions such as JavaScript `a+--b` → `a---b` or
`a*/regex/` → `a//regex/`. This never writes modified source to disk.
Missing files, unsafe paths, symlinks escaping
the project root and stale/forged candidates fail the entire request. This validates
a read-time snapshot, not a guarantee that a file cannot change afterward.

Output is sorted by path, span, rule, replacement and ID, independent of input or
configuration ordering. Repeated identical byte edits are deduplicated; no no-op
edits are emitted. Nested candidates stay independent. Manifests are alternatives
against the original file, never a composed patch or an instruction to apply them
sequentially.

Phase three is deliberately absent: no applying/restoring source, isolated execution
workspace, target build/test configuration, baselines, outcomes/classification,
agent decisions or dashboard UI.
