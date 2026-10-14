# Independent evaluation: Atlas navigation skill vs plain navigation

## Verdict

In these six persisted runs, **Atlas was not cheaper in tokens or estimated cost, and was not faster**. It used fewer tool calls in TypeScript/mixed-Elixir and Elixir, but more in Python: 84 vs 91 overall (−7.7%). That hides substantially more model-response roundtrips: 66 vs 40 (+65%). Source accuracy was high in both conditions. I found **no substantive incorrect source claim in either condition**; there is no demonstrated precision advantage for Atlas. Plain included four additional boundary details in the common rubric below. These are omissions, not Atlas falsehoods.

This is an unblinded, descriptive review of **n=1 per condition per project**, not evidence that either approach generally wins. The model was `gpt-6.1-sol`, thinking `high`, throughout all measured assistant responses.

| User question | Measured answer |
|---|---|
| Cheaper tokens? | No. Atlas: 1,832,100 total vs 766,810 plain (+138.9%); uncached input +20.1%, output +29.0%. Estimated cost $0.710541 vs $0.504623 (+40.8%). |
| Fewer calls? | Tool calls: modest aggregate reduction, with a Python regression. Model responses: more in every Atlas pair. There were 53 individual Atlas CLI invocations inside 32 bash calls. |
| Faster? | No. Atlas was 31.0%, 50.2%, and 35.4% slower in the PY, TS, and EX pairs. |
| More precise? | Not demonstrated. Rubric precision 100% for both; completeness 32/36 Atlas vs 36/36 plain. No substantive source contradiction found outside the rubric either. |

## Scope and controls

I read `metrics.json`, `measure.py`, `checkouts.json`, `setup.json`, all six top-level prompts and answer files, and parsed **only the six session histories named in metrics.json**. I inspected their tool-call/result summaries and relevant source-verification excerpts, then independently read current production source in `/home/leon/workspace/projects/{atlas,matato-pi,beer-game-elixir}`. I also read the original `.agents/skills/atlas-navigate/SKILL.md` and `references/commands.md`. I did not perform an arm, delegate, inspect `pilot/`, run project code/tests/indexing, or modify repository files. This report is the only evaluator-created output.

Current HEADs and clean `git status --porcelain` match `checkouts.json`:

| Project | HEAD |
|---|---|
| atlas | `d317a805197a8d4cf95415f70a2b6336598fa52d` |
| matato-pi | `0bc58465ad37c031e9a86a4e8ffbbb4b905cd0cb` |
| beer-game-elixir | `f2d01a1e691cd212188824fc0f306ac0cb025f37` |

All histories begin in the Atlas worktree, not the target project: the user message tells each arm to `cd` to its target for commands. The actual bash commands do so; source reads use the correct target checkout. All six recorded system `sections` are identical (canonical JSON SHA-256 `22837cd7b74f93373f4eb71137c9cd8ecf15c3c68fae5e651bcdfc1d0c2e5df2`). They contain the same tools, worktree instructions, and available-skill metadata. **Plain was not fully skill-naive:** it saw the atlas-navigate name/description/location in that metadata, but not its body. No plain arm read a skill file, ran the Atlas CLI, opened a graph database, or read another benchmark answer/session. Shared system instructions also mention Atlas report commands; none executed them. This is metadata exposure, not observed graph/body contamination.

All Atlas arms read both original skill files completely. Their historical read-result text matches the current original files. Each checks database existence before `projects`, then uses the intended cwd registration, constant `DATABASE_PATH`, and a consistent revision after overview:

| Arm | Project registration | Revision |
|---|---|---|
| PY-ATLAS | `bd3dc339-1396-403a-9449-003160297738` | `2341804570ab45f6ab0226e8c77fb425` |
| TS-ATLAS | `c18a2523-60ae-4b19-8e75-a23a4d85efbc` | `e5b5215ec38f4c2ba58ed01efe8f3094` |
| EX-ATLAS | `210c8d79-4d07-437a-bb48-9ed256efefaa` | `49a1a70d98cc4ba090b5de41f5a4449d` |

No session contains delegation, tests, reindexing, migration, source edits, other answer reads, or unrelated session reads. All writes/edits are to that arm's permitted answer file. Atlas CLI execution is the treatment explicitly authorized by its prompt, not execution of the investigated application workflow. Some ordinary searches list tests or find test callers; no tests execute.

The prompts share the same task/output constraints within each project. Treatment prompts necessarily add the skill/reference/database instructions; loading those is part of measured treatment overhead. All answers have citations, explicit unknowns, failure reporting, and a 6–15-node Mermaid flowchart; whitespace word counts are comfortably below 900:

