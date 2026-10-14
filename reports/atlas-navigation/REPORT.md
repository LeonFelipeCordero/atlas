# Atlas navigation benchmark

## Result

Plain source navigation was faster and cheaper in all three original comparisons. More complete in TS/EX; tied in PY. Atlas saved seven tool calls but needed 26 more model responses. No source-accuracy advantage found.

| Three projects combined | Original Atlas | Plain | Revised Atlas |
|---|---:|---:|---:|
| Processed tokens, including cached context | 1,832,100 | 766,810 | 1,255,032 |
| Uncached input + output tokens | 196,132 | 162,138 | 172,536 |
| Cache-read tokens | 1,635,968 | 604,672 | 1,082,496 |
| Estimated cost | $0.710541 | $0.504623 | $0.592914 |
| Tool calls | 84 | 91 | 86 |
| Model responses | 66 | 40 | 60 |
| Mean investigation time | 229.218 s | 164.468 s | 179.680 s |
| Supported checkpoints, out of 36 | 32 | 36 | 29 |
| Wrong / omitted checkpoints | 0 / 4 | 0 / 0 | 0 / 7 |
| Rubric completeness | 88.9% | 100% | 80.6% |

Original Atlas vs plain: **139% more tokens, 41% more cost, 39% more time**. Revised Atlas used 31.5% fewer tokens than original Atlas, but covered less. Still 63.7% more tokens and 17.5% more cost than plain. Only revised TypeScript finished faster than plain.

**Not an equal-quality speedup.** Revised runs happened later, not in new matched pairs. One run per condition/project; results describe these runs, not general performance.

## What was tested

Nine fresh agents investigated three end-to-end flows on 2026-10-14:

| Label | Project | Question |
|---|---|---|
| PY | `atlas` — Python | Index command → discovery/parsing/resolution → SQLite commit → CLI output |
| TS | `matato-pi` — TypeScript and Elixir | Saved automation → scheduled dispatch → execution → completion/delivery |
| EX | `beer-game-elixir` — Elixir | Player order → persistence → runners/delivery → client refresh |

Each project had an original Atlas-skill agent and a plain search/read agent. Three later agents used a revised skill. Same model (`gpt-6.1-sol`, thinking `high`), question, and output contract: under 900 words, a 6–15-node flowchart, source citations, failures, and unknowns. No delegation, tests, application execution, reindexing, or source edits.

Atlas agents loaded the skill/reference and queried a prepared graph, with source fallback. Plain agents saw shared skill metadata, but never loaded the skill body or used Atlas/database. This tests skill use, not ignorance of Atlas.

An earlier six-agent pilot lacked usage histories and is excluded. Separate database setup indexed all three projects successfully, with zero reported parse errors: **22.847 s total**. Indexing, migration, startup, pilot, and review costs are excluded. First-use costs would be higher; repeated-use savings unknown.

## Why Atlas did worse here

Python: graph orientation followed by nearly the same broad source reading as plain. Both covered all twelve checkpoints.

TypeScript/Elixir: focused scheduler context showed unresolved `Map` calls, not callback execution. Source supplied the flow. Original Atlas omitted two error boundaries: failed refresh still advances the fingerprint; failed monitoring registration warns and continues unmonitored.

Elixir: both found the key boundary—timers broadcast; connected LiveViews perform CPU ordering/production. Delivery is manual. Original Atlas omitted the missing CPU-flag check and ten-order-per-direction refresh cap.

Broad queries, test-heavy contexts, clipping, and repeated source reads added output and responses. Atlas returned 43% more serialized tool content. Original Atlas made 53 CLI invocations inside 32 bash calls; none failed. Ordinary search failures affected both conditions. A no-match exit is not a broken command, and pipelines sometimes hid real failures.

## Revision: less work, less coverage

PR #24 narrowed searches/context, moved source reads earlier, limited repeated graph exploration, and added boundary checks. No Atlas implementation changed. This follow-up edits reports only; skills unchanged.

| Run | Tokens | Tools | Responses | Time | Est. cost | Supported / wrong / omitted |
|---|---:|---:|---:|---:|---:|---|
| PY original Atlas | 513,941 | 32 | 18 | 204.898 s | $0.237007 | 12 / 0 / 0 |
| PY plain | 282,834 | 27 | 13 | 156.429 s | $0.181260 | 12 / 0 / 0 |
| PY revised Atlas | 391,969 | 33 | 19 | 201.082 s | $0.202744 | 12 / 0 / 0 |
| TS original Atlas | 846,734 | 33 | 28 | 268.942 s | $0.259241 | 10 / 0 / 2 |
| TS plain | 277,913 | 37 | 15 | 179.022 s | $0.187644 | 12 / 0 / 0 |
| TS revised Atlas | 520,842 | 36 | 23 | 164.952 s | $0.202191 | 6 / 0 / 6 |
| EX original Atlas | 471,425 | 19 | 20 | 213.814 s | $0.214293 | 10 / 0 / 2 |
| EX plain | 206,063 | 27 | 12 | 157.953 s | $0.135720 | 12 / 0 / 0 |
| EX revised Atlas | 342,221 | 17 | 18 | 173.005 s | $0.187978 | 11 / 0 / 1 |

