# Original runs: source and session review

## Verdict

Plain won cost and time in all three pairs. Atlas used 84 tools vs 91, but 66 model responses vs 40. No substantive source contradiction found in either condition. Plain stated four boundary details Atlas omitted.

| Combined | Atlas | Plain |
|---|---:|---:|
| Tokens, including cached context | 1,832,100 | 766,810 |
| Estimated cost | $0.710541 | $0.504623 |
| Mean time | 229.218 s | 164.468 s |
| Supported / wrong / omitted checkpoints | 32 / 0 / 4 | 36 / 0 / 0 |
| Rubric completeness | 88.9% | 100% |

One run per condition/project, unblinded review, post-hoc rubric. No general winner established. This file condenses the original review; no new session/source audit performed for the rewrite.

## Controls checked

The original reviewer inspected six named JSONL histories, prompts, answers, metric/setup records, original skill files, and production source. Clean source commits matched the records in [provenance.json](provenance.json). No pilot or unrelated sessions inspected; no applications/tests/indexing run by the reviewer.

All measured responses used `gpt-6.1-sol/high`. Shared system sections matched. Plain agents saw skill metadata but never loaded the body, queried Atlas, opened its database, or read other answers. Atlas agents loaded both skill files, checked database existence, selected the correct project, and pinned its revision. Project commands used the target checkout despite sessions starting in the Atlas worktree.

No delegation, source edits, tests, migration, or reindexing found in the histories. Writes targeted only each agent's answer. All answers met the word/node limits and included citations, failures, and unknowns. EX-PLAIN's returned answer differed only in opening wording and output-path sentence; scoring used its saved file.

## Measurement audit

Independent session parsing agreed with every published hash, usage total, cost, call/response count, error flag, result-byte count, and duration in [metrics.json](metrics.json).