| Arm | Words | Diagram nodes |
|---|---:|---:|
| PY-ATLAS | 711 | 13 |
| PY-PLAIN | 738 | 13 |
| TS-ATLAS | 696 | 13 |
| TS-PLAIN | 694 | 13 |
| EX-ATLAS | 668 | 14 |
| EX-PLAIN | 705 | 11 |

Five final assistant texts equal their persisted answer files after stripping surrounding whitespace. EX-PLAIN differs only in its opening wording and final sentence naming the output path; substantive content is identical. Scoring uses the requested top-level `.md` files.

## Independent measurement audit

I independently parsed each JSONL, selected its sole user entry and all assistant entries, summed numeric usage fields and the recorded cost components, counted each `content[type=toolCall]`, matched tool results by call ID, and subtracted outer entry timestamps (user to last assistant). All six file hashes, usage totals, costs, call counts, response counts, error flags, serialized tool-result byte counts, and elapsed times agree with `metrics.json`/the definitions in `measure.py`. I did **not** execute `measure.py`: it writes metrics and call summaries.

Measurement definitions:

```text
usage[field] = sum(assistant.message.usage[field])
toolCalls = count(assistant.content items with type == toolCall)
modelResponses = count(assistant message entries)
elapsed = final_assistant_entry.timestamp - user_entry.timestamp
cost = sum(recorded assistant usage.cost.total)
```

`totalTokens = input + output + cacheRead + cacheWrite` in every arm. `reasoning` is an output subset, **not additional tokens**; adding it again would double-count. Totals represent repeated context processing across responses, not unique source text or context-window size. Recorded cost components consistently imply $2/M uncached input, $10/M output, and $0.10/M cache-read tokens. There are no cache writes; no rate can be inferred for them. Estimated dollars use the session's recorded rates, not independently verified billing or a subscription charge.

### Tokens and estimated cost

| Arm | Input | Output | Cache read | Cache write | Total | Reasoning subset | Est. USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| PY-ATLAS | 65,370 | 6,203 | 442,368 | 0 | 513,941 | 405 | 0.2370068 |
| PY-PLAIN | 55,269 | 4,845 | 222,720 | 0 | 282,834 | 227 | 0.1812600 |
| TS-ATLAS | 54,862 | 7,104 | 784,768 | 0 | 846,734 | 452 | 0.2592408 |
| TS-PLAIN | 55,923 | 5,414 | 216,576 | 0 | 277,913 | 341 | 0.1876436 |
| EX-ATLAS | 56,565 | 6,028 | 408,832 | 0 | 471,425 | 447 | 0.2142932 |
| EX-PLAIN | 35,961 | 4,726 | 165,376 | 0 | 206,063 | 320 | 0.1357196 |
| Atlas sum | 176,797 | 19,335 | 1,635,968 | 0 | 1,832,100 | 1,304 | 0.7105408 |
| Plain sum | 147,153 | 14,985 | 604,672 | 0 | 766,810 | 888 | 0.5046232 |

Atlas cache reads were +170.6%. Cached tokens are much cheaper than uncached tokens, so the +138.9% token delta is **not** a +138.9% cost delta. TS-ATLAS even uses 1,061 fewer uncached input tokens than TS-PLAIN, but its output and repeated cached context still make it more expensive. Input plus output excluding cache is 196,132 vs 162,138 (+21.0%). Both final file writing and returning the full answer are included, as the prompts require.

### Calls, roundtrips, elapsed time

| Arm | Read | Bash | Write | Edit | Tool calls | Model responses | Seconds user→final | Serialized result bytes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PY-ATLAS | 22 | 8 | 1 | 1 | 32 | 18 | 204.898 | 172,603 |
| PY-PLAIN | 20 | 6 | 1 | 0 | 27 | 13 | 156.429 | 142,260 |
| TS-ATLAS | 12 | 20 | 1 | 0 | 33 | 28 | 268.942 | 147,709 |
| TS-PLAIN | 30 | 6 | 1 | 0 | 37 | 15 | 179.022 | 94,891 |
| EX-ATLAS | 4 | 14 | 1 | 0 | 19 | 20 | 213.814 | 107,045 |
| EX-PLAIN | 20 | 5 | 1 | 1 | 27 | 12 | 157.953 | 61,756 |
| Atlas sum | 38 | 42 | 3 | 1 | 84 | 66 | 687.654 | 427,357 |
| Plain sum | 70 | 17 | 3 | 1 | 91 | 40 | 493.404 | 298,907 |

