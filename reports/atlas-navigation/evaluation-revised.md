# Independent review, round 2: revised Atlas navigation skill

## Verdict

The revised runs processed fewer tokens and finished sooner than the original Atlas runs, but **did not establish equivalent-coverage efficiency gains or a causal skill improvement**. Against the earlier plain runs, revised Atlas still used **63.7% more total tokens, 17.5% more estimated dollars, 50.0% more model responses and 9.2% more aggregate latency**, while using 5.5% fewer tools. Only TS finished sooner than plain.

Using the original evaluator's **unchanged 36 checkpoints**, revised answers score **29 supported / 0 wrong / 7 omitted**, versus original Atlas 32/0/4 and plain 36/0/0. PY retains 12/12; EX improves to 11/12; TS drops to 6/12 because the independent OTP runtime is compressed to a paragraph. It is correctly distinguished from the Bun worker, but much of its requested E2E coverage disappears. A separate TS diagram error routes a skipped job into a node labelled “Log completed”; this contradicts the actual logged outcome. Thus 100% *rubric* precision must not be described as an error-free answer or universal precision estimate.

This is source-accuracy review, not runtime validation. No Atlas/app code fix is warranted by these results.

## Scope, isolation and loaded treatment

I read the original `/tmp/atlas-navigation-benchmark/evaluation.md` completely and relied on its original six-run findings. I audited the three revised JSONL histories identified below, their assistant/tool entries and results, final answer files and relevant current production source; read the two edited skill files completely and their Git diff; and reviewed published REPORT/metrics/provenance/prompts/evidence. For system-section identity comparison only, I also parsed the named original PY-ATLAS history; I did not re-audit its investigation. I did not delegate, inspect unrelated sessions/pilot/secrets, open the graph database, execute Atlas/application code/tests/indexing, or change repository files. This document is my only output file.

Current target HEADs and clean statuses match provenance:

| Project | HEAD |
|---|---|
| atlas | `d317a805197a8d4cf95415f70a2b6336598fa52d` |
| matato-pi | `0bc58465ad37c031e9a86a4e8ffbbb4b905cd0cb` |
| beer-game-elixir | `f2d01a1e691cd212188824fc0f306ac0cb025f37` |

Each revised history contains one task user entry, initially requesting its own prompt file and explicitly directing commands to the correct target checkout. All bash project commands change there; source reads use that checkout. No other benchmark answer/session is read. Each agent loads only its own prompt and both worktree skill files, not the external installed copy. The persisted prompt and skill read-result text equals the complete current file text byte-for-byte. The two revised hashes match published provenance:

```text
SKILL.md     ab3cb8e3a8bb29c6caa2bc2231fb85649a1b98e22ac96a91d562016bd1cd82be
commands.md  9f7eead42584ef4dff29c326eaffc56b5a099b714b37c02a50e6010fda72a9c3
```

The original hashes in provenance also match `git show HEAD:<skill path>`. System sections are identical across the revised histories and to the original PY history; canonical JSON using sorted keys/default separators has the prior evaluator's SHA-256 `22837cd7b74f93373f4eb71137c9cd8ecf15c3c68fae5e651bcdfc1d0c2e5df2`. Skill metadata exposure remains the same control limitation. Measured assistant model/thinking remain `gpt-6.1-sol/high`.

All revised agents check existence of the supplied database before local overview, use the same `DATABASE_PATH`, and then pin the expected project revision. EX places check and overview on separate shell lines rather than gating overview on successful existence; the check actually succeeds here, so there is no observed absent-database violation, but this would not enforce the stop rule on an absent file.

| Arm | Registered project ID | Revision |
|---|---|---|
| PY | `bd3dc339-1396-403a-9449-003160297738` | `2341804570ab45f6ab0226e8c77fb425` |
| TS | `c18a2523-60ae-4b19-8e75-a23a4d85efbc` | `e5b5215ec38f4c2ba58ed01efe8f3094` |
| EX | `210c8d79-4d07-437a-bb48-9ed256efefaa` | `49a1a70d98cc4ba090b5de41f5a4449d` |

