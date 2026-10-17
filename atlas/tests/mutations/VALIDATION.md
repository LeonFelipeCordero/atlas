# Mutations package unit-test validation

This test-only layer stacks on PR #43 (`metrics-mutation-coverage-tests`).
Production code and README files are unchanged. No E2E tests were added.

`test_config_rules_report.py` checks opt-in configuration, exact catalog mappings,
and report projection. `test_manifests.py` checks identity, rule selection,
independent edit deduplication, ordering, and request-local verification caching.
`test_verification.py` checks filesystem safety, grammar-node classification,
complete candidate identity, and byte-level replacement verification.

Tests use real domain records and reusable input factories. Parser, extractor,
filesystem, and report-generation boundaries use mocks or small syntax stubs.
Assertions check values and rejection behavior, not only mock calls. Call
assertions additionally check boundary arguments, caching, and fail-before-I/O.
These tests do not establish real parser or database integration correctness.

## Final checks

Run from the repository root:

```sh
(cd atlas && uv run pytest tests/mutations -q) # 159 passed
(cd atlas && uv run pytest) # 1,774 passed
(cd atlas && uv run pyright) # passed
(cd atlas && uv run ruff check .) # passed
(cd atlas && uv run --with coverage coverage run --branch -m pytest tests/mutations -q)
(cd atlas && uv run --with coverage coverage report --include='src/atlas/mutations/*' -m)
```

The focused suite covers all 140 statements and 24 branches in `atlas.mutations`
(100% combined coverage). Coverage is temporary tooling, not a dependency change.
Dashboard build, 200 tests, typecheck, and lint pass after `bun install --no-save`.
The whole-project `uv run --project atlas atlas check --f .` exits 1 on policy
violations, including parameter counts in the new parametrized unit tests.

## Mutation evidence

`mutation_evidence.json` records exact replacements and outcomes. All 49 selected
mutations were killed against the final 159-test suite. Each mutation was applied
alone and restored in `finally`. A kill required pytest exit 1 with failed tests;
collection errors were not counted. No temporary production changes remain.
This is a hand-selected mutation set, not an exhaustive package mutation score.

Independent review found weaknesses in rule-ID identity, sort precedence and
tie-breakers, cache lifetime, and root forwarding. The first 155-test suite allowed
hardcoded rule IDs, candidate sorting by ID before language, missing output
rule-ID/ID sort keys, module-level caching, and a wrong inventory root. Tests now
exercise those distinctions. The final seven mutations reproduce these defects
and separately check the replacement sort key; all are killed.

To replay every recorded mutation, run this Python snippet from the repository
root. It edits production files temporarily; start with a clean checkout and do
not run other validation concurrently. It always restores the active mutation.

```python
import json
import subprocess
from pathlib import Path

root = Path("atlas")
command = ["uv", "run", "pytest", "tests/mutations", "-q", "--tb=short"]
subprocess.run(command, cwd=root, check=True)
evidence = json.loads((root / "tests/mutations/mutation_evidence.json").read_text())
for case in evidence["mutations"]:
    path = root / case["file"]
    original = path.read_bytes()
    text = original.decode()
    assert text.count(case["old"]) == 1, case["reason"]
    try:
        path.write_text(text.replace(case["old"], case["new"]))
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        output = result.stdout + result.stderr
        assert result.returncode == 1 and " failed" in output, (case, output)
        assert "ERROR collecting" not in output, (case, output)
    finally:
        path.write_bytes(original)
```