Each tool call is an individual persisted read/bash/etc call, not a shell command or a model turn. Multiple reads can be emitted in one response. There are no parallel-wrapper tool calls to reinterpret. Model responses include the initial prompt read and final answer, as well as tool-bearing or intermediate assistant responses. These are persisted response/roundtrip proxies, not independently instrumented HTTP requests or internal provider retries. EX-ATLAS has 20 responses but 19 calls: counting calls as responses would be especially misleading.

Elapsed uses completion/persistence timestamps on the outer session entries. The assistant's inner `message.timestamp` precedes its outer entry timestamp, consistent with response-start rather than completion; using that inner timestamp would undercount the final generation. Startup before the user's entry and evaluator time are excluded. The sum of per-arm latencies is **not sequential wall time**: all six overlap. Mean latency is 229.218 seconds Atlas vs 164.468 plain (+39.4%).

| Pair | Total tokens Atlas delta | Tool calls delta | Responses delta | Latency delta | Cost delta |
|---|---:|---:|---:|---:|---:|
| PY | +81.7% | +18.5% | +38.5% | +31.0% | +30.8% |
| TS | +204.7% | −10.8% | +86.7% | +50.2% | +38.2% |
| EX | +128.8% | −29.6% | +66.7% | +35.4% | +57.9% |

### Atlas CLI invocations inside bash

I counted actual Atlas command occurrences in submitted shell strings, not merely bash calls or the word “atlas.” The calls execute their Atlas portions successfully, including Atlas commands followed by failing ordinary searches. No CLI invocation below is skipped by an earlier failing `&&` clause.

| Arm | Bash calls containing Atlas | projects | overview | find | show | context | children | source | Individual CLI invocations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PY-ATLAS | 6 | 1 | 1 | 1 | 1 | 2 | 0 | 3 | 9 |
| TS-ATLAS | 14 | 1 | 1 | 8 | 1 | 3 | 1 | 8 | 23 |
| EX-ATLAS | 12 | 1 | 1 | 7 | 1 | 2 | 1 | 8 | 21 |
| Total | 32 | 3 | 3 | 16 | 3 | 7 | 2 | 19 | 53 |

Thus “19 tools in EX-ATLAS” does not mean 19 graph queries: its 14 bash calls contain 21 Atlas invocations plus ordinary searches/listing. Plain has zero Atlas invocations. The source CLI also batches several declarations/files per invocation; invocation count is not excerpt count.

### Errors vs expected no matches

`measure.py` counts `toolResult.isError`, not semantic command failures. These are different:

| Arm | Flagged tool results | Observed interpretation |
|---|---:|---|
| PY-ATLAS | 1 | Ordinary search used absent guessed paths `atlas/src/atlas/discovery.py` and `atlas/src/atlas/graph`; exit 2. Earlier Atlas source in that compound call succeeded. |
| PY-PLAIN | 2 | `rg --files` rewritten to incompatible grep, exit 2; compound `find` rejected by RTK, exit 1. Both genuine failures, not no matches. |
| TS-ATLAS | 6 | Three clearly diagnosed ordinary failures (grep rejects `--glob`, missing `systemd`, missing `web-app/lib/mix/tasks`); one additional failed broad compound search with clipped diagnostic; two expected no-match searches (`webhook`, `worker|ExecStart`), exit 1. |
| TS-PLAIN | 1 | Flagged result is webhook no-match exit 1. Separately, initial `rg --glob ... | head` visibly fails inside the pipeline but is not flagged: `head` masks its exit status. |
| EX-ATLAS | 0 | No failed commands. Empty successful graph searches are not failures. |
| EX-PLAIN | 0 | No failed commands. |

TS-ATLAS's first failed broad search has absent `scripts`/`systemd` arguments, but the persisted 12,000-character output clips the diagnostic/exit footer; its precise failure cause cannot be reconstructed with the same confidence as the other three. I do not count six Atlas CLI failures: **none are evidenced**. Both Atlas no-match searches halt later `&&` clauses. In TS-PLAIN, `grep ... && true` does not rescue a no-match exit (the `true` is never reached). These outcomes must not all be presented as broken navigation commands.

The answers report ordinary failures honestly. TS-ATLAS summarizes no matches without enumerating every search term; TS-PLAIN correctly mentions its unflagged pipeline failure. Successful graph searches returning no nodes (`tick`, `startScheduler`, `game_live`, `player_live`, `game_runner`) are valid bounded name searches, not errors or proof of absent behavior.

### Source-read coverage and evidence portions inspected

| Arm | Distinct target files via read tool | Distinct files with visible Atlas `source.status=ok` | Union of those files |
|---|---:|---:|---:|
| PY-ATLAS | 19 | 4 | 20 |
| PY-PLAIN | 19 | 0 | 19 |
| TS-ATLAS | 8 | 14 | 22 |
| TS-PLAIN | 27 | 0 | 27 |
| EX-ATLAS | 1 | 13 | 14 |
| EX-PLAIN | 19 | 0 | 19 |