No revised history contains delegation, source edits, tests, application workflow execution, migration or reindexing. Writes/edits target only that arm's allowed answer. Final assistant answers equal their persisted files after surrounding-whitespace normalization. Word counts are PY 691, TS 748, EX 674; diagrams contain 13, 14, 12 nodes respectively. No Mermaid renderer was used or claimed.

## Independent metric recomputation

I independently summed numeric assistant usage fields and recorded `usage.cost.total`, counted toolCall content entries by tool name, collected flagged toolResult IDs, hashed the full JSONL bytes, counted serialized result-content bytes with `json.dumps(..., ensure_ascii=False)`, and subtracted first-user from last-assistant **outer** timestamps. All revised fields agree with local metrics.json, including hashes, error IDs, bytes and finish status. I did not execute `measure.py` (it scans other histories and writes outputs); I read its definitions only.

Reasoning is an output subset, not added again. Total tokens equal input + output + cacheRead + cacheWrite. Dollars are recorded-rate estimates, not bills; the observed rates remain $2/M uncached input, $10/M output, $0.10/M cache read. Cache writes are zero. Tools are individual persisted calls, not individual shell/CLI commands. Responses are persisted assistant roundtrip proxies, not hidden HTTP retries. Final file writing and returning the full answer remain included.

| Revised arm | Input | Output | Cache read | Total | Reasoning subset | Estimated USD |
|---|---:|---:|---:|---:|---:|---:|
| PY | 57,055 | 5,570 | 329,344 | 391,969 | 244 | 0.2027444 |
| TS | 43,025 | 6,905 | 470,912 | 520,842 | 1,082 | 0.2021912 |
| EX | 55,007 | 4,974 | 282,240 | 342,221 | 278 | 0.1879780 |
| Sum | 155,087 | 17,449 | 1,082,496 | 1,255,032 | 1,604 | 0.5929136 |

| Revised arm | Read | Bash | Write | Edit | Tools | Responses | Seconds | Result-content bytes | Flagged errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PY | 24 | 8 | 1 | 0 | 33 | 19 | 201.082 | 142,743 | 1 |
| TS | 21 | 13 | 1 | 1 | 36 | 23 | 164.952 | 110,122 | 2 |
| EX | 6 | 10 | 1 | 0 | 17 | 18 | 173.005 | 87,937 | 1 |
| Sum | 51 | 31 | 3 | 1 | 86 | 60 | 539.039 | 340,802 | 4 |

Mean revised latency is 179.680 seconds. Summed latencies are not experiment wall time: revised runs overlap from about 10:34 to 10:37; the original phase overlapped around 10:13–10:17.

| Revised relative to | Total tokens | Uncached input + output | Est. cost | Tools | Responses | Latency | Result bytes |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original Atlas | −31.5% | −12.0% | −16.6% | +2.4% | −9.1% | −21.6% | −20.3% |
| Earlier plain | +63.7% | +6.4% | +17.5% | −5.5% | +50.0% | +9.2% | +14.0% |

| Pair / comparator | Tokens | Cost | Tools | Responses | Latency |
|---|---:|---:|---:|---:|---:|
| PY vs original Atlas | −23.7% | −14.5% | +3.1% | +5.6% | −1.9% |
| TS vs original Atlas | −38.5% | −22.0% | +9.1% | −17.9% | −38.7% |
| EX vs original Atlas | −27.4% | −12.3% | −10.5% | −10.0% | −19.1% |
| PY vs plain | +38.6% | +11.9% | +22.2% | +46.2% | +28.5% |
| TS vs plain | +87.4% | +7.8% | −2.7% | +53.3% | −7.9% |
| EX vs plain | +66.1% | +38.5% | −37.0% | +50.0% | +9.5% |

