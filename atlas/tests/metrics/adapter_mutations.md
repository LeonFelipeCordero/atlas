# Focused adapter mutation evidence

Baseline checkout: `4c9f04240885c0ef62ee9fd60736e3252bb9976c` (shared checkout; no branch switch).
Only `test_adapter_*.py`, `adapter_support.py`, and this record belong to this task.
No production source, dependencies, or parser pipelines were changed.

Baseline from repository root:

```sh
(cd atlas && uv run pytest tests/metrics/test_adapter_*.py -q)
(cd atlas && uv run pyright tests/metrics/test_adapter_*.py tests/metrics/adapter_support.py)
(cd atlas && uv run ruff check tests/metrics/test_adapter_*.py tests/metrics/adapter_support.py)
```

Previous baseline: **204 passed**. Owned type and lint checks passed.
Continuation results appear below; the original 25 mutants remain historical evidence.
Tests use domain records and small syntax stubs, not tree-sitter parsing.

## Experiment and outcomes

Reused the isolated-copy/subprocess/PYTHONPATH approach from
`/tmp/atlas-service-mutation-runner.py`; did not reuse its service-specific manifest.
Runner: `/tmp/run-adapter-mutations.py`.
Initial evidence: `/tmp/atlas-adapter-mutations-y_lfbdad/` (174 tests).
Final evidence: `/tmp/atlas-adapter-mutations-rvahgsol/` (204 tests).
Each directory contains `baseline.log`, `mutant-NN.log`, and `results.json`.
Each mutation runs alone; the isolated source is restored after each run.
Shared production files are never mutation targets.

The executable list below records exact, unique before/after replacements.
Paths are relative to `atlas/src/atlas/metrics/adapters/`.
All 25 final mutants exited **1**, with assertion failures, not collection errors.
The final isolated baseline exited **0** with **204 passed**.

| IDs | Initial outcome | Final outcome | Behavior checked |
| --- | --- | --- | --- |
| 1–2 | killed | killed | Duplicate relative files; multiple package directories |
| 3 | survived | killed | Package suffix must start at a path-segment boundary |
| 4–6 | killed | killed | Half-open import scope; nearest binding; equal-width ambiguity |
| 7–8 | killed | killed | Half-open module scope; ambiguous module identity |
| 9 | killed | killed | Python module file cannot act as a package parent |
| 10–13 | killed | killed | Type-only imports; last JS method; TS signature order and executability |
| 14–16 | killed | killed | Required arguments; duplicate named argument; uncertain type proof |
| 17–20 | killed | killed | Go grouped inputs; Java/Rust receiver exclusion; unknown Kotlin arity |
| 21–22 | killed | killed | Elixir pipeline input; private function file boundary |
| 23 | survived | killed | Reassigned Python self cannot prove bound-instance dispatch |
| 24 | survived | killed | Kotlin logical negation is not a receiver write |
| 25 | survived | killed | Rust trait implementation is not an inherent instance member |

The four initial survivors exposed genuine missing cases. Added assertions for
`src/apkg` versus `pkg`, reassigned `self`, non-mutating unary operators, and trait
implementations. No mutation was classified as equivalent. No final survivor was
observed in this selected set. This is not an exhaustive mutation score or a claim
of complete adapter coverage.

## Reproduce safely

From repository root, run the following Python block with `python`. It copies
only source and owned tests into a fresh `/tmp` directory. It uses the existing
virtual environment and rejects replacements that are no longer unique. It
prints the first failing test for each mutant and saves complete logs.