Counts exclude prompt/skill reads, deduplicate repeated reads, and exclude ordinary bash search excerpts. They are coverage indicators, **not counts of fully understood files** or a quality score. PY-ATLAS mostly duplicates plain's broad current-source reads after graph orientation; it does not save source-read work. EX gets its main source through batched verified CLI reads. Plain EX additionally inspects browser/endpoint and migrations. TS-PLAIN reads runtime configuration and storage/transcript source that TS-ATLAS does not fully inspect.

Relevant historical evidence is actually present, not just a claim that source was checked:

* PY-ATLAS: verified CLI `index_command` lines 18–34 and indexer 1–33 after the earlier context-heavy compound output clipped; later verified parser 151–200 and resolver 111–140. Ordinary full reads cover discovery, resolver, artifact, storage, models and record conversion in both arms.
* TS-ATLAS: verified worker runner 92–148, then complete index/scheduler/watcher/runner. Verified web scheduler/automations/runner, with subscription reread in a separate batch after earlier output clipping. `execution.ex` initially returns `truncated=true`, `nextStartLine=181`; the next query visibly supplies 181–262. It does paginate rather than assert completion from an incomplete receive loop.
* TS-ATLAS's final focused outgoing context for `createScheduler` contains only two `CALLS/INFERRED` edges to unresolved `Map`, with `truncated=false`. It does **not** establish Croner dispatch. The scheduler source supplies that behavior. Earlier runner neighborhoods are test-heavy and output-clipped.
* EX-ATLAS: visible complete Show 1–174, Orders 1–150 followed by 148–180 (covering the clipped tail), delivery 1–110, all three runners, schemas, template, session/store, plus ordinary application source. The verified Show excerpt explicitly contains `Orders.create_cpu_orders` in the LiveView handler and `if player.role == "factory"` for production. No edge is substituted for these runtime/message claims.
* Plain source reads cover the same important workflows directly, including shutdown/output validation and the two web execution paths in TS; no plain answer relies on a graph tool result.

All visible verification statuses are `ok`; no changed/missing/unverified-source status is observed. Hash checking validates the indexed file match at query time, not runtime behavior. Broad graph searches/contexts and RTK/tool output are sometimes truncated separately from Atlas's own `truncated` field. Serialized tool-result bytes (+43.0% Atlas) measure JSON-encoded returned content including metadata/truncation notices, not raw source bytes, all command stdout, or token usage.

## Source accuracy rubric

This rubric is common to both conditions within each project and based on checkable source checkpoints. It is **not preregistered** and the reviewer is unblinded; the counts should be read as an explicit, inspectable descriptive score, not an objective universal ranking.

Each row is one checkpoint: **S** = its affirmative behavior/important boundary is correctly stated, **W** = a substantive contrary or unsupported assertion, **O** = that checkpoint is not stated. An omission is not a false claim. Precision = S/(S+W); completeness = S/12. Several checkpoints group inseparable workflow details; the table states exactly what earns credit. Auxiliary details and diagrams are audited separately below, without inflating precision denominators by counting every noun/citation. Unknowns are not scored as falsehoods.

Paths in each table are relative to the respective current checkout. Python `P` means `atlas/src/atlas/`; TypeScript/web `W` means `web-app/lib/`; Elixir `Show`, `Template`, `Orders`, `Boards`, `Delivery` mean `lib/beer_game_web/live/board_live/show.ex`, its `show.html.heex`, and `lib/beer_game/{orders,boards,order_delivery}.ex` respectively.

### PY: Atlas indexing (12 checkpoints)

