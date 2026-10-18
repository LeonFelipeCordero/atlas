# Test suite timing

Measured on the same machine with installed dependencies. These are single-run measurements, not timing assertions. The Python and dashboard changes below did not change README or production code. The Rust follow-up retains behavior coverage while replacing repeated timeout executions with direct priority assertions.

## Suite runtime

Python: **39.17 → 27.90 seconds (29% faster)**, 1,774 tests, four workers.
Dashboard: **27.34 → 14.67 seconds (46% faster)**, 200 tests and 15,024 assertions.
The required Python `-n auto` run also passed in 30.29 seconds; more workers are not necessarily faster on this machine.

## Changes and remaining slow files

- Python service fixtures migrate once per worker instead of per test. Each worker already owns a private database, so the global filesystem lock was unnecessary. Cleanup still deletes registrations and verifies cascading deletion from every graph table after each test.
- Python defaults to xdist `loadfile` scheduling. Tests in one file reuse the same process-local snapshot caches instead of rebuilding bundles on several workers. Worker count remains explicit in the test command.
- Edge-case tests request cached analysis directly instead of also running four unrelated CLI report/check commands per language. Pipeline snapshot tests still cover those CLI commands.
- Dashboard integration suites copy a closed, checkpointed, Python-migrated database template into a private directory per test. They still run real Python indexing and verify Python/dashboard interoperability.
- Compiler boundary regressions reuse dependency syntax trees, but rebuild fixture syntax trees and programs for every case.

Every file above three seconds was inspected. Remaining slow Python files exercise full physical projects through extraction, resolution, indexing, CLI output, and persisted snapshots. Their coverage remains intact. The two remaining dashboard files above three seconds run real Python subprocesses for indexing, reindexing, and persistence compatibility; replacing those with mocks would remove the behavior they test. Compiler boundary regression timing remains near three seconds and can cross that threshold with system load.

## Reproduce

Run from the repository root. Use the same worker count before and after a change. Run the suites separately to avoid CPU contention.

```sh
(cd atlas && uv run pytest -n 4 --durations=0 --junitxml=/tmp/python-tests.xml)
(cd dashboard && bun test --reporter=junit --reporter-outfile=/tmp/dashboard-tests.xml)
```

The tables sum JUnit testcase durations per file. Python includes setup, call, and teardown; parallel file totals are not suite wall time. Bun testcase timings do not fully include suite hooks, including template migration. Shared fixture/cache cost is charged to the first test that needs it. Very small durations can round to zero. Test helpers and code samples are not executable test files.

## Python file totals (seconds)

