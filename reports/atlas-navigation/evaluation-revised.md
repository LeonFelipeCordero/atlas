# Revised runs: source and session review

## Verdict

Revised Atlas used fewer tokens and less time than original Atlas, **but lost coverage**. Against earlier plain runs: 63.7% more tokens, 17.5% more estimated cost, 50% more responses, 9.2% more time. Only TS finished sooner than plain.

Same 36-checkpoint rubric: revised 29 supported / 0 wrong / 7 omitted; original Atlas 32/0/4; plain 36/0/0. A separate TS diagram error labels skipped work as completed. Zero wrong rubric checkpoints does not mean an error-free answer.

Three later follow-ups, not new matched pairs. No causal or equal-quality speedup established. This file condenses the original round-two review; no new session/source audit performed for the rewrite.

## Controls and audit

The reviewer read the original evaluation, three revised histories/prompts/answers, relevant production source, both measured skill files, and published artifacts. The original PY history was parsed only for system-section comparison. No unrelated sessions, pilot, delegation, application/tests/indexing, or database queries by the reviewer.

Source commits/clean statuses matched provenance. Shared system sections and `gpt-6.1-sol/high` matched original runs. Each revised agent read its own prompt and complete worktree skill/reference; measured text/hashes matched the preserved [skill snapshot](evidence/skill-measured/) and [provenance](provenance.json). This does not apply to later unbenchmarked clarifications.

Commands used the correct target checkout; no other answers read. Agents checked database existence and pinned the expected revision. EX's check and overview were on separate shell lines: the check succeeded, but would not have gated overview if the database were absent. No source edits, tests, workflows, migration, reindexing, or delegation. Writes targeted only each answer.

Final answers matched saved files. Word counts PY/TS/EX: 691/748/674; diagram nodes: 13/14/12. Diagrams source-reviewed, not rendered.