Original totals remain 1,832,100 tokens/$0.7105408/84 tools/66 responses/687.654 seconds; plain remains 766,810/$0.5046232/91/40/493.404. The published headline original deltas agree with those numbers and the prior evaluation.

### CLI, failures and actual evidence

PY submits six graph-query invocations plus one `find --help`; TS submits fourteen queries; EX eleven. Of the 31 query attempts, two invalid `find --path` invocations fail. They occur inside 24 Atlas-bearing bash calls (including the PY help call). There are no `projects`, `show`, or `children` invocations; every agent uses one depth-1/12-node/30-edge context. These are query attempts, not source-excerpt counts.

The four flagged errors are genuine failures: PY and EX unsupported `--path` (exit 2), TS incompatible rewritten `rg --files` (exit 2), TS `ls` of nonexistent `web-app/lib/web_app/execution` (exit 2), which prevents its chained grep. PY additionally has an **unflagged** incompatible `rg --files | head` failure: `head` masks the exit status. All are reported in the relevant final answers. Do not compare flagged errors as if they counted all semantic failures, or call these expected no matches. TS's later webhook grep no-match is bounded evidence, not proof no webhook can exist elsewhere.

PY still combines context then source in one output, contrary to the revised separation guidance. The persisted source metadata reports `ok`, but its lines visibly end mid-import with an ellipsis; only one excerpt header is visible although two keys were requested. Direct current-source reads recover the necessary CLI/service evidence. TS's verified source batches visibly finish all seven requested excerpts; its focused scheduler neighborhood still exposes unresolved Map targets rather than callback semantics. It then reads current source, including the complete Elixir RPC receive loop. EX's batched sources visibly finish all fifteen excerpts, including Orders, Delivery, runners, schemas, Boards, session/store, Show, Repo and router. No non-ok verification status is observed.

For ordinary target source reads I compared persisted text with the requested current-source spans; all match (some append continuation notices). Historical evidence genuinely supports the main prose; source verification is not merely asserted. EX rereads the already directly read Show via Atlas, and TS verifies runner/watcher/config after direct reads: the stopping/no-reread rule was not followed completely. A complete investigation can still omit known details in its final answer, as TS does.

## Unchanged 36-checkpoint scoring

Definitions and grouping are **exactly those of the original evaluation**, not a new worker-only rubric: S = the checkpoint's behavior/important boundary is correctly stated; W = substantive contrary/unsupported assertion; O = not stated. No partial points. The concise labels below identify those original checkpoints; the original report remains the full definition/source-span reference. A partially summarized compound checkpoint is O when its specified important boundary is absent. Citations or having read a file do not by themselves state that boundary.

Paths below are relative to each target checkout. PY `P` = `atlas/src/atlas/`; TS `W` = `web-app/lib/`; EX Show = `lib/beer_game_web/live/board_live/show.ex`.