| ID | Checkable claim and current-source evidence | Atlas | Plain |
|---|---|:---:|:---:|
| P1 | Console entry is `atlas.cli:main`; Click index accepts folder aliases/default and resolves the root. `atlas/pyproject.toml:22–24`; `Pcli/commands.py:16–25`. | S | S |
| P2 | Actual route is in-memory `analyze_folder`, then service `save_folder`, not project-name `RepositoryService.index`; analysis precedes DB opening. `Pcli/commands.py:23–28`; `Pservices/repositories.py:27–29,71–94`. | S | S |
| P3 | Directory validity, sorted recognized-byte discovery, language catalog excluding C/C++, root-relative paths. `Pparsing/discovery.py:24–28,56–75,158–200`. | S | S |
| P4 | Root `.gitignore` selects Git/nested rules vs built-in exclusions; nested `.atlasignore` always applies; outside-root files are excluded. `Pparsing/discovery.py:106–155`. | S | S |
| P5 | Sequential parsing, original-byte hash, replacement UTF-8, shared syntax/native extraction; exceptions abort rather than return a partial repository. `Pparsing/parser.py:151–222`. | S | S |
| P6 | Dedicated syntax errors become diagnostics, generic fallback suppresses these; this is distinct from parser exceptions. `Pparsing/parser.py:174–200`; `Pparsing/adapters/__init__.py:7–26`. | S | S |
| P7 | Callable metrics before relationship resolution; repository-local indexes and import→inheritance→call resolution. `Pindexer.py:29–33`; `Pmetrics/callables.py:10–35`; `Pmetrics/resolver.py:111–140,271–356`. | S | S |
| P8 | Unresolved/ambiguous targets become deduplicated external nodes; edge relationship/confidence/evidence are retained. `Pmetrics/resolver.py:70–107,154–207`. | S | S |
| P9 | Validated schema-v2 artifact includes hierarchy/views/metrics/cycles/diagnostics/stats and UTC index metadata, with unique-key/reference checks. `Pmetrics/artifact.py:28–76,420–512`. | S | S |
| P10 | Service/storage composition does not migrate implicitly; SQLite path selection, foreign keys, busy timeout. `Pservices/factories.py:26–30`; `Ppersistence/database.py:18–44,68–78`. | S | S |
| P11 | Canonical-location reuse or unique new name; new registration and normalized graph replacement commit together, with rollback on exceptions. `Pservices/repositories.py:71–85`; `Ppersistence/repositories.py:107–164`; `Ppersistence/models.py:65–121`. | S | S |
| P12 | Row-count DTO built before commit, returned after commit; CLI prints only ID/schema/stats and wraps specified exceptions, not all failures. `Ppersistence/repositories.py:125–148`; `Ppersistence/graph_queries.py:31–52`; `Pcli/commands.py:28–34`. | S | S |

**Score:** Atlas 12 S / 0 W / 0 O; plain 12 / 0 / 0. Both precision and rubric completeness 100%.

Both correctly avoid equating indexing with automatic migration or persisting the entire artifact blob. Current `graph_records.py:51–178` serializes selected normalized metadata/facts, not artifact dependency views/cycle groups. Plain adds explicit output-failure-after-commit, explicit BEGIN/WAL administration, and the pre-write name/location race boundary. Atlas adds explicit `CALLS` vs `REFERENCES`, `typeOnly`, and warns that “external” does not establish third-party origin. These are supported additional emphases, not a demonstrated error/completeness gap on the common essentials.

### TS: matato-pi automation (12 checkpoints; this is a mixed TS/Elixir repository)

| ID | Checkable claim and current-source evidence | Atlas | Plain |
|---|---|:---:|:---:|
| T1 | Two distinct schedulers/config paths exist; no single persisted due-row queue is shown. Worker entry/watcher/Croner vs OTP automations/subscription/Quantum. `package.json:26`; `worker/index.ts:10–37`; `Wweb_app/automations/scheduler.ex:1–48`. | S | S |
| T2 | JSON path env/default, missing-file empty config, legacy overlap/skill defaults. `src/automationConfig.ts:9–29`. | S | S |
| T3 | Immediate + five-second nonconcurrent polling; normalized-content comparison and retained schedules/content on failed reload; repeated same error suppressed. `worker/watcher.ts:21–57`. | S | S |
| T4 | Paused 5/6-part Croner candidates, duplicate names rejected, disabled jobs omitted, enabled monitoring rejected; candidates validated before replacing old schedules. `worker/scheduler.ts:15–44,71–80`. | S | S |
| T5 | Process-local per-name active counter; overlap-disabled occurrence skipped, not queued; release in finally; no shared durable execution lock. `worker/scheduler.ts:52–68`. | S | S |
| T6 | Optional skill/pre-script, empty-output skip; configured Pi JSON print/approve execution, subagent restriction and optional daily session. `worker/runner.ts:12–49,61–147`. | S | S |
| T7 | Standalone completion requires exit/protocol/settled/final stop or length, then post-script; RPC has a different length/error boundary and closes its port, with no receive timeout. `worker/process.ts:24–84`; `worker/piOutput.ts:16–51`; `Wweb_app/execution.ex:77–94,160–193,231–261`. | S | S |
| T8 | Web CRUD persists validated Ecto records/broadcasts; subscription refreshes at startup, on changes, and one-second fingerprint poll. `Wweb_app/automations.ex:43–105,134`; `Wweb_app/automations/record.ex:20–59`; `Wweb_app/automations/subscription.ex:14–35`. | S | S |
| T9 | A returned scheduler-refresh error logs **but still advances the subscription fingerprint**, so unchanged config is not retried by subsequent polls. `Wweb_app/automations/subscription.ex:23–41`. | O | S |
| T10 | Quantum task is Runner.run with overlap setting; manual failed-run retry uses Task.start outside scheduled dispatch. `Wweb_app/automations/scheduler.ex:38–45`; `Wweb_app/automations.ex:15`; `Wweb_app_web/live/automation_run_live.ex:45–57`. | S | S |
| T11 | Monitored session file/status metadata and PubSub→UI transcript/status refresh; unmonitored returned response discarded/logged, not automatically delivered externally. `Wweb_app/automations/runner.ex:22–41,60–66`; `Wweb_app/sessions/registry.ex:55–79,130–132,314–337`; `Wweb_app_web/live/automation_run_live.ex:59–60,88–130`. | S | S |
| T12 | Returned monitoring-registration error warns and continues unmonitored; skipped preparation creates no registered run. `Wweb_app/automations/runner.ex:10–18,22–24,46–56`. | O | S |