Independent recomputation agreed with all revised session hashes, token/cost totals, calls/responses, error IDs, result bytes, and duration in [metrics.json](metrics.json). Same definitions as original; [REPORT.md](REPORT.md#how-numbers-were-counted) explains them.

| Revised run | Tokens | Est. cost | Tools | Responses | Time | Result bytes |
|---|---:|---:|---:|---:|---:|---:|
| PY | 391,969 | $0.202744 | 33 | 19 | 201.082 s | 142,743 |
| TS | 520,842 | $0.202191 | 36 | 23 | 164.952 s | 110,122 |
| EX | 342,221 | $0.187978 | 17 | 18 | 173.005 s | 87,937 |
| Total | 1,255,032 | $0.592914 | 86 | 60 | 539.039 s | 340,802 |

Mean time: 179.680 s. Total time sums overlapping agent durations, not wall time.

| Revised relative to | Tokens | Est. cost | Tools | Responses | Time |
|---|---:|---:|---:|---:|---:|
| Original Atlas | −31.5% | −16.6% | +2.4% | −9.1% | −21.6% |
| Earlier plain | +63.7% | +17.5% | −5.5% | +50.0% | +9.2% |

## Tool use and evidence

31 graph-query attempts plus one help call inside 24 Atlas-bearing bash calls. Every agent used one depth-1/12-node/30-edge context; none used `projects`, `show`, or `children`.

Four flagged failures: PY/EX invented unsupported `find --path`; TS's rewritten `rg --files` failed, and a nonexistent directory stopped a chained grep. PY also had a real search failure hidden by `| head`. All reported in answers. TS webhook no-match was bounded evidence, not proof of global absence.

PY still combined context/source output, clipping excerpts; direct reads recovered evidence. TS source batches completed, but scheduler context still showed unresolved Map calls rather than callbacks. EX completed all fifteen batched excerpts. All visible verification statuses were `ok`; ordinary read spans matched current source.

TS and EX reread already inspected source despite the stopping rule. Reading a detail does not ensure the final answer states it—TS read RPC/subscription source but omitted key boundaries.

## Same checkpoint scoring

Full requirements/source spans: [original rubric](evaluation-original.md#scoring-rule). S = required behavior stated correctly; W = contrary/unsupported assertion; O = omitted. No partial credit for compound checkpoints. Citations alone earn nothing. Labels below are abbreviated, not new requirements.

| ID | Checkpoint / revised assessment | Score |
|---|---|:---:|
| P1 | CLI entry, folder aliases/default, resolved root. | S |
| P2 | analyze_folder→save_folder; analysis before DB; not named-project index. | S |
| P3 | Valid directory, sorted byte discovery, language catalog/exclusions, relative paths. | S |
| P4 | Git rules vs built-ins, atlasignore, outside-root exclusion. | S |
| P5 | Sequential parsing, byte hash, replacement UTF-8, syntax/native extraction, abort on exception. | S |
| P6 | Dedicated diagnostics vs generic suppression vs parser exceptions. | S |
| P7 | Callable metrics first; local indexes; import/inheritance/call resolution order. | S |
| P8 | Deduplicated unresolved/ambiguous external targets; edge evidence/confidence. | S |
| P9 | Validated v2 artifact, metadata/content, unique/reference checks. | S |
| P10 | No implicit migration; DB path, foreign keys, busy timeout. | S |
| P11 | Canonical reuse/unique name; registration+graph replacement commit; rollback. | S |
| P12 | Count DTO before commit, output after; summary-only CLI, limited exception wrapping. | S |
| T1 | Independent JSON/Croner and Ecto/Quantum runtimes. | S |
| T2 | JSON path/default, missing-file empty config, legacy defaults. | S |
| T3 | Immediate/five-second nonconcurrent polling; normalized comparison; retained config/schedules; repeated-error suppression. | S |
| T4 | Paused cron candidates; duplicate/disabled/monitor rules; validate before replacement. | S |
| T5 | Process-local overlap counts; skipped not queued; finally release; no durable lock. | S |
| T6 | Skill/pre-script/empty skip; Pi configuration; subagent restriction/daily session. | S |
| T7 | Standalone completion explained; **RPC length/error distinction, port close, no timeout omitted**. | O |
| T8 | Ecto/broadcast/polling named; **validated records and startup refresh omitted**. | O |
| T9 | **Fingerprint advances even after returned refresh error: omitted**. | O |
| T10 | Quantum runner named; **manual Task.start retry outside dispatch omitted**. | O |
| T11 | Generic monitoring/logging named; **session metadata and PubSub→UI transcript/status refresh omitted**. | O |
| T12 | **Registration-error warn/continue and preparation skip before registration omitted**. | O |
| E1 | Form/validation; UI-only gating; no positivity/repeat-turn enforcement. | S |
| E2 | Sorted locks, supplier routing, order/associations transaction, post-commit notifications. | S |
| E3 | Factory bypass; separate weekly update/close even after failed update. | S |
| E4 | Independent supervised broadcasters, 60/60/120 s, no phase barrier. | S |
| E5 | Connected views execute work; duplicates repeat; no subscribers means no handlers. | S |
| E6 | Sender-only CPU order/next-demand transaction; ignored handler result. | S |
| E7 | **Missing cpu-flag check omitted**, as in original Atlas. | O |
| E8 | Factory-only locked production/stock update; ignored result. | S |
| E9 | Manual delivery, checks/locks/transfers; receiverless CPU orders. | S |
| E10 | Generic flashes; repeat-delivery pending check; post-commit updates. | S |
| E11 | Sending-only append vs existing-entry replacement; session call/broadcast/DB refresh. | S |
| E12 | Ten orders per direction now stated; live appends uncapped. | S |

| Condition | PY S/W/O | TS S/W/O | EX S/W/O | Total | Completeness |
|---|---|---|---|---|---:|
| Original Atlas | 12/0/0 | 10/0/2 | 10/0/2 | 32/0/4 | 88.9% |
| Plain | 12/0/0 | 12/0/0 | 12/0/0 | 36/0/0 | 100% |
| Revised Atlas | 12/0/0 | 6/0/6 | 11/0/1 | 29/0/7 | 80.6% |

T8 cannot earn full credit by naming Ecto/subscription alone. Even crediting that partial summary gives only 30/36, below original Atlas. All conditions have 100% rubric precision; diagram defects are separate.

## Citation and diagram defects

PY prose agrees with source. Its chart lacks an explicit commit-failure rollback branch, though prose covers it. Discovery citation ends at 190; sorted byte-reading evidence needs `atlas/src/atlas/parsing/discovery.py:178–200`. The agent read that loop; narrow citation defect, not invented behavior.

TS chart sends “Skipped” to “Log completed.” Wrong: `worker/index.ts:12–17` logs the runner's completed/skipped result; `worker/scheduler.ts:60–68` releases counts on either result or failure. Correct shared label: “Log completed/skipped; release active count,” or separate outcome nodes. Raw chart preserved; correction noted in [REPORT.md](REPORT.md#revision-less-work-less-coverage).

TS distinguishes the two runtimes, but has no OTP diagram nodes and only a paragraph on that runtime. It omits completion/failure boundaries despite reading the source. Missing monitored-session details are put under unknowns. This is scope loss, not equivalent end-to-end coverage.

EX citations/semantics agree with source: timers broadcast, views execute, factory production differs from manual delivery, transaction notifications follow commit. Sending-only append qualifies the diagram's refresh shorthand. No substantive revised prose contradiction found; omissions and TS diagram error remain.

## Publication fixes and skill advice

The review requested disclosure of later-phase comparisons, unchanged-rubric coverage loss, the wrong skip label, and measured-vs-final provenance. PR #24's report included these; this rewrite retains them. Raw artifacts stay untouched rather than silently correcting measured answers.

Ambiguous “narrow by path” led two agents to invent `find --path`. Existing CLI accepts positional query text, e.g. `atlas graph --revision "$REVISION" find 'worker/scheduler.ts' --limit 5`; not a path filter or guaranteed unique result. Keep completion/failure coverage for every relevant runtime and distinguish completed/skipped/failed outcomes.

Those final skill clarifications were not tested by these runs. [Provenance](provenance.json) retains measured and final hashes separately; measured text remains in [evidence/skill-measured/](evidence/skill-measured/). No savings assigned to the final text. No implementation fix justified here.

## Limits and records

Unblinded, post-hoc rubric, one run per condition/project. Fresh agents were isolated from answers, but revised runs happened later on shared host/provider/caches. Phase order, load, warm caches, and sampling confound savings. Coverage loss is an observed alternative explanation. PY kept coverage but barely changed time; EX gained one checkpoint. Neither beat plain on cost/time.

Published metrics, prompts, raw answers, and provenance matched local records at review time; setup/checks were not rerun. The original evaluation was then an exact historical copy; both evaluations are now shortened. Inner prompts alone omit the outer checkout wrapper; reproduction instructions retain it in [REPORT.md](REPORT.md#evidence-and-repeat-runs).

[Metrics](metrics.json) retains revised session basenames and independently recomputed hashes. Same local session directory as the original review. PY-ATLAS was additionally parsed only for system-section comparison. Raw histories remain local. No benchmark rerun for this rewrite.
