# Python mutation gap audit on PR #44

Target: `ff9341eaab63337c71fb7b8290505fe9675f6b63`, the exact head of
`mutations-package-test-coverage`, based on `metrics-mutation-coverage-tests`.
This report adds no production changes or tests. README files are unchanged.

## Scope and method

Fresh Atlas analysis covered the entire disposable project copy. All 18 catalog
rules with Python mappings were enabled in that copy's temporary `atlas.json`.
The production Python code contains 1,536 manifests across 64 of its 93 files.
The other files have no supported mutation candidates. Test code, sample code,
and other languages were excluded from mutation execution.

The first pass selected one manifest per production file: prefer rule IDs
containing `equal` or `logical`, then source byte offset and rule ID. Up to four
baseline-covered tests ran per edit. Selection preferred non-snapshot,
non-pipeline tests, then shorter node IDs. Where no run context existed, the
fallback was `test_coffee_pipeline.py` and `test_coffee_navigation_snapshots.py`.
Each exact focused command passed on pristine code before the mutant ran.
This bounded selection does **not** establish full-suite survival.

Three focused survivors then ran against the complete suite. All three failed.
Further focused-survivor confirmation was stopped for budget; an interrupted
fourth confirmation is not counted. The next three full-suite experiments instead
targeted unexecuted code. This increased the initial 64-mutant sample to 67.

Every edit used the manifest's SHA-256, byte span, and base64 bytes. Each ran
alone and restored the original bytes in `finally`. Sources in both disposable
copies were verified against the manifests after execution. No experimental
mutation or temporary rule configuration was applied to this checkout.

## Results

| Result | Count |
| --- | ---: |
| Selected and executed distinct mutants | 67 |
| Detected by focused tests | 33 |
| Focused survivors detected by the full suite | 3 |
| Confirmed full-suite survivors | 3 |
| Focused survivors not confirmed against the full suite | 28 |

No mutation score is claimed. Only six mutants received completed full-suite
checks. The sample leaves 1,469 production manifests unexecuted. The per-command
timeout was 180 seconds; none of the completed experiments timed out. Initial
planning used 60 seconds, increased after the full baseline took 84 seconds.

“Detected” means a mutation caused a test failure or a runtime failure in a
behavior exercised by tests. This includes exceptions, not just assertion
failures. No syntax or collection failure is counted as a confirmed kill.

## Confirmed gaps

| ID | Location | Exact edit | Missing observation and next action |
| --- | --- | --- | --- |
| 65 | `src/atlas/metrics/adapters/callable_selection.py:206` | Kotlin family `==` → `!=` | Character literals never reach the `Char` versus `char` distinction. Add Java and Kotlin overload sample cases that distinguish character and string arguments; assert the resolved target in the existing sample snapshots. |
| 66 | `src/atlas/parsing/adapters/python.py:34` | definition fallback `or` → `and` | No test enters normalization with a `decorated_definition` wrapper. Establish whether production extraction can pass this wrapper before adding a test. If reachable, extend the decorated declaration sample and snapshot; otherwise consider deleting the redundant defensive path. This is not evidence that decorated functions generally lack coverage. |
| 67 | `src/atlas/persistence/database.py:84` | argument count `== 3` → `!= 3` | The standalone migration entry point has no path-forwarding assertion. Add isolated unit tests for `main()` with default and explicit database paths, mocking `migrate_database` and asserting its argument. Also check missing and invalid command arguments. |

Each confirmed survivor passed **1,774 tests and 78 subtests** after the edit.
These are demonstrated detection gaps, not three confirmed user-visible bugs.
ID 66 needs a reachability decision before adding coverage.

Coverage also found unexecuted mutation locations in JavaScript parenthesis
unwrapping (`parsing/adapters/javascript.py:99,106`), Rust generic callee
unwrapping (`parsing/adapters/rust.py:268`), shared generic callee unwrapping
(`parsing/syntax.py:110`), and migration argument validation
(`persistence/database.py:82`). Those edits were **not executed**. Across all
unexecuted lines, Atlas generated nine manifests at eight distinct locations.

## Evidence and replay

`evidence.jsonl` contains one record per selected mutant: the complete manifest,
exact command, clean-baseline outcome, mutant outcome, and test output. Completed
full-suite confirmation records are attached to their focused records. Paths in
commands are relative to the disposable copy's `atlas/` directory.

`logs/` retains the full baseline and the three confirmed survivor outputs.
External scratch logs were under `/tmp/atlas-python-audit-results/`; the durable
records here do not depend on retaining that directory.

To replay, make a disposable copy of the target commit, install its dependencies
with `uv sync` in `atlas/`, and run a record's command on unchanged sources first.
Decode its manifest bytes, verify the full source SHA-256 and original byte slice,
apply only the specified slice, and rerun that exact command. Restore the bytes
before replaying another record. Do not apply these edits to a working checkout.
The baseline for IDs 65–67 is `logs/full.baseline.log`.

## Validation

The unchanged Python suite passed: 1,774 tests and 78 subtests in 84.42 seconds.
A separate coverage baseline passed in 196.99 seconds and measured 6,100 of 6,179
statements (98.72%; statement coverage only). The independent confirmation copy's
full baseline passed in 86.43 seconds. Commands:

```sh
(cd atlas && uv run pytest -q)
(cd atlas && uv run pyright)
(cd atlas && uv run ruff check .)
(cd dashboard && bun run build)
(cd dashboard && bun test)
(cd dashboard && bun run typecheck)
(cd dashboard && bun lint --fix)
uv run --project atlas atlas check --f .
```

Pyright, Ruff, dashboard build, 200 dashboard tests, TypeScript checking, and
ESLint passed. Dashboard dependencies needed `bun install --no-save` first.
Whole-project Atlas check exited 1 on existing policy violations, including
parameter counts in test helpers. This audit does not fix those violations.

This is a broad file-level sample, not exhaustive mutation testing of Python.
No test or production fix is included. Unsupported operator kinds, unselected
expressions, and the 28 unconfirmed focused survivors remain outside the result.