**Score:** Atlas 10 S / 0 W / 2 O; plain 12 / 0 / 0. Precision 100% each; completeness 83.3% vs 100%.

Concrete omission evidence: Atlas says “Refresh failures are logged” but does not explain the unconditional fingerprint return after `apply`; plain explicitly does. Atlas explains optional registration/status, but not the `{:error, reason}` branch returning `nil` and continuing; plain explicitly does. The Atlas statements themselves are true, not wrong. Plain additionally reads/cites the configured Quantum timezone and actual production SQLite path; Atlas leaves timezone behavior unspecified. Both appropriately qualify lack of a webhook implementation rather than proving none could exist. I independently searched production source/config for webhook references; no corresponding implementation was found. Standalone shutdown/process-group semantics described by both are supported at `worker/index.ts:26–35` and `worker/process.ts:15–84`.

### EX: beer-game-elixir (12 checkpoints)

| ID | Checkable claim and current-source evidence | Atlas | Plain |
|---|---|:---:|:---:|
| E1 | Form create_order→LiveView reload/cast/required-field validation; UI gating is not server turn gating or positivity/one-order-per-turn enforcement. `Template:39–60`; `Show:97–101,111–138`; `lib/beer_game/game/player.ex:5–25`. | S | S |
| E2 | Board-player locks in ID order, supplier routing retailer→wholesaler→factory, pending player order + receiving/sending associations in transaction, post-commit creation notifications. `Orders:56–87,135–153`; `lib/beer_game/game/order.ex:5–17`. | S | S |
| E3 | Factory bypasses order insertion; separate weekly update/session close, with failed weekly update returning old player but still closing ordering. `Show:114–130`; `Boards:92–101`. | S | S |
| E4 | Three independent supervised GenServers broadcast: order-time/CPU every 60 seconds, production every 120 seconds; no coordinated phase barrier. `lib/beer_game/application.ex:10–30`; runners `state_runner.ex`, `order_runner.ex`, `factory_runner.ex:9–17`. | S | S |
| E5 | Connected Show views execute timer-driven work, not runner simulation; duplicate connected views can repeat it; disconnected views do not run these handlers. `Show:12–17,64–85`. | S | S |
| E6 | CPU demand creates sender-only CPU order and transactionally updates next demand; handler ignores returned error. `Show:71–75`; `Orders:91–115,168–178`. | S | S |
| E7 | CPU command handler does **not check the player's cpu flag**. `Show:71–75`; the cpu field exists at `lib/beer_game/game/player.ex:12`. | O | S |
| E8 | Factory-only handler invokes locked production, immediately adding weekly_orders to stock; return errors are ignored in the handler. `Show:78–85`; `Boards:103–117`. | S | S |
| E9 | Supplier delivery is manual/immediate, not scheduled shipment; transaction locks order, authorizes sender, checks pending/participants/stock, locks players in sorted order and updates stock/state; CPU has no receiver. `Template:107–127`; `Show:104–108`; `Delivery:7–109`. | S | S |
| E10 | Creation/delivery failures map to generic flashes; repeated delivery fails pending check; delivery broadcasts player/order changes after transaction. `Show:104–108,122–124`; `Delivery:23–33,55–56`. | S | S |
| E11 | Creation appends only matching SENDING orders; updates replace existing entries; synchronous session GenServer call broadcasts, triggering DB-backed player/order reload. `Show:23–42,140–173`; `lib/beer_game_web/live_session.ex:24–38`; `lib/beer_game/live_session_store.ex:9–30`. | S | S |
| E12 | Full session refresh takes **ten orders per direction**, not an unbounded history. `Show:159–165`. | O | S |

**Score:** Atlas 10 S / 0 W / 2 O; plain 12 / 0 / 0. Precision 100% each; completeness 83.3% vs 100%.

