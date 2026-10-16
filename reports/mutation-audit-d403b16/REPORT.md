# Python production mutation audit: verified fixes and open work

This PR covers only the Python importer. Dashboard changes and dashboard audit
artifacts were removed at the user's request.

This is a partial survivor-remediation result, not an “all survivors fixed” claim.
All 1,536 selected Python production manifests ran at least once. There are still
657 survivors, 160 inconclusive results and four timeouts. No survivor is
automatically considered equivalent or a production bug.

## Scope and isolation

The target and merge base with `origin/main` were both
`d403b16a2b68a07a11cc22679677bb2fd00dc8a4`. The starting checkout was clean.
The retained scope is `atlas/src/atlas`. Tests, fixtures, test-support modules and
generated code were excluded. These are supported catalog edits, not every possible
program mutation.

All 24 catalog rules were enabled only in disposable checkouts. The exact temporary
configuration is in `temporary-config.json`. No production mutation configuration,
README or production source changed. Atlas generated manifests without saved
indexing. Experimental edits used detached disposable Git worktrees, exact
SHA-256/base64/span validation, one byte edit at a time and verified restoration.
The user's checkout received only the intentional test changes and audit evidence.

## Outcomes

| Executed | Killed | Survived | Invalid | Inconclusive | Timeout |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,536 | 625 | 657 | 90 | 160 | 4 |

The selected-check score is `killed / (killed + survived)`: **48.8%**.
Invalid, inconclusive and timeout outcomes are excluded. This score describes this
experiment only, not full-project behavioral coverage.

The pristine baseline passed 1,968 tests in 196.83 seconds. An initial 180-second
baseline timed out, so it ran no mutants. The successful retry used a 600-second
limit. A coverage-instrumented baseline also passed in 465.55 seconds.
Primary commands used the fastest observed covering test, or a relevant module for
uncovered sites, with passing command-specific baselines. Broader confirmation used
up to six covering tests from distinct modules. It completed 928 of 1,019 planned
checks; 91 broader confirmations did not complete before the 30-minute execution
budget. Every manifest still has a completed primary execution. Line coverage does
not prove branch or operator coverage. Twenty-six sites had no observed coverage.
Focused commands used explicit timeouts and the shared wall-clock deadline.
Timeouts are not kills.

## Verified fixes

The new cases test consistent candidate identities with dot-relative,
parent-relative and absolute aliases to real source files. Existing forged-path
tests could fail later identity validation even with a broken path guard. Three
new cases kill two confirmed `or` to `and` survivors in
`atlas/src/atlas/mutations/manifests.py:56`.

| Manifest | New failing case |
| --- | --- |
| `013c57b33ddf90ca2fb2b87a4a6a5c31bbab5db2de045b78b23f4426a7541421` | `parent` |
| `e12a1fa22da726d866571c4ddcd774c548f4ea51401e407a687134e42a6e1801` | `dot` |

Both mutants previously passed 85 relevant tests. After the fix, the unchanged
baseline passed 88 tests and each mutant failed with `DID NOT RAISE ValueError`.
No production behavior was changed to improve the score.

An independent review found no blockers, copied implementations, tautological
assertions or new file/function size violations. The architecture fit is
compatible: the tests exercise the existing manifest safety contract without
moving its owner. No new indexing/check/report/navigation behavior was introduced.
The change covers mutation-generation validation, outside those snapshot-first
areas.

## Open work

The 657 survivors need broader tests and semantic review, especially receiver
resolution and language adapters. Narrow passing commands do not prove gaps in the
entire existing suite. The 160 runtime failures remain inconclusive rather than
being counted as kills. Four timeouts need controlled reproduction.

## Validation and evidence

After the Python fixes, the parent full suite passed **1,971 tests**. Pyright, Ruff
and fresh whole-repository `uv run --project atlas atlas check --f .` also passed.
The retained logs record those checks. A performance test timed out under concurrent
mutation load in an earlier run; the final quiet full-suite run passed.

`python-1.tsv` through `python-4.tsv` contain all 1,536 IDs, source hashes, paths,
spans, edits, before/after outcomes, commands and evidence. Before/after columns
retain command-specific experiment history; later broader confirmations can change
classifications without any test-code change. They are not a clean global
before/after score. Commands are relative to `atlas/`. Runtime paths in `log` are
local artifact locations, not hosted links. Raw manifests and full execution logs
remain at `/tmp/atlas-python-artifacts-d403b16/`; Atlas does not persist these
outcomes. Representative path-guard before/after logs and final validation logs are
included here. Full production source hashes were verified restored in experiment
roots. Temporary checkouts and logs were retained for follow-up, not deleted.

## Tool assessment

I rate Atlas **8/10 for manifest generation** and **6/10 for the complete mutation
workflow**. The exact byte contract worked reliably and required no offset repairs.
It exposed two confirmed Python safety-test gaps: earlier tests passed for the
wrong reason, and consistent candidate identities made the missing checks visible.

The most useful improvements would be coverage-aware test selection, resumable
isolated execution, portable outcome/log export, stronger type-aware candidate
filtering, and explicit equivalence review. Atlas currently supplies manifests,
not those execution facilities. Preserve separate invalid, timeout, inconclusive
and survivor categories instead of optimizing a misleading score.