| File under `atlas/tests/` | Before | After |
| --- | ---: | ---: |
| `test_coffee_pipeline.py` | 53.183 | 26.446 |
| `test_coffee_mutation_manifest_snapshots.py` | 17.769 | 17.470 |
| `test_coffee_edge_cases.py` | 16.177 | 6.271 |
| `test_coffee_mutation_candidate_snapshots.py` | 16.117 | 15.956 |
| `test_coffee_report_snapshots.py` | 8.495 | 9.082 |
| `test_coffee.py` | 5.715 | 5.319 |
| `test_coffee_check_snapshots.py` | 4.829 | 4.588 |
| `test_coffee_navigation_snapshots.py` | 4.804 | 4.789 |
| `services/test_source_contracts.py` | 3.778 | 1.238 |
| `services/test_navigation.py` | 3.663 | 0.940 |
| `services/test_repositories.py` | 3.431 | 0.325 |
| `services/test_navigation_limits.py` | 1.961 | 0.633 |
| `services/test_symbol_contracts.py` | 0.857 | 0.239 |
| `test_coffee_go_rust_receiver_snapshots.py` | 0.408 | 0.323 |
| `services/test_storage_contracts.py` | 0.338 | 0.180 |
| `cli/test_commands.py` | 0.268 | 0.316 |
| `cli/test_graph.py` | 0.215 | 0.269 |
| `test_coffee_safety_review_snapshots.py` | 0.122 | 0.123 |
| `metrics/test_receiver_bindings.py` | 0.096 | 0.043 |
| `test_script_member_coffee_snapshots.py` | 0.065 | 0.070 |
| `metrics/test_artifact.py` | 0.054 | 0.051 |
| `cli/test_mutations.py` | 0.053 | 0.055 |
| `metrics/test_resolution_members.py` | 0.032 | 0.033 |
| `metrics/test_resolver.py` | 0.032 | 0.031 |
| `mutations/test_verification.py` | 0.031 | 0.055 |
| `test_jvm_callable_selection_snapshots.py` | 0.029 | 0.031 |
| `parsing/test_discovery.py` | 0.028 | 0.031 |
| `metrics/test_receiver_resolution.py` | 0.022 | 0.025 |
| `metrics/test_resolution_syntax.py` | 0.019 | 0.015 |
| `metrics/test_adapter_inheritance.py` | 0.018 | 0.022 |
| `mutations/test_config_rules_report.py` | 0.010 | 0.010 |
| `parsing/test_parser.py` | 0.010 | 0.009 |
| `metrics/test_receiver_syntax.py` | 0.009 | 0.014 |
| `metrics/test_cycles.py` | 0.008 | 0.004 |
| `metrics/test_callables.py` | 0.007 | 0.007 |
| `metrics/test_config.py` | 0.007 | 0.006 |
| `parsing/test_structure.py` | 0.007 | 0.006 |
| `metrics/test_adapter_rust_modules.py` | 0.005 | 0.010 |
| `metrics/test_adapter_binding_indexes.py` | 0.004 | 0.002 |
| `metrics/test_adapter_paths.py` | 0.004 | 0.003 |
| `metrics/test_adapter_python_modules.py` | 0.004 | 0.003 |
| `metrics/test_adapter_receivers.py` | 0.003 | 0.005 |
| `metrics/test_adapter_resolution.py` | 0.003 | 0.002 |
| `metrics/test_adapter_syntax.py` | 0.003 | 0.003 |
| `mutations/test_manifests.py` | 0.003 | 0.012 |
| `metrics/test_adapter_elixir_syntax.py` | 0.002 | 0.001 |
| `metrics/test_adapter_policy.py` | 0.002 | 0.001 |
| `metrics/test_adapter_selection.py` | 0.002 | 0.005 |
| `metrics/test_adapter_metrics.py` | 0.001 | 0.000 |
| `metrics/test_adapter_imports.py` | 0.001 | 0.002 |
| `metrics/test_adapter_parameters.py` | 0.000 | 0.001 |
| `metrics/test_adapter_script_members.py` | 0.000 | 0.002 |
| `cli/test_graph_output.py` | 0.000 | 0.000 |
| `metrics/test_check.py` | 0.000 | 0.003 |
| `metrics/test_complexity.py` | 0.000 | 0.002 |
| `metrics/test_resolution_contract.py` | 0.000 | 0.000 |
| `metrics/test_report.py` | 0.000 | 0.002 |
| `metrics/test_report_markdown.py` | 0.000 | 0.001 |
| `metrics/test_dependency_metrics.py` | 0.000 | 0.000 |
| `parsing/test_grammar_boundaries.py` | 0.000 | 0.000 |

## Dashboard file totals (seconds)