```python
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path.cwd()
work = Path(tempfile.mkdtemp(prefix="atlas-adapter-reproduce-"))
shutil.copytree(root / "atlas/src", work / "src", ignore=shutil.ignore_patterns("__pycache__"))
(work / "tests/metrics").mkdir(parents=True)
(work / "tests/__init__.py").touch()
for source in (root / "atlas/tests/metrics").glob("*.py"):
    if source.name.startswith("test_adapter_") or source.name in {"adapter_support.py", "__init__.py"}:
        shutil.copy2(source, work / "tests/metrics" / source.name)
env = {**os.environ, "PYTHONPATH": str(work / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
command = [str(root / "atlas/.venv/bin/python"), "-m", "pytest",
           *[str(p.relative_to(work)) for p in sorted((work / "tests/metrics").glob("test_adapter_*.py"))],
           "-q", "-x", "--tb=short"]

# Ordered IDs match the outcome table. Each tuple is (file, exact before, exact after).
mutations = [
    ("resolution_paths.py", "return matches if len(matches) == 1 else []", "return matches"),
    ("resolution_paths.py", "if len(directories) != 1:", "if not directories:"),
    ("resolution_paths.py", 'if parent == path or parent.endswith("/" + path)', 'if parent == path or parent.endswith(path)'),
    ("resolution.py", "binding.start <= position < binding.end", "binding.start <= position <= binding.end"),
    ("resolution.py", "width = min(b.end - b.start for b in matches)", "width = max(b.end - b.start for b in matches)"),
    ("resolution.py", "if len(matches) == 1 else Binding(name, [], False, 0, 0)", "if matches else Binding(name, [], False, 0, 0)"),
    ("module_index.py", "scope.body.start_byte <= position < scope.body.end_byte", "scope.body.start_byte <= position <= scope.body.end_byte"),
    ("module_index.py", "if len(identities) != 1:", "if not identities:"),
    ("python.py", 'if not _package_parent(index.get(".".join(parts[:length]), [])):', "if False:"),
    ("javascript.py", "[] if type_only or match[1] else ctx._members(request, match[2])", "ctx._members(request, match[2])"),
    ("javascript.py", "return [max(matches, key=lambda s: s.start_byte)]", "return [min(matches, key=lambda s: s.start_byte)]"),
    ("script_resolution.py", "s.start_byte < body.start_byte", "s.start_byte > body.start_byte"),
    ("typescript.py", '"method_signature", "function_signature", "abstract_method_signature", "property_signature"', '"function_signature", "abstract_method_signature", "property_signature"'),
    ("callable_selection.py", "return assignment.complete()", "return True"),
    ("callable_selection.py", "if index in self.assigned and not self.parameters[index].variadic:", "if False:"),
    ("callable_selection.py", "return None if _uncertain_type(context, annotation, node) else annotation", "return annotation"),
    ("go.py", 'return sum(max(1, len(child.children_by_field_name("name"))) for child in entries)', "return len(entries)"),
    ("java.py", 'frozenset({"receiver_parameter"})', "frozenset()"),
    ("kotlin.py", 'if node.type == "lambda_literal"', 'if node.type == "lambda_literal" or node.type == "function_declaration"'),
    ("rust.py", 'child.type not in {"self_parameter", "attribute_item"}', 'child.type not in {"attribute_item"}'),
    ("elixir.py", "count + 1 if pipeline else count", "count"),
    ("elixir.py", "not private or (not call.qualifier and symbol.file_path == call.file_path)", "not private or not call.qualifier"),
    ("script_python_selection.py", "return not any(_self_assignment(syntax, n, node) for n in syntax.nodes)", "return True"),
    ("kotlin.py", 'if node.type in self.receiver_updates and not any(c.type in {"++", "--"} for c in node.children):', "if False:"),
    ("rust.py", 'if not name or field(node, "trait"):', "if not name:"),
]

def run(label):
    result = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=60)
    (work / f"{label}.log").write_text(result.stdout + result.stderr)
    return result

assert run("baseline").returncode == 0
results = []
for number, (name, before, after) in enumerate(mutations, 1):
    target = work / "src/atlas/metrics/adapters" / name
    original = target.read_text()
    assert original.count(before) == 1, (name, before)
    try:
        target.write_text(original.replace(before, after))
        result = run(f"mutant-{number:02}")
        outcome = {0: "survived", 1: "killed", 2: "invalid"}.get(result.returncode, "error")
        failure = next((line for line in result.stdout.splitlines() if line.startswith("FAILED ")), "")
        results.append(dict(id=number, file=name, before=before, after=after,
                            exit=result.returncode, outcome=outcome, first_failure=failure))
        print(number, outcome, failure)
    finally:
        target.write_text(original)
(work / "results.json").write_text(json.dumps(results, indent=2))
print(work)
```

## Previous validation limits and observations

Repository checks ran from repository root:

- `(cd atlas && uv run pytest -n auto)`: 1111 passed; five collection errors
  in other shared metrics test files importing `tests.metrics.metric_core_support`.
- `(cd atlas && uv run pyright)`: one error in unowned `test_artifact.py:203`
  (`RepositoryMetadata.languages` is not a required key).