Tokens sum input + output + cache read + cache write. Reasoning is already in output; repeated cached context counts again. Cost uses recorded rates, not bills. Tools count persisted calls; responses count assistant entries, not hidden retries. Duration uses outer user/final timestamps. Setup and startup excluded; overlapping agent durations are not wall time. Definitions and rates: [REPORT.md](REPORT.md#how-numbers-were-counted).

| Pair | Atlas token increase | Cost increase | Tool change | Response increase | Time increase |
|---|---:|---:|---:|---:|---:|
| PY | 81.7% | 30.8% | +18.5% | 38.5% | 31.0% |
| TS | 204.7% | 38.2% | −10.8% | 86.7% | 50.2% |
| EX | 128.8% | 57.9% | −29.6% | 66.7% | 35.4% |

Atlas made 53 CLI invocations in 32 bash calls; none failed. Returned serialized tool content: 427,357 bytes Atlas vs 298,907 plain (+43%). Not raw source size or tokens.

| Run | Flagged tool results | Actual issue |
|---|---:|---|
| PY Atlas | 1 | Ordinary search guessed absent paths; earlier Atlas source succeeded. |
| PY plain | 2 | Rewritten `rg --files` and rejected compound `find`. |
| TS Atlas | 6 | Four ordinary failures, one with clipped diagnostics; two expected no-match exits. |
| TS plain | 1 | Webhook no-match; another genuine search failure hidden by a pipeline. |
| EX Atlas / plain | 0 / 0 | No failures. Empty graph searches are not errors. |

Source evidence was present, not merely asserted. Python read broad source after graph orientation, often duplicating plain's work. TS paginated its RPC source; focused scheduler context exposed unresolved `Map` targets, so source—not graph edges—established dispatch. EX used batched verified source and recovered a clipped tail. All visible source verification statuses were `ok`.

Large outputs sometimes clipped source independently of Atlas's `truncated` flag. File-read counts indicate exposure, not understanding. Verification establishes indexed/current source identity, not execution.

## Scoring rule

Same twelve checkpoints per project for both conditions. S = required behavior/boundary stated correctly; W = substantive contrary/unsupported claim; O = not stated. Omission is not falsehood. Compound checkpoints require their listed boundaries; reading/citing a file alone earns no credit. Precision = S/(S+W); completeness = S/12. Auxiliary claims and diagrams reviewed separately.

The tables retain the original checkpoint requirements and source spans in shorter wording. Paths are relative to each target checkout. PY `P` = `atlas/src/atlas/`; TS `W` = `web-app/lib/`. EX `Show` = `lib/beer_game_web/live/board_live/show.ex`, `Template` = its `show.html.heex`; `Orders`, `Boards`, `Delivery` = `lib/beer_game/{orders,boards,order_delivery}.ex`.

### PY: indexing

| ID | Required behavior and source | Atlas | Plain |
|---|---|:---:|:---:|
| P1 | `atlas.cli:main`; folder aliases/default; resolved root. `atlas/pyproject.toml:22–24`; `Pcli/commands.py:16–25`. | S | S |
| P2 | `analyze_folder` then `save_folder`, not named-project `RepositoryService.index`; analysis before DB opening. `Pcli/commands.py:23–28`; `Pservices/repositories.py:27–29,71–94`. | S | S |
| P3 | Valid directory; sorted recognized-byte discovery; language catalog excludes C/C++; root-relative paths. `Pparsing/discovery.py:24–28,56–75,158–200`. | S | S |
| P4 | Root `.gitignore` selects Git/nested rules vs built-ins; nested `.atlasignore` always applies; outside-root files excluded. `Pparsing/discovery.py:106–155`. | S | S |
| P5 | Sequential parsing, original-byte hash, replacement UTF-8, shared syntax/native extraction; exceptions abort, not partial success. `Pparsing/parser.py:151–222`. | S | S |
| P6 | Dedicated syntax errors produce diagnostics; generic fallback suppresses them; distinct from parser exceptions. `Pparsing/parser.py:174–200`; `Pparsing/adapters/__init__.py:7–26`. | S | S |
| P7 | Callable metrics before relationships; repository-local indexes; import→inheritance→call resolution. `Pindexer.py:29–33`; `Pmetrics/callables.py:10–35`; `Pmetrics/resolver.py:111–140,271–356`. | S | S |
| P8 | Unresolved/ambiguous targets become deduplicated external nodes; relationship/confidence/evidence retained. `Pmetrics/resolver.py:70–107,154–207`. | S | S |
| P9 | Validated schema-v2 artifact: hierarchy/views/metrics/cycles/diagnostics/stats/UTC metadata; unique-key/reference checks. `Pmetrics/artifact.py:28–76,420–512`. | S | S |
| P10 | No implicit migration; SQLite path selection, foreign keys, busy timeout. `Pservices/factories.py:26–30`; `Ppersistence/database.py:18–44,68–78`. | S | S |
| P11 | Canonical-location reuse or unique new name; registration and normalized graph replacement commit together; exception rollback. `Pservices/repositories.py:71–85`; `Ppersistence/repositories.py:107–164`; `Ppersistence/models.py:65–121`. | S | S |
| P12 | Count DTO before commit, return after commit; CLI prints ID/schema/stats and wraps only specified exceptions. `Ppersistence/repositories.py:125–148`; `Ppersistence/graph_queries.py:31–52`; `Pcli/commands.py:28–34`. | S | S |

Both 12/12. Neither confused indexing with migration or storing the full artifact blob. Plain emphasized post-commit output failure/name races; Atlas emphasized relationship/confidence distinctions. No common-rubric gap.

### TS: automation, including the independent Elixir runtime

| ID | Required behavior and source | Atlas | Plain |
|---|---|:---:|:---:|
| T1 | Separate JSON/watcher/Croner and Ecto/subscription/Quantum paths; no single persisted due-row queue. `package.json:26`; `worker/index.ts:10–37`; `Wweb_app/automations/scheduler.ex:1–48`. | S | S |
| T2 | JSON env/default path, missing-file empty config, legacy overlap/skill defaults. `src/automationConfig.ts:9–29`. | S | S |
| T3 | Immediate/five-second nonconcurrent poll; normalized comparison; old schedules/content retained on reload failure; repeated error suppressed. `worker/watcher.ts:21–57`. | S | S |
| T4 | Paused 5/6-part Croner candidates; duplicate names rejected, disabled omitted, enabled monitoring rejected; validate before replacing schedules. `worker/scheduler.ts:15–44,71–80`. | S | S |
| T5 | Per-name process-local active count; overlap-disabled occurrence skipped, not queued; finally release; no shared durable lock. `worker/scheduler.ts:52–68`. | S | S |
| T6 | Optional skill/pre-script, empty-output skip; Pi JSON print/approve; subagent restriction and optional daily session. `worker/runner.ts:12–49,61–147`. | S | S |
| T7 | Standalone exit/protocol/settled/stop-or-length completion then post-script; RPC differs on length/errors, closes port, has no receive timeout. `worker/process.ts:24–84`; `worker/piOutput.ts:16–51`; `Wweb_app/execution.ex:77–94,160–193,231–261`. | S | S |
| T8 | Validated Ecto CRUD/broadcasts; subscription refresh at startup, changes, one-second fingerprint poll. `Wweb_app/automations.ex:43–105,134`; `record.ex:20–59`; `subscription.ex:14–35` (both under `Wweb_app/automations/`). | S | S |
| T9 | Returned refresh error logs but advances fingerprint; unchanged config not retried by later polls. `Wweb_app/automations/subscription.ex:23–41`. | O | S |
| T10 | Quantum Runner.run/overlap; manual failed-run retry via Task.start outside scheduled dispatch. `Wweb_app/automations/scheduler.ex:38–45`; `Wweb_app/automations.ex:15`; `Wweb_app_web/live/automation_run_live.ex:45–57`. | S | S |
| T11 | Monitored session file/status metadata, PubSub→UI transcript/status refresh; unmonitored response discarded/logged, not externally delivered. `Wweb_app/automations/runner.ex:22–41,60–66`; `Wweb_app/sessions/registry.ex:55–79,130–132,314–337`; `Wweb_app_web/live/automation_run_live.ex:59–60,88–130`. | S | S |
| T12 | Registration error warns and continues unmonitored; preparation skip creates no registered run. `Wweb_app/automations/runner.ex:10–18,22–24,46–56`. | O | S |

Atlas 10/12; plain 12/12. “Refresh failures are logged” misses fingerprint advancement. Optional registration/status misses warn-and-continue. Neither statement is false. Both bounded webhook absence to inspected source; no implementation found there.

### EX: orders and delivery

| ID | Required behavior and source | Atlas | Plain |
|---|---|:---:|:---:|
| E1 | Form→LiveView reload/cast/required validation; UI gating is not server turn, positivity, or one-order-per-turn enforcement. `Template:39–60`; `Show:97–101,111–138`; `lib/beer_game/game/player.ex:5–25`. | S | S |
| E2 | Player locks in ID order; retailer→wholesaler→factory routing; pending order/receiving+sending associations in transaction; post-commit notifications. `Orders:56–87,135–153`; `lib/beer_game/game/order.ex:5–17`. | S | S |
| E3 | Factory skips insertion; separate weekly update/session close; failed update returns old player but still closes ordering. `Show:114–130`; `Boards:92–101`. | S | S |
| E4 | Three independent supervised GenServers broadcast; order/CPU every 60 s, production every 120 s; no phase barrier. `lib/beer_game/application.ex:10–30`; `lib/beer_game/{state_runner,order_runner,factory_runner}.ex:9–17`. | S | S |
| E5 | Connected Show views perform timer work, not runners; duplicate views can repeat it; disconnected views lack handlers. `Show:12–17,64–85`. | S | S |
| E6 | Sender-only CPU order and next-demand update in transaction; handler ignores returned errors. `Show:71–75`; `Orders:91–115,168–178`. | S | S |
| E7 | CPU handler does not check player's cpu flag. `Show:71–75`; `lib/beer_game/game/player.ex:12`. | O | S |
| E8 | Factory-only handler invokes locked production, immediately adds weekly_orders to stock, ignores returned errors. `Show:78–85`; `Boards:103–117`. | S | S |
| E9 | Manual/immediate delivery; locks order, authorizes sender, checks pending/participants/stock, locks players in sorted order, updates stock/state; CPU has no receiver. `Template:107–127`; `Show:104–108`; `Delivery:7–109`. | S | S |
| E10 | Generic flashes on create/deliver failure; repeat delivery fails pending check; post-transaction broadcasts. `Show:104–108,122–124`; `Delivery:23–33,55–56`. | S | S |
| E11 | Only matching SENDING creations append; updates replace existing entries; synchronous session call broadcasts and triggers DB-backed reload. `Show:23–42,140–173`; `lib/beer_game_web/live_session.ex:24–38`; `lib/beer_game/live_session_store.ex:9–30`. | S | S |
| E12 | Full session refresh takes ten orders per direction. `Show:159–165`. | O | S |

Atlas 10/12; plain 12/12. Both correctly found the surprising boundary: timers only broadcast; subscribed LiveViews execute work. Atlas omitted CPU predicate/history cap, not contradicted them.

## Citation and diagram review

Essential citations supported the prose. All original diagrams met node limits and source semantics; text reviewed, not rendered. Python's rollback edge placement was slightly imprecise, but prose located commit correctly. TS kept the two runtimes separate. EX compressed browser→handler→delivery into a grouped edge, with the handler explained in prose. No static edge treated as an execution trace.

Rubric precision was 100% for both. This does not prove every claim correct, every behavior covered, or all checkpoints equally important. Runtime races, deployment, cron/DST, and actual delivery were not tested.

## Recommendations at the time

Narrow queries; small focused contexts; read source early; stop graph exploration when callbacks/tests obscure the boundary. Separate graph output from source batches to avoid clipping. Check separate commits, state after errors, optional failures, dispatch predicates, and history caps. Distinguish no-match exits from broken searches; keep source/revision verification.

These were proposals when this review was written. PR #24 later revised the skill and ran follow-ups: [revised evaluation](evaluation-revised.md). No implementation changes recommended on this evidence alone. Callback coverage, scoping, and compact output remain investigation leads, not confirmed bugs.

## Limits and records

Shared host/provider/caches, concurrent runs, fixed launch order, model sampling, and setup exclusion limit cost/time conclusions. TS includes Elixir; not a pure TypeScript parser test. Setup took 22.847 s with no reported parse errors; including it worsens first-use Atlas costs. Amortization unknown.

[Metrics](metrics.json) retains exact rows, six original session basenames, and independently matched SHA-256 hashes. Histories share `/home/leon/.pi/agent/sessions/--home-leon-.t3-worktrees-atlas-t3-58766ed7--/` and remain local. [Prompts](prompts.json), [provenance](provenance.json), and [raw answers](evidence/) retain the audit inputs.