| File under `dashboard/` | Before | After |
| --- | ---: | ---: |
| `src/lib/repositories.servers.test.ts` | 9.012 | 3.947 |
| `tests/database-boundary-regressions.test.ts` | 8.672 | 2.958 |
| `src/lib/normalized-graph.servers.test.ts` | 6.138 | 3.341 |
| `tests/database-architecture.test.ts` | 1.783 | 1.709 |
| `src/lib/project-graph.test.ts` | 0.478 | 0.556 |
| `tests/database-factory-boundary.test.ts` | 0.406 | 0.442 |
| `src/routes/graph-project-name.test.ts` | 0.230 | 0.231 |
| `src/components/graph/graph-explorer.test.tsx` | 0.049 | 0.049 |
| `src/components/graph/graph-complexity.test.tsx` | 0.013 | 0.015 |
| `src/lib/graph-analysis.test.ts` | 0.010 | 0.020 |
| `src/components/graph/graph-layout.test.ts` | 0.007 | 0.010 |
| `src/components/graph/graph-dependency-metrics.test.tsx` | 0.006 | 0.007 |
| `src/components/graph/graph-file-complexity.test.tsx` | 0.005 | 0.006 |
| `src/lib/project-graph-boundary.test.ts` | 0.003 | 0.003 |
| `src/components/graph/graph-size-metrics.test.tsx` | 0.002 | 0.003 |
| `src/lib/database.servers.test.ts` | 0.001 | 0.000 |
| `src/lib/graph-cycles.test.ts` | 0.001 | 0.016 |
| `src/lib/project-graph-real.test.ts` | 0.001 | 0.001 |
| `src/components/ui/primitives.test.tsx` | 0.001 | 0.001 |
| `src/lib/graph-visibility.test.ts` | 0.001 | 0.001 |
| `src/branding.test.ts` | 0.000 | 0.000 |

## Validation

Passed: Python tests with four workers and with `-n auto`, Pyright, Ruff, dashboard tests, production build, TypeScript type check, ESLint `--fix`, and `uv run --project atlas atlas check --f .`.

The measurements above preceded stacking this change onto PR #46. After rebasing onto `autonomous-mutation-testing`, all checks passed again: 1,854 Python tests and 200 dashboard tests. That concurrent validation run is not a replacement for the isolated timing measurements above.

## Rust follow-up (PR #55)

Baseline: `253b95a`. Debug tests, installed parser grammars, default test thread count, same machine, no concurrent checks. Compilation is excluded: the first build took 96 seconds. These are single-run measurements, not portable three-second guarantees.

The sum of Cargo's test execution times fell from **49.89 to 24.61 seconds**. The library test executable fell from **32.42 to 6.87 seconds**, including snapshots. All 226 unit tests and 135 integration tests passed. All non-snapshot test files finish below three seconds when measured separately.

The migration test uses a 100 ms deadline and a 10 ms SQLite busy timeout on its private connection. Production keeps its 30-second deadline, busy timeout, and error message. The test still checks rollback, unchanged migration history, and reuse of the connection after timeout.

Mutation outcome priority is checked directly in both target orders. Two multi-target integration cases still check real execution, recorded outcomes, and source restoration. `runner_process_tests.rs` still exercises a real one-second timeout and child-process cleanup. This avoids three extra one-second waits under the runner's process-wide signal-handler lock.

### Rust integration file times (seconds)

Paths are under `atlas-rust/tests/`. Values come from Cargo's per-executable summaries. Snapshot suites were measured but not optimized.

```text
File                       Before   After
architecture.rs             0.36     0.36
cli.rs                      0.03     0.03
cli_numeric.rs              0.16     0.16
cli_validation.rs           0.09     0.09
discovery_failures.rs        0.03     0.03
metrics.rs                  0.12     0.12
metrics_patterns.rs         0.06     0.07
mutation_safety.rs          0.57     0.57
navigation_budget.rs        0.06     0.06
parity.rs                   9.61     9.83  snapshot suite, excluded
parity_families.rs          0.22     0.21
parity_inventory.rs         0.00     0.00
parity_navigation.rs        2.43     2.43  snapshot suite, excluded
parity_pipeline.rs          3.67     3.72  snapshot suite, excluded
reindex.rs                  0.06     0.06
```

### Rust unit source file times (seconds)