- `(cd atlas && uv run ruff check .)`: passed.
- `uv run --project atlas atlas check --f .`: reported policy violations,
  including parameter counts and syntax-stub/test complexity in owned files.
  The check was not clean. No configuration or production edits were made to suppress it.

No dashboard files changed; dashboard checks were not run. No new E2E tests,
parser integration tests, dependencies, or commits were added.

Observed but not fixed: `namespace_binding("_ 'pkg/tools'", "pkg/tools")` returns
`"_"`, not `None`, because alias matching precedes blank-import rejection. The Go
adapter has a similar alias policy. This likely blank-import defect is outside
this test-only task; the suite does not assert that result as correct behavior.

## Continuation: syntax, module mounts, bindings, and inheritance

Added **283 cases** in nine new owned files. Focused baseline: **487 passed**.
The shared syntax stub now uses identity equality and hashing, like real tree
nodes. This permits testing the real method-scope cache, not a replacement cache.
No production edits, parser pipelines, dependency-file edits, or commits.

Validation from repository root:

```sh
(cd atlas && uv run pytest tests/metrics/test_adapter_*.py -q)
(cd atlas && uv run pyright tests/metrics/test_adapter_*.py tests/metrics/adapter_support.py)
(cd atlas && uv run ruff check tests/metrics/test_adapter_*.py tests/metrics/adapter_support.py)
(cd atlas && uv run --with coverage python -m coverage run --data-file=/tmp/adapter-focused.coverage --branch --source=atlas.metrics.adapters -m pytest tests/metrics/test_adapter_*.py -q)
(cd atlas && uv run --with coverage python -m coverage report --data-file=/tmp/adapter-focused.coverage -m)
```

All focused tests, owned types, and lint pass. Coverage uses an ephemeral
`uv --with coverage` environment; it does not change project dependencies.
Report: `/tmp/adapter-focused-coverage.log`. Coverage counts statements and branches.
All adapter modules meet the requested 85% threshold in the focused run alone.

| Module | Previous metrics-run coverage | Focused continuation coverage |
| --- | ---: | ---: |
| Python | 53% | 95% |
| Elixir | 55% | 93% |
| Rust | 62% | 88% |
| JavaScript | 65% | 92% |
| Go | 64% | 96% |
| Java | 69% | 95% |
| Kotlin | 74% | 89% |
| resolution_policy | 56% | 85% |
| script_resolution | 63% | 94% |
| resolution | 69% | 100% |
| script_python_selection | 84% | 89% |
| callable_selection | 85% | 85% |
| base | 91% | 89% |
| registry / generic | 75% / 95% | 100% / 100% |
| module_index / parameters / resolution_paths / TypeScript | 100% | 100% |

Adapter-directory aggregate: **92%** (2087 statements, 580 branches).
The earlier report included other metrics tests; the focused run excludes them.
Thus the base-policy difference is not a regression claim. Coverage is not proof
of full grammar correctness, and Rust receiver-owner/qualified-impl paths and
callable-selection uncertainty branches still have uncovered code.

### New isolated mutations, IDs 26–51

Runner: `/tmp/run-adapter-continuation-mutations.py`.
Final evidence: `/tmp/atlas-adapter-continuation-wxyu_7bq/`.
Its baseline ran only the nine new files: **283 passed**, exit **0**.
Each of the **26 final mutations** exited **1** with an assertion mismatch,
not an import error, collection error, or runtime exception. The previous 25
mutations were not rerun in this continuation. Do not combine these selected
experiments into an exhaustive mutation score.

Initial evidence: `/tmp/atlas-adapter-continuation-dl_d90od/`.
Two initial experiments survived:

* ID 45 removed the plain-base regex check. The original dynamic-base scenario
  used `makeBase()` syntax but the inheritance record still said `Base`; a
  separate equality check rejected it. Corrected the record to `makeBase()` so
  syntax and record agree. The same mutant is now killed.
* The initial ID 42 changed `if pattern is None or pattern.type != "arguments":`
  to `if pattern is None:`. It survived: downstream shape checks still reject
  the guarded wildcard stub. No claim of equivalence. Replaced that experiment
  with a direct guarded-pattern decision reversal, killed by the guarded case.

