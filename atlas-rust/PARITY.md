# Native parity tests

Python snapshots are the reference. No test updates snapshots. Rust tests invoke Rust APIs and the native executable, never Python. `tests/code_samples` and `tests/snapshots` are local copies of the Python reference fixtures, so native tests do not depend on the Python source tree.

```text
Python fixtures/snapshots ──> cargo test ──> native artifact/report/check/mutations
```

The Python CLI comparison harness and recorded benchmarks have been removed. CI no longer runs cross-runtime CLI or SQLite comparisons.

## Native snapshots

Run from the repository root:

```sh
cargo test --manifest-path atlas-rust/Cargo.toml --test parity --test parity_families --test parity_pipeline --test parity_navigation --test parity_inventory
cargo test --manifest-path atlas-rust/Cargo.toml --test parity_pipeline typescript::same_source_grammar_variants -- --exact
cargo test --manifest-path atlas-rust/Cargo.toml --test parity_families typescript_script_members -- --exact
cargo test --manifest-path atlas-rust/Cargo.toml --test parity python::artifact -- --exact
cargo test --manifest-path atlas-rust/Cargo.toml --test parity python::report -- --exact
cargo test --manifest-path atlas-rust/Cargo.toml --test parity rust::mutation_operators -- --exact
```

The five native parity targets contain 159 tests and cover all 73 unchanged Python golden files. `parity` has 56 artifact/report/check/CLI/mutation tests. `parity_families` adds 11 safety-review, script-member, and JVM callable-selection tests. `parity_pipeline` adds 81 extraction/analysis/staged-graph tests across all nine languages. `parity_navigation` adds eight complete navigation goldens plus two normalization guards. `parity_inventory` rejects new or missing golden files until native coverage is extended.

Each coffee language checks the complete artifact, report JSON/Markdown, check JSON/Markdown, and the complete four-command CLI bundle, including exact exit codes/stderr. Artifacts include all candidates, spans, hashes, edges, views, diagnostics, and circular dependencies. Report/check API tests also use the canonical graph/report as input to isolate failures from parsing.

Pipeline tests reproduce `coffee_pipeline.py`, `project_snapshot_support.py`, and `source_snapshot_fixture.py`: every parsed file, source byte, content hash, optional declaration field, call, import, inheritance, enriched symbol, resolved connection, and external node. They compare native/tag-only/merged structures, all native structure fields, excluded-language bytes and C syntax, and every explicit or JSX shared-grammar variant. Serialization uses the original lowercase byte hex and exact Python `StructureKind` representation; it retains null/empty fields that native serde otherwise omits. No numeric rounding, array sorting, field dropping, or new goldens are used.

Navigation goldens execute all 189 canonical requests against graphs analyzed from physical samples and stored in isolated native SQLite databases. Existing golden `filters` supply requests only; no golden graph/response populates storage. Responses receive the original `normalize_responses` metadata placeholders and root normalization only after checking every response against the saved graph's identical, nonempty repository ID, revision, and timestamp. Node keys, graph fields, provenance, ordering, diagnostics, and source lines remain exact.

Artifact normalization matches `coffee_snapshot`: remove `repository.indexedAt`; replace only the repository path and root node absolute path. Arrays, fields, IDs, hashes, evidence, confidence, numbers, and nulls stay unchanged. Native CLI subprocesses fail after 60 seconds. Set `ATLAS_PARITY_TIMEOUT_SECS` to change that bound; timeout is never a passing result.

## Validation

```sh
cargo test --manifest-path atlas-rust/Cargo.toml --locked --all-targets
cargo build --manifest-path atlas-rust/Cargo.toml --release --locked --bins
cargo fmt --manifest-path atlas-rust/Cargo.toml --check
cargo clippy --manifest-path atlas-rust/Cargo.toml --locked --all-targets -- -D warnings
```

CI runs these native checks. Rust uses its tracked Cargo lockfile. Native runner tests cover mutation path/output protection and interruption cleanup. Permission/race/symlink security permutations from the Python test suite are not all reproduced by native tests.