Concrete omission evidence: plain explicitly says the CPU handler lacks a cpu check and session reload takes ten orders per direction; Atlas does not state either detail. Atlas correctly says CPU work is “for their player,” so it does not make the contrary claim that only cpu=true players execute it. Both accurately identify the important surprising boundary: timers merely broadcast, subscribed LiveViews actually perform work. Both distinguish the live-session in-memory process boundary from database order persistence. Plain's Postgres label is supported by `lib/beer_game/repo.ex:2–4`, and its browser/session citations match `assets/js/app.js:1–14` and endpoint session/socket configuration.

### Combined accuracy and citation/diagram audit

| Condition | Supported | Wrong | Omitted | Rubric precision | Rubric completeness |
|---|---:|---:|---:|---:|---:|
| Atlas | 32 | 0 | 4 | 100% | 88.9% |
| Plain | 36 | 0 | 0 | 100% | 100% |

This does not mean either answer covers every relevant fact in its repository, nor that all 36 checkpoints have equal practical importance. Plain's extra details are modest; the central workflow, transaction and message boundaries agree. No concrete **wrong** substantive claim was found to furnish an error example; the four concrete differences above are explicitly omissions. Inventing an error to break the tie would be unjustified.

I checked citations against current declarations and historical read coverage, not merely whether paths exist. Important spans support their associated prose. EX-PLAIN's shorthand is declared clearly, though less copy/pasteable than full paths. Some spans are broad and include adjacent declarations/docstrings, but I found no material citation pointing to a contradictory/unread source for the essential claim. Broad claims of absence are confined to the inspected paths and accompanied by unknowns.

All diagrams satisfy node limits and their workflow semantics are supported by source:

* PY diagrams correctly put analysis before storage, normalized replacement/counting before commit/return, and rollback on storage failure. PY-ATLAS's J→rollback label mentions commit failure although commit is in K; K also has an exception edge, and prose locates commit correctly. This is slightly imprecise edge placement, not a claim that CLI output rolls back committed storage.
* TS diagrams keep standalone JSON/Croner and Ecto/Quantum as separate paths, and do not invent a webhook/durable due queue. Optional pre-script/monitor/error paths are compressed rather than exhaustively branched. Manual retry in Atlas's chart is supported by the UI/Task source, not a graph edge alone.
* EX diagrams show PubSub/GenServer/LiveView boundaries, production separately from browser-triggered delivery, and post-commit notifications. EX-PLAIN abbreviates the deliver_event→Show→delivery call into a direct browser-to-delivery edge, but its prose supplies the actual handler; this is acceptable grouped flowchart abstraction, not direct browser access to a transaction.

I reviewed Mermaid text/semantics; I did not execute a renderer or claim syntax/render validation. Static edges are not interpreted as timing traces in these answers. Runtime correctness, race frequency, deployment topology, library internals, cron/DST/missed-tick behavior and actual notification delivery are outside this source-accuracy score.

## Interpretation limits

All runs overlap from roughly 10:13 to 10:17. They share host resources, provider/model and common prompt prefixes, and Atlas runs share a prepared SQLite database. Cache and concurrent scheduling/provider load can affect latency and cost; these are not randomized, isolated serial trials. Paired task prompts are controlled, but ordering, warm caches, host contention and model sampling are not controlled enough for causal/general speed estimates. The recorded initial default model changes to `gpt-6.1-sol/high` before any assistant response; there is no mixed measured model usage.

TS is a **mixed TypeScript/Elixir repository** and both answers investigate its independent OTP path. It is not a pure TypeScript-language quality test. The evaluator sees arm names and mechanisms. Source checkout cleanliness/HEAD agreement supports comparison against current source; it does not establish runtime behavior or guarantee parser/resolver completeness.

Prepared setup/indexing is excluded from measured arms: setup.json records 16.300, 5.032 and 1.515 seconds (22.847 total) for the three indexes, all exit 0, with zero reported parseErrors. Those are setup records, not independently repeated or full index-build cost instrumentation. Migration, checks, pilot and orchestration startup are not charged here. Including one-off indexing would make this specific first-use comparison less favorable to Atlas; amortization across many tasks is unknown. I ignored the uninstrumented pilot entirely: no speed/accuracy evidence is inferred from it. This tests **only the original skill/reference**, not proposed revisions or alternative graph-query strategies.

The measured cost is session rate arithmetic, not a bill. Persisted tool output is sometimes clipped by RTK/the harness, preventing complete low-level error reconstruction and underrepresenting actual command stdout. No inference is made from unrelated sessions or hidden provider retries. These restrictions do not overturn the observed paired direction: Atlas is slower and more expensive in all three recorded pairs, but fewer-tool-call and accuracy conclusions require the distinctions above.