The following is the exact final replacement list. Paths are relative to
`atlas/src/atlas/metrics/adapters/`; IDs follow list order starting at 26.
Every entry's final outcome is **killed**. The initial ID 42 replacement above
is not included in that final count.

```python
continuation_mutations = [
    ("python.py", 'return node.type != "assignment" or field(node, "right") is not None', 'return True'),
    ("python.py", 'if syntax.scope(node) != syntax.root:', 'if False:'),
    ("python.py", 'while scope.type in COMPREHENSIONS:', 'if scope.type in COMPREHENSIONS:'),
    ("python.py", 'if _hides_class_scope(syntax, parent, position):', 'if False:'),
    ("python.py", 'if members:\n            return alias or name, members, False', 'if False:\n            return alias or name, members, False'),
    ("go.py", 'if not any(c.type == ":=" for c in node.children) and node.parent:', 'if any(c.type == ":=" for c in node.children) and node.parent:'),
    ("go.py", 'self._package(resolver, f) == package', 'True'),
    ("java.py", 'return node.named_children[-1], node.named_children[0]', 'return node.named_children[0], node.named_children[-1]'),
    ("kotlin.py", 'return target, node', 'return target, scope'),
    ("rust.py", 'return text(\n            next((c for c in value.named_children if c.type == "string_content"), None)\n        )', 'return None'),
    ("rust.py", 'suffix = suffix[1:]\n    while suffix', 'suffix = suffix\n    while suffix'),
    ("rust.py", 'return [file for file in candidates if file.source.path not in referenced]', 'return files'),
    ("rust.py", '[attribute_dir / path for path in paths] if paths else [scope.directory / name]', '[scope.directory / name]'),
    ("rust.py", 'node.parent.start_byte if node.parent else 0', 'node.start_byte'),
    ("elixir.py", 'return fallback == "true" and owner is not None and target(owner) == "cond"', 'return fallback == "true"'),
    ("elixir.py", 'return count - defaults, count, text(field(node, "target")) == "defp"', 'return count, count, text(field(node, "target")) == "defp"'),
    ("elixir.py", 'return True  # Guarded patterns remain refutable, even guarded wildcards.', 'return False  # Guarded patterns remain refutable, even guarded wildcards.'),
    ("script_resolution.py", 'return [] if self.base_instance_write(parent, seen) else direct', 'return direct'),
    ("script_resolution.py", 'receivers |= aliases', 'return receivers | aliases'),
    ("script_resolution.py", r're.fullmatch(r"[\w$]+(?:\.[\w$]+)*", text(base))', 'True'),
    ("javascript.py", 'if target.type == "computed_property_name":\n        return True', 'if target.type == "computed_property_name":\n        return False'),
    ("javascript.py", 'return self.namespace_exports(ctx, request.file, request.path) if targets else {}', 'return {}'),
    ("resolution.py", 'if file.source.language == source.source.language', 'if True'),
    ("resolution.py", 'if adapter.require_import_node and directive is None:', 'if False:'),
    ("resolution_policy.py", 'c.type in self.static_containers\n                and "static" in text(c).split()', 'c.type in self.static_containers'),
    ("script_python_selection.py", 'descriptors |= _descriptor_aliases(imported)', 'descriptors |= set()'),
]
```

To rerun, use the safe reproduction block above, replacing `mutations` with
`continuation_mutations` and starting enumeration at 26. To verify kills come
only from new scenarios, copy/select these files instead of all adapter tests:

```python
new_cases = [
    "syntax", "python_modules", "elixir_syntax", "rust_modules", "inheritance",
    "script_members", "binding_indexes", "policy", "metrics",
]
```

The standalone `/tmp` runner copies source plus those tests and both test package
markers into a fresh directory. It checks replacement uniqueness, restores each
isolated target in `finally`, and saves `baseline.log`, `mutant-NN.log`, and
`results.json` with exact snippets, original SHA-256, exit codes and first failing
assertion names. It never writes to shared source.

### Continuation limits

An exploratory `tests/metrics` run before the final additions found **812 passed,
5 failed** in unowned `test_receiver_bindings.py` (ambiguous/future/shadowed/
reassigned/member_write scenarios). These tests use a separate support module.
No unowned files were changed and that broader run was not repeated. The 487
owned adapter tests pass together. Full-suite, dashboard, whole-project type/lint,
and atlas policy checks remain with the parent task, as requested.