| ID | Same checkpoint / revised evidence assessment | Revised |
|---|---|:---:|
| P1 | Console entry, folder aliases/default and resolved root explicitly stated; pyproject:22–24, Pcli/commands.py:16–25. | S |
| P2 | analyze_folder→save_folder, not named-project index; analysis before opening DB. | S |
| P3 | Valid directory, sorted recognized byte files, catalog excluding C/C++, relative paths stated. | S |
| P4 | Root/nested Git rules vs built-ins, atlasignore and outside-root exclusion stated. | S |
| P5 | Sequential parsing, byte hash, replacement UTF-8, shared syntax/native extraction and aborting exceptions stated. | S |
| P6 | Dedicated diagnostics vs generic suppression and parser exceptions distinguished. | S |
| P7 | Callable metrics first; repository-wide indexes and imports/inheritance/calls resolution listed in order. | S |
| P8 | Deduplicated unresolved/ambiguous external nodes, retained edge evidence/confidence stated. | S |
| P9 | Validated v2 artifact, hierarchy/views/metrics/cycles/diagnostics/stats/UTC and reference checks stated. | S |
| P10 | No implicit migration, DB location, foreign keys and busy timeout stated. | S |
| P11 | Canonical reuse/unique name, registration plus replacement one commit and rollback stated. | S |
| P12 | Count DTO before commit, return/output after commit, summary-only CLI and limited exception wrapping stated. | S |
| T1 | Independent JSON/Croner and Ecto/Quantum runtimes, not one due-row queue, correctly distinguished. | S |
| T2 | JSON env/default path, missing-file empty config and legacy defaults stated. | S |
| T3 | Immediate/five-second nonconcurrent poll, normalized comparison, retained content/schedules and same-error suppression stated. | S |
| T4 | Paused 5/6-part cron candidates, duplicate/disabled/monitor rules and validate-before-replace stated. | S |
| T5 | Per-name process-local active counts, skipped-not-queued overlap, finally release and no distributed durable lock stated. | S |
| T6 | Optional skill/pre-script/empty skip, configured JSON print/approve, subagent restriction/daily sessions stated. | S |
| T7 | Standalone completion/post-script explained, **RPC length/error difference, port close and no receive timeout absent**. Wweb_app/execution.ex:77–94,160–193,231–261. | O |
| T8 | Ecto persistence/broadcasts and PubSub/one-second polling stated, but **validated CRUD records and startup refresh not actually explained**. Wweb_app/automations/record.ex:20–59; subscription.ex:14–35. Partial summary, not full checkpoint. | O |
| T9 | **Unconditional fingerprint advance after returned refresh error absent**. subscription.ex:23–41. | O |
| T10 | Quantum runner/overlap stated; **manual failed-run retry through Task.start outside scheduled dispatch absent**. automations.ex:15; Wweb_app_web/live/automation_run_live.ex:45–57. | O |
| T11 | Generic optional monitor completion and logging stated; **session file/status metadata and PubSub→UI transcript/status refresh absent**. Wweb_app/sessions/registry.ex:55–79,130–132,314–337; automation_run_live.ex:59–60,88–130. | O |
| T12 | **Returned registration error warning/continuing unmonitored and preparation skip before registration absent**. runner.ex:10–18,22–24,46–56. | O |
| E1 | Form/LiveView validation, UI-only gating, no positivity/repeat-turn enforcement stated. | S |
| E2 | Sorted player locks, supplier routing, pending order/two associations transaction and post-commit creation notifications stated. | S |
| E3 | Factory bypass, separate weekly update/close even if update returns old player stated. | S |
| E4 | Three independent supervised broadcasters, 60/60/120-second timing and no phase barrier stated. | S |
| E5 | Connected views execute timer work, duplicates can repeat and absent subscribers do none stated. | S |
| E6 | Sending-only CPU order/next-demand transaction and ignored handler results stated. | S |
| E7 | **Explicit lack of cpu-flag check absent**, as in original Atlas. Show:71–75; game/player.ex:12. General subscriber language does not earn this specific predicate checkpoint. | O |
| E8 | Factory production/locked stock addition and ignored result stated. | S |
| E9 | Manual immediate supplier delivery, authorization/pending/participant/stock checks, sorted locks/transfers and receiverless CPU orders stated. | S |
| E10 | Generic flashes, repeated-delivery pending failure and post-commit updates stated. | S |
| E11 | Matching sending-order append vs existing-entry replacement, synchronous session call/broadcast/DB refresh stated. | S |
| E12 | **Ten per direction** reload cap now explicit (also uncapped live appends). Show:159–165. | S |

| Condition | PY S/W/O | TS S/W/O | EX S/W/O | Combined S/W/O | Rubric precision | Completeness |
|---|---|---|---|---|---:|---:|
| Original Atlas (prior review) | 12/0/0 | 10/0/2 | 10/0/2 | 32/0/4 | 100% | 88.9% |
| Plain (prior review) | 12/0/0 | 12/0/0 | 12/0/0 | 36/0/0 | 100% | 100% |
| Revised | 12/0/0 | 6/0/6 | 11/0/1 | **29/0/7** | 100% | **80.6%** |

