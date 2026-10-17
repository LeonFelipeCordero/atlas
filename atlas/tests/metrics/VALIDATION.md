# Metrics unit-test validation

This test-only layer stacks on PR #42, `service-persistence-integration-tests`.
No production code, parser pipeline, database, or E2E tests were added.
Tests use domain records, small syntax stubs, and mocked parser or adapter boundaries.

## Final results

- Dedicated metrics suite: **942 passed**, serial and parallel.
- Full importer suite: **1,615 passed** with `pytest -n auto`.
- Python types and lint: passed.
- Dedicated suite coverage for `src/atlas/metrics`: **95%**, including branches.
  Every adapter module reaches at least 85%. This is not complete coverage.
- Dashboard build, 200 tests, types, and lint: passed after installing dependencies.
- Whole-project Atlas check: exits 1 on policy limits, including parameter counts
  and complexity in these tests. The test suite and type checks still pass.

Reproduce from the repository root:

```sh
(cd atlas && uv run pytest tests/metrics -n 4)
(cd atlas && uv run pytest -n auto)
(cd atlas && uv run pyright && uv run ruff check .)
(cd atlas && uv run --with coverage coverage run --branch -m pytest tests/metrics)
(cd atlas && uv run --with coverage coverage report --include='src/atlas/metrics/*' -m)
```

`coverage` is temporary tooling, not a project dependency.

## Mutation evidence

Final validation reran all recorded replacements against the complete, final
metrics test suite in a fresh isolated source-and-test copy. Each mutation was
applied alone and restored. The baseline passed. A kill required exit 1 and a
reported failed test; collection errors were not counted.

| Manifest | Selected mutations | Killed | Survived |
| --- | ---: | ---: | ---: |
| `core_mutations.json` | 51 | 49 | 2 |
| `resolution_mutations.json` | 70 | 70 | 0 |
| `adapter_mutations.md` | 51 | 51 | 0 |
| `review_mutations.json` | 4 | 4 | 0 |
| Total | 176 | 174 | 2 |

The two survivors are documented in `core_mutations.json`: a redundant finite
number check, and sibling traversal order under pure metric policies. The latter
is not a proof for stateful callbacks. This hand-selected set is not a package-wide
mutation score. Each manifest includes exact replacements and reproduction steps;
its earlier experiment paths and counts are historical evidence.

Independent review found four weak scenarios. Final tests now distinguish
selection from its input, use distinct dispatch targets, assert internal call
connections from enclosing callables, and keep rejected receivers separate from
unknown receivers. The four review mutations confirm those strengthened assertions.
