# Full-production mutation audit: verified fixes and open work

This is a partial survivor-remediation result, not an “all survivors fixed” claim.
All 1,897 selected production manifests ran at least once. There are still 664
survivors, 160 inconclusive results and five timeouts. No survivor is automatically
considered equivalent or a production bug.

## Scope and isolation

The target and merge base with `origin/main` were both
`d403b16a2b68a07a11cc22679677bb2fd00dc8a4`. The starting checkout was clean.
The scope was both projects: `atlas/src/atlas` and production `dashboard/src`.
Tests, fixtures, test-support modules and generated code were excluded. Fresh
whole-repository analysis produced 4,990 manifests; 3,093 were outside that
production scope. The production module `graph-test-path.ts` was included despite
its name. These are supported catalog edits, not every possible program mutation.

All 24 catalog rules were enabled only in disposable checkouts. The exact temporary
configuration is in `temporary-config.json`. No production mutation configuration,
README or production source changed. Atlas generated manifests without saved
indexing. Experimental edits used detached disposable Git worktrees, exact
SHA-256/base64/span validation, one byte edit at a time and verified restoration.
The user's checkout received only the intentional test changes and this report.

## Outcomes

| Project | Executed | Killed | Survived | Invalid | Inconclusive | Timeout |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Python importer | 1,536 | 625 | 657 | 90 | 160 | 4 |
| Dashboard | 361 | 272 | 7 | 81 | 0 | 1 |
| Total | 1,897 | 897 | 664 | 171 | 160 | 5 |

The selected-check score is `killed / (killed + survived)`: Python 48.8%, dashboard
97.5%, combined 57.5%. Invalid, inconclusive and timeout outcomes are excluded.
These scores describe this experiment only. Commands and test-selection methods
differ between projects; scores are not directly comparable coverage measures.

The Python pristine baseline passed 1,968 tests in 196.83 seconds. An initial
180-second baseline timed out, so it ran no mutants. The successful retry used a
600-second limit. A coverage-instrumented baseline also passed in 465.55 seconds.
Primary commands used the fastest observed covering test, or a relevant module for
uncovered sites, with passing command-specific baselines. Broader confirmation used
up to six covering tests from distinct modules. It completed 928 of 1,019 planned
checks; 91 broader confirmations did not complete before the 30-minute execution
budget. Every manifest still has a completed primary execution. Line coverage does
not prove branch or operator coverage. Twenty-six sites had no observed coverage.

Dashboard commands selected graph/component tests or storage tests by owner, then
ran new focused tests under separate passing baselines. Syntax and semantic checks
of mutated TypeScript files found 81 invalid alternatives. A production build and
full-project typecheck were not repeated for every mutation. Its 30-minute target
was exceeded by approximately four seconds to finish the final four candidates.
Individual mutation timeouts were 180 seconds; Python focused commands also used
explicit command limits and the shared wall-clock deadline. Timeouts are not kills.

## Verified fixes

Python now tests consistent candidate identities with dot-relative, parent-relative
and absolute aliases to real source files. Existing forged-path tests could fail
later identity validation even with a broken path guard. Three new cases kill two
confirmed `or` to `and` survivors in `mutations/manifests.py:56`.

Dashboard tests now cover canvas selection and actions, layout coordinates, graph
navigation, cycle projection, boundary nodes, repository forms and route states,
repository service behavior, normalized storage keys, and SQL key batches around
500 parameters. They kill 115 former survivors and one former timeout. Together,
117 confirmed survivors and one timeout now fail behavior checks. No production
behavior was changed to improve the score.

An independent review found no blockers, copied implementations, tautological
assertions, mock contamination or new file/function size violations. Three
subprocess-based kills had weak crash diagnostics. The parent added stderr to the
assertion and reran manifests 41, 45 and 47 under a new passing baseline. Their
logs show mutation-induced undefined graph-trail access in production code, not
setup or syntax failure. Original source hashes were restored afterward.

The architecture fit is compatible: tests exercise the existing manifest safety,
projection, presentation and persistence contracts without moving their owners.
No new indexing/check/report/navigation behavior was introduced. The Python change
covers mutation-generation validation, outside those snapshot-first areas.

## Open work

The 657 Python survivors need broader tests and semantic review, especially receiver
resolution and language adapters. Narrow passing commands do not prove gaps in the
entire existing suite. The 160 runtime failures remain inconclusive rather than
being counted as kills. Four Python timeouts need controlled reproduction.

Six dashboard survivors have equivalence arguments, including comparator equality
branches over distinct object keys and a guarded common-prefix loop. These remain
listed as survived. One sort-comparator alternative has bounded runtime evidence
but no general proof. The `&&` to `||` boundary-prefix loop mutant times out; it
can continue comparing two undefined entries. Browser interaction and general
comparator equivalence were not verified. No UI behavior changed.

## Final validation and evidence

The parent ran every required check from the repository root after the fixes:
Python pytest: **1,971 passed**; Pyright and Ruff passed. Dashboard production build,
**226 Bun tests**, typecheck and `bun lint --fix` passed. Fresh whole-repository
`uv run --project atlas atlas check --f .` passed. The diagnostic-only follow-up
also passed its focused baseline and restoration run. No browser smoke was run
because the changes are tests only.

`python-1.tsv` through `python-4.tsv` and `dashboard-1.tsv` contain all 1,897 IDs,
source hashes, paths, spans, edits, before/after outcomes, commands and evidence.
Python before/after columns retain command-specific experiment history; later
broader confirmations can change classifications without any test-code change.
They are not a clean global before/after score. Dashboard `originalTests` records
the original suite; focused new tests ran under their own passing baseline.
`tests` is relative to the relevant project directory. Runtime paths in `log` are
local artifact locations, not hosted links. Raw manifests and full execution logs
remain at `/tmp/atlas-python-artifacts-d403b16/` and
`/tmp/atlas-dashboard-mutations/`; Atlas does not persist these outcomes.
Representative path-guard before/after logs, diagnostic reruns and final validation
logs are included here. Full source hashes were verified restored in experiment
roots. Temporary checkouts and logs were retained for follow-up, not deleted.

## Tool assessment

I rate Atlas **8/10 for manifest generation** and **6/10 for the complete mutation
workflow**. The exact byte contract worked reliably and required no offset repairs.
It helped substantially: 117 genuine survivor checks and one former timeout now
fail, including safety tests that previously passed for the wrong reason.

The most useful improvements would be coverage-aware test selection, resumable
isolated execution, portable outcome/log export, stronger type-aware candidate
filtering, and explicit equivalence review. Atlas currently supplies manifests,
not those execution facilities. Concurrency also distorted a 15-second performance
test; the final quiet full-suite run passed. Preserve separate invalid, timeout,
inconclusive and survivor categories instead of optimizing a misleading score.