T8 is deliberately not credited merely because the paragraph names Ecto and a subscription. The original checkpoint explicitly includes validated records and startup refresh. Even a more permissive credit for that partial summary would yield only 30/36, still below original Atlas; it would not repair the central scope reduction.

### Citations, diagrams and unsupported-claim checks

The important PY claims agree with current CLI, discovery/parser, resolver and persistence source. `_save` counts before committing and catches commit failures; analysis precedes storage; post-commit CLI printing cannot roll back storage. Its diagram only shows J→rollback, not the K commit-failure branch: incomplete depiction, with correct prose, not a contrary transaction claim. The discovery citation ending at 190 should extend through 200 to support the sorted byte-reading loop; that loop was actually read. This is a narrow citation-range defect, not invented behavior.

TS prose correctly describes standalone scheduling, retained schedules, overlap counting, Pi protocol completion and agent-invoked external tools. The diagram, however, explicitly connects **H “Skipped” → L “Log completed; release active count”**. Source at worker/runner.ts:110 and worker/index.ts:12–17 returns/logs `skipped`, not `completed`; active-count release is shared but outcomes are not. Minimum correction: label the shared node “Log completed/skipped; release active count” or label separate outcomes. This is a concrete wrong outcome label audited separately, as diagrams were in the original rubric; do not hide it behind the table's zero W.

TS does not conflate runtimes: its opening and paragraph expressly call them independent alternatives. Nonetheless the graph has **zero OTP nodes**, and “downstream monitored-session persistence” is relegated to unknowns rather than investigating the registry/UI already central to the matched task. It reads complete execution.ex and subscription.ex but omits their crucial boundaries. Calling this an equivalent full E2E improvement would be premature. The broad webhook absence statement stays appropriately bounded to searched paths; it is not an unsupported global impossibility claim.

EX's key source/citations agree: Show has no turn/cpu predicate; Orders transactions lock/create associations; Boards keeps the old player on failed weekly update; Delivery authorizes and commits before PubSub. The diagram's order_created→refresh compression is explicitly qualified as sending-only append, rather than falsely claiming a full reload. Factory stock addition is separated from manual order delivery. Browser/timer/concurrent-tab effects are described as source-derived possibilities with runtime unknowns, not measured occurrences. The new ten-order cap is correct. No substantive prose contradiction was found in revised answers; this does not excuse omissions or the TS diagram error.

## Published report and reproducibility consistency

`reports/atlas-navigation/metrics.json` equals the local nine-row metrics exactly except intentional session-basename redaction. Published prompts equal all nine local prompt-file bodies; all nine published evidence maps equal the local files byte-for-byte. `evaluation-original.md` equals the prior evaluator file byte-for-byte. Provenance checkout/setup records and original/revised skill hashes agree with the inspected records/source; I did not independently rerun setup or checks.

Outside the deliberately pending revised paragraph, REPORT's original numbers, mixed-language description, setup exclusion, rate arithmetic, original source scores and limitations are consistent with the prior review. I found no other material factual contradiction. The original evaluator's recommendations marked “not implemented” are correctly explained as a historical snapshot, not misrepresented as current status. Claims about uninstrumented pilot/preparation/check executions remain previously recorded claims, not newly verified runtime observations in this review.

Must fix when publishing revised results: state that these are **three later follow-ups against earlier comparators**, not three new contemporaneous matched pairs; publish the unchanged-rubric score and missing OTP coverage alongside efficiency numbers; distinguish the diagram error from rubric precision; replace the pending paragraph without asserting causality or equal-quality wins. After adding any clarification, distinguish its new hash from the **benchmarked** hashes above. Updating provenance to a final unbenchmarked hash without retaining the measured version would break the treatment record.

A smaller reproducibility issue: prompt-file text says the registration folder “is your cwd”, while persisted sessions start in the Atlas worktree. The outer user wrapper supplies the required `cd`, as REPORT explains. Published prompts alone omit that outer wrapper; include/restate it in reproduction instructions rather than treating prompt-file bodies as the complete task messages.

