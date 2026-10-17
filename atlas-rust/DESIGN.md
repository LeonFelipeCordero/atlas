# Native Atlas importer

`src/atlas/` follows the Python package layout. Rust modules use `.rs` and `mod.rs` in place of `.py` and `__init__.py`. Large modules split into adjacent helpers. The binary names remain `atlas` and `atlas-migrate`.

```text
cli -> services -> indexer -> parsing -> metrics -> graph artifact
          |
          +-> domain contracts -> persistence -> SQLite
```

Parsing uses `tree-sitter-language-pack` 1.20.0, matching the pinned Python package version. The language catalog and exclusions come from the reference importer. The pinned Python wheel and Rust crate contain different tag-query assets despite the same version. `parsing/queries/` retains the wheel's 64 tag queries to preserve extraction results, with the upstream MIT license. Dedicated language adapters retain language-specific extraction, metric and resolution policies; other supported grammars use generic extraction.

References: [language pack crate](https://crates.io/crates/tree-sitter-language-pack/1.20.0), [native API](https://docs.rs/tree-sitter-language-pack/1.20.0/tree_sitter_language_pack/), [Diesel SQLite](https://diesel.rs/guides/getting-started).

Diesel supplies SQLite connections, typed table mappings, queries and transactions. Storage uses the Python schema and Alembic revision IDs. Migration stays explicit. Vendored queries and migration SQL retain upstream whitespace; do not auto-trim these data assets. Both implementations share `DATABASE_PATH` and the XDG default path. Use an isolated database for comparisons; no benchmark needs the user's default database.

The runtime does not invoke Python. Developer parity tools invoke each implementation separately and compare output, exit status, schema and stored data. `tests/code_samples` and `tests/snapshots` link to the unchanged Python reference fixtures. A matching report alone is not proof of a matching graph: graph snapshots compare all fields and preserve array order.

Build and test from the repository root:

```sh
cargo build --release --locked --manifest-path atlas-rust/Cargo.toml
cargo test --locked --manifest-path atlas-rust/Cargo.toml
uv run --project atlas atlas check --f .
```

See `PARITY.md` for differential tests and benchmark commands. Benchmark evidence must identify failed comparisons and reference timeouts; a faster failed result is not a verified speedup.