Revised vs original Atlas: cost −16.6%, tools **+2.4%**, responses −9.1%, time −21.6%. PY time barely changed (−1.9%) and tools increased. TS had the largest time reduction (−38.7%) and largest coverage loss. EX improved coverage/cost/time vs original Atlas, but remained 38.5% costlier and 9.5% slower than plain.

Python kept full coverage. Elixir added the history cap but still omitted the CPU predicate. TypeScript reduced its separate OTP runtime to a paragraph, omitting RPC completion/failure boundaries, validated records/startup refresh, failed-refresh fingerprint behavior, manual retry, monitored UI completion, and registration failure. That lost coverage can explain part of the savings.

The revised TS diagram also wrongly sends “Skipped” to “Log completed.” Correct outcomes: completed → log completed; skipped → log skipped; exception → log failure. All release the active count in `finally` (`worker/index.ts:12–17`, `worker/scheduler.ts:60–68`). The revised Python discovery citation should extend through `parsing/discovery.py:178–200`.

Raw answers remain unchanged as measurement evidence. Zero wrong *rubric checkpoints* does not mean error-free answers. The rubric was post-hoc and review unblinded.

Two revised agents invented unsupported `graph find --path`. PR #24's final skill clarification uses positional path queries, requires completion coverage per runtime, and keeps completed/skipped/failed outcomes distinct. **Those final edits were not benchmarked.** Measured skill snapshots and separate measured/final hashes remain preserved.

## How numbers were counted

Tokens: sum session `usage.totalTokens` = input + output + cache read + cache write. Repeated cached context counts; reasoning is already included in output. No cache writes recorded.

Cost: sum recorded `usage.cost.total`, not verified billing. Recorded rates: $2/M input, $10/M output, $0.10/M cache read. Original Atlas's uncached input/output was only 21.0% above plain despite 138.9% more total tokens. Revised uncached usage fell 12.0% vs original Atlas, not 31.5%; still 6.4% above plain. Most token savings were reduced repeated cache reads, not a 31.5% reduction in uncached work or evidence of fewer unique source bytes read.

Tools: persisted tool calls, including prompt/skill reads and answer writes. One bash call can run several CLI commands. Responses: persisted assistant messages, not hidden HTTP retries. Time: first user to final assistant outer timestamp. Summed agent times are not experiment wall time.

Shared host/provider, warm caches, overlapping runs, launch order, and sampling limit comparisons. Graph revision/hash checks establish source identity, not runtime behavior. No answer is a tested execution trace.

## Evidence and repeat runs

[Original evaluation](evaluation-original.md): controls, audit, and full 36-checkpoint rubric. [Revised evaluation](evaluation-revised.md): same rubric, coverage loss, and diagram/citation defects. These are shortened summaries of the original reviews, not new audits.

[Raw answers and measured skill](evidence/) remain unchanged. [Metrics](metrics.json) has all nine rows and session hashes; [prompts](prompts.json) has exact inner prompts; [provenance](provenance.json) has source commits, setup records, and skill hashes. Session histories remain local, not in Git.

To repeat, use those clean commits and a separate indexed database. Launch fresh equal-model agents with the recorded prompts and this outer wrapper:

```text
Read <arm>.prompt.txt and perform exactly that investigation. Start by cd <target checkout> for project commands. Do not inspect other benchmark artifacts. Write the requested answer and return it.
```

Keep plain agents away from the skill body/CLI/database and all agents away from prior answers. Preserve sessions, count CLI commands separately from bash calls, and score the same checkpoints. Use randomized repeated runs before generalizing.

## Not implemented

Possible later work: callback/indirect-dispatch coverage, production-vs-test scoping, and smaller output that preserves evidence without clipping. These are investigation leads, not confirmed resolver bugs. Any code fix needs production-pipeline sample snapshots first.

PR #24 recorded importer tests (1,822 passed), Pyright, Ruff, whole-project Atlas analysis, and artifact checks passing. No dashboard/UI changes; no dashboard or browser checks. Flowcharts were source-reviewed, not rendered. This report rewrite does not rerun the benchmark.