## Minimal skill advice; no code fix

The edited instruction “narrow broad matches by path” is ambiguous. Two independent revised agents translated it into the nonexistent `graph find --path`. Current `atlas/src/atlas/cli/graph.py:61–66` defines only positional QUERY and `--limit` for find. Clarify the existing sentence/reference with one valid example:

```sh
atlas graph --revision "$REVISION" find 'worker/scheduler.ts' --limit 5
```

Suggested text: **“To search a path, put its concrete text in positional QUERY; `find` has no `--path` filter. For a specific symbol use its concrete name and inspect returned paths; do not assume name+path filtering.”** This addresses the observed misuse without adding CLI functionality. A path-text find can also return declarations in that file and be truncated; it is not guaranteed to select exactly one file.

Keep the instruction to separate alternative implementations, but add at most a short stopping-rule qualifier: **“Cover each relevant independent runtime through completion/failure; do not shorten one to an existence note.”** The existing boundary checklist already addresses fingerprints, optional failures and predicates; a sprawling repository-specific checklist is unnecessary. The skip-label defect can be addressed by retaining completed/skipped/failed distinctions in diagrams, not by modifying application code.

These are recommendations only. Neither the proposed clarification nor any subsequent final skill text has been benchmarked by these three sessions. A textual clarification may plausibly prevent wasted usage errors; no measured savings can be assigned to it.

## Interpretation limits and must-fix summary

This remains unblinded n=1 per condition/project with a post-hoc descriptive rubric, not a causal experiment. Revised agents were fresh and isolated from earlier answers, but phase order, shared prompt/provider caches, warm filesystem/database caches, host/provider load and sampling are uncontrolled. Lower recorded cache reads do not prove cold caches or identify which change caused the difference. Setup/indexing remains excluded; amortization is unknown.

Coverage loss is an actual competing explanation for TS improvements, not merely a hypothetical objection. PY preserves rubric coverage but hardly changes latency and adds calls; EX adds one checkpoint while reducing cost/time versus original, which is encouraging descriptive evidence, not causal proof. Neither PY nor EX is cheaper/faster than plain. Do not divide cost by supported checkpoints to manufacture an adjusted winner: these grouped details are not equal-value interchangeable tasks.

Before publication, the necessary corrections are the revised comparison/coverage disclosure, TS skip-outcome label, and clear measured-versus-final skill provenance. The path-query clarification is the minimal skill repair to recommend. All Atlas implementation changes remain deferred.

## Audited revised session identifiers

These are the three histories fully audited during this review. The original PY-ATLAS history named in the prior evaluation was additionally parsed only to compare system sections:

| Arm | Absolute session path | Recomputed SHA-256 |
|---|---|---|
| PY-REVISED | `/home/leon/.pi/agent/sessions/--home-leon-.t3-worktrees-atlas-t3-58766ed7--/2026-10-14T10-34-12-631Z_01a139fa-1317-7492-a5dc-97010ba27755.jsonl` | `383c3fb73d19689018d68a222abe09164627d82fde2351adad51dcb73be8e5a6` |
| TS-REVISED | `/home/leon/.pi/agent/sessions/--home-leon-.t3-worktrees-atlas-t3-58766ed7--/2026-10-14T10-34-18-525Z_01a139fa-2a1c-778d-89bd-1263fc85df04.jsonl` | `a384716bcbf7d2c9e432509e0a21e4936998f60ca5149c14871e3c44e79d9a6e` |
| EX-REVISED | `/home/leon/.pi/agent/sessions/--home-leon-.t3-worktrees-atlas-t3-58766ed7--/2026-10-14T10-34-23-033Z_01a139fa-3bb8-70f3-9a62-418de09c07f4.jsonl` | `4af5f06dab28c04f971efd3593968e08f557ff2faf5b1c50a3e8400945ddc6f3` |