## Narrow recommendations — skill only, not implemented

Retain the original skill's read-only setup checks, exact project selection, revision/source verification and warnings about CALLS/REFERENCES, callbacks and graph absence. They help evidence hygiene; these runs do not show that removing them would preserve accuracy.

The most defensible efficiency edits to the **skill/reference text** would be:

1. Prefer concrete file/entrypoint queries and small result limits over broad `find automation/order` searches, then batch known source keys early. TS/EX spend 8/7 find invocations and receive clipped broad output; this is observed wasted orientation, not evidence for dropping verification.
2. Add an explicit bounded stopping rule for context: if one focused neighborhood is unresolved/test-heavy or omits callback dispatch, switch to current/verified source and targeted route/event/config searches. TS's scheduler context exposes only Map; repeated runner neighborhoods do not establish the callback chain. Do not enlarge whole-project graphs merely to compensate.
3. Recommend compact context summaries preserving revision, diagnostics, truncation, boundaries, relation/confidence and pertinent edges, rather than emitting huge node/evidence payloads. Keep source excerpts in separate bounded batches when a context payload could clip them. PY has to reread source after a large compound output; EX rereads Orders' clipped tail.
4. Add a small source-led boundary checklist to the existing explanation guidance: “what writes commit separately; what failed refresh records; what optional registration failure does; what dispatch predicate/list cap exists.” That targets the four omissions without adding repository-specific facts or a sprawling workflow template.
5. Clarify ordinary-search exit handling in the reference: no-match exit 1 differs from syntax/path failure; do not chain unrelated verification after an expected optional match with `&&`. When the harness visibly rewrites rg/find, use known working direct binaries/grep and report the wrapper limitation. This is a harness-specific hint, not an Atlas CLI repair.

These changes might reduce roundtrips/output waste, but no claimed savings are measured until rerunning. They are proposals only; `.agents/skills/atlas-navigate/` is unchanged.

## Deferred code-level Atlas opportunities (separate; not implemented)

The histories suggest examining callback/closure/indirect-dispatch coverage: `createScheduler` has only unresolved Map edges in the focused context even though its source contains meaningful schedule/run logic. That does not alone prove a resolver bug; anonymous-function containment or unsupported resolution may explain it. A future code investigation could distinguish these cases with project samples/snapshots.

Other candidates are smaller task-focused output/search controls (production-vs-test scoping, less verbose neighborhoods, clear visibility of callback boundaries) and output-budget-aware source/metadata presentation. Repeated test-heavy contexts and harness-clipped results motivate examining them, but this benchmark does not isolate whether CLI design, indexing, skill query selection or RTK caused each inefficiency. No code change is necessary to state this benchmark's findings, and none was made.

## Reproducibility: audited session identifiers

All session paths share `/home/leon/.pi/agent/sessions/--home-leon-.t3-worktrees-atlas-t3-58766ed7--/`. These are the only histories reviewed; independently computed hashes match metrics.json.

| Arm | Session basename | SHA-256 |
|---|---|---|
| PY-ATLAS | `2026-10-14T10-13-07-495Z_01a139e6-c527-753c-8400-69b0100fe4d2.jsonl` | `69135ab7f0a30653594f25296718ea18e4d38f9767ab9789d08708add7d4692e` |
| PY-PLAIN | `2026-10-14T10-13-11-377Z_01a139e6-d451-7362-92f7-714a467c07c6.jsonl` | `9f4db63ae1659949b8fa11a5756e7523e8276d69d858fb3259be1ebfc1b85fbc` |
| TS-ATLAS | `2026-10-14T10-13-16-609Z_01a139e6-e8c1-714f-98e0-b68c9ec5744b.jsonl` | `54da279582f1085f9770a96f2d45b6a3a8f3fb5a518572052cab63efe9fa332c` |
| TS-PLAIN | `2026-10-14T10-13-20-949Z_01a139e6-f9b5-73f0-a0be-f5053d8da70c.jsonl` | `6e67a35ea7855d07be471da2630eb06e6743ab0d8417cae5509c9d568ad8b03f` |
| EX-ATLAS | `2026-10-14T10-13-27-160Z_01a139e7-11f8-7344-a880-deb0d24c5128.jsonl` | `dc422d7981e5d2fad73f9504c987703b431b18f2c1aac96675b746f2c8ad0e4c` |
| EX-PLAIN | `2026-10-14T10-13-32-468Z_01a139e7-26b4-746d-9b8c-74a3dea448bc.jsonl` | `7787f44b3d71e7628aa365852713d266b79f64f1dc9b051548943aeb2ad9a30b` |