Paths are under `atlas-rust/src/atlas/`. Each source file's tests ran in a fresh library test process, with default test threads and exact fully qualified test-name filters. Values include process startup. These isolated file times do not sum to the parallel library suite time. Inline test modules are included. Shared helper files have no independent test runtime.

```text
File                                              Before   After
cli/graph_output.rs                                0.002   0.003
cli/integers.rs                                    0.005   0.005
cli/mutation_targets.rs                            0.002   0.003
cli/mutations.rs                                   0.018   0.019
cli/options_tests.rs                               0.007   0.008
cli/schema.rs                                     0.003   0.003
metrics/adapters/base.rs                           0.004   0.004
metrics/adapters/callable_selection.rs             0.008   0.007
metrics/adapters/elixir_tests.rs                   0.157   0.152
metrics/adapters/generic.rs                        0.003   0.003
metrics/adapters/go.rs                             0.014   0.013
metrics/adapters/java.rs                           0.090   0.089
metrics/adapters/javascript.rs                     0.015   0.015
metrics/adapters/kotlin.rs                         0.019   0.019
metrics/adapters/parameters.rs                     0.003   0.003
metrics/adapters/python.rs                         0.019   0.017
metrics/adapters/resolution.rs                     0.020   0.020
metrics/adapters/resolution_metadata.rs            0.002   0.003
metrics/adapters/resolution_paths.rs               0.024   0.024
metrics/adapters/rust_tests.rs                     0.145   0.146
metrics/adapters/rust_unicode.rs                   0.002   0.002
metrics/adapters/script_adapter_tests.rs           0.101   0.112
metrics/adapters/script_python_selection.rs        0.003   0.003
metrics/adapters/script_resolution.rs              0.014   0.014
metrics/adapters/typescript.rs                     0.003   0.003
metrics/receiver_aliases.rs                        0.008   0.009
metrics/receiver_tests.rs                          0.072   0.073
metrics/resolution_syntax.rs                       0.100   0.090
metrics/resolver.rs                                0.002   0.002
metrics/resolver_graph.rs                          0.002   0.002
metrics/resolver_tests.rs                          0.024   0.017
mutations/manifests.rs                             0.002   0.002
mutations/runner_process_tests.rs                  1.203   1.194
mutations/runner_tests.rs                          3.503   0.444
mutations/tests.rs                                4.956   5.052  snapshots, excluded
parsing/adapters/rust_macro_tests.rs               0.099   0.103
parsing/adapters/tests.rs                          0.168   0.165
parsing/discovery.rs                               0.015   0.016
parsing/discovery_open.rs                          0.002   0.002
parsing/ignore_spec.rs                             0.027   0.026
parsing/structure_tests.rs                         0.144   0.147
parsing/tests.rs                                   0.047   0.037
paths/home.rs                                     0.003   0.003
persistence/migration_tests.rs                    30.020   0.276
persistence/tests.rs                               0.379   0.379
```

Reproduce the suite summaries and the two changed unit-file groups from the repository root:

```sh
cargo test --manifest-path atlas-rust/Cargo.toml --locked --all-targets
cargo test --manifest-path atlas-rust/Cargo.toml --locked --lib persistence::migration_tests::
cargo test --manifest-path atlas-rust/Cargo.toml --locked --lib mutations::runner_tests::
```

For isolated file timings, build first with `cargo test --manifest-path atlas-rust/Cargo.toml --locked --lib --no-run`. Use the reported library test executable with `--list` to obtain test names, then run it with `--exact` and all test names belonging to one source file. Measure that process's elapsed time, not compilation. Macro-defined tests belong to the source file defining the test macro.

Validation passed: Rust all-target tests, locked release binary build, formatting, Clippy with warnings denied, and whole-project `uv run --project atlas atlas check --f .`. The shortened lock-timeout test also passed 20 consecutive isolated runs. Python and dashboard suites were not run because their code, shared fixtures, schemas, and output contracts did not change. Mutation campaigns were not run.
