# Verified parity and CLI timings

These results use source commit `0ca66c3f15938de526e42a01273cd2f197ad6f9b` and frozen release executables. The original Python importer, dashboard, samples, and snapshots remain unchanged. See [PARITY.md](PARITY.md) for comparison rules and [DESIGN.md](DESIGN.md) for architecture and limits.

## Validation

| Check | Result |
|---|---:|
| Native tests | 382 passed |
| Original golden files covered by native tests | 73 / 73 |
| Full nine-language CLI matrix | 3,762 / 3,762 |
| Comparable local projects | 455 / 455, across 13 projects |
| VU readers against native-produced data | 14 / 14 |
| Python importer tests | 1,774 passed |
| Dashboard tests | 200 passed |
| Harness self-tests | 13 passed |

Rust formatting and Clippy with `-D warnings` pass. Python types/lint, dashboard build/types/lint, and harness types/lint pass. Python Atlas reports no findings for the whole repository. A fresh independent review found no blocking issues; its 12-file fixture also matched index output, complete schema/data, report, check, and mutations.

The full sample matrix includes 2,070 generic cases, 1,197 interoperability cases, 189 canonical navigation cases, and 306 configuration/stale-source variants. Invalid-input cases compare real errors and exit codes. No timeout or absent output counts as a pass.

| Sample language | Passed comparisons |
|---|---:|
| Java | 426 |
| Kotlin | 426 |
| Go | 424 |
| Rust | 420 |
| Elixir | 420 |
| Python | 418 |
| JavaScript | 426 |
| TypeScript | 426 |
| TSX | 376 |

## Method

The machine ran Linux x86-64 on an Intel Core i7-11800H with 16 logical CPUs. Python was 3.11.16; SQLite was 3.53.1; Rust was 1.98.1. Both implementations used language-pack 1.20.0. [Metadata](benchmarks/metadata.json) records package/compiler versions, source revision, executable hashes, and lockfile hashes.

All times measure complete CLI wall time, including startup. The Python command includes the small developer-only parity wrapper. Timings exclude prerequisite indexing, database cloning, and schema inspection. Rust executes first in each pair. Each process uses isolated temporary database paths; no benchmark changes user projects or their databases.

The full matrix and local-project runs use zero warmups and one measured repetition. Three sample groups and two project groups run concurrently; other validation jobs share the machine. The core table uses one warmup and three measured repetitions. These are workflow measurements, not isolated parser or CPU benchmarks. Small differences need more runs on a quiet machine.

CSV files in [benchmarks/](benchmarks/) contain every case's status, sample count, median/min/max milliseconds, and Python/Rust ratio. A ratio above 1 means Rust was faster. Failed or blocked comparisons have no speedup ratio. The CSV files contain statistics only, not project source, source output, database payloads, or absolute home paths.

## Every CLI action: Python coffee sample

Median milliseconds, three measured repetitions after one warmup. Each repeated case also passes strict parity. These numbers include startup; the large graph-reader ratios are not parser-only speedups.

| Action | Python ms | Rust ms | Ratio |
|---|---:|---:|---:|
| index | 1,413.27 | 356.03 | 3.97× |
| projects | 642.68 | 2.92 | 219.91× |
| report, fresh JSON | 1,296.18 | 329.33 | 3.94× |
| check, fresh JSON | 1,349.91 | 333.37 | 4.05× |
| mutations, folder | 1,330.94 | 355.29 | 3.75× |
| mutations, saved | 786.69 | 81.46 | 9.66× |
| mutations, rules | 689.92 | 2.27 | 303.75× |
| migrate, fresh | 568.50 | 3.67 | 154.84× |
| migrate, repeat | 515.76 | 1.99 | 259.50× |
| graph overview | 612.17 | 4.01 | 152.51× |
| graph find | 638.79 | 3.41 | 187.48× |
| graph show | 654.61 | 3.93 | 166.74× |
| graph children | 642.60 | 3.44 | 186.99× |
| graph context | 621.24 | 4.17 | 149.15× |
| graph path | 634.47 | 4.21 | 150.53× |
| graph source, JSON | 640.76 | 3.46 | 184.93× |
| graph source, text | 629.90 | 3.67 | 171.50× |

[Core CSV](benchmarks/core-python.csv) also includes the same readers against native-produced data. The nine `sample-*.csv` files cover every flag combination, output format, help/error case, and selected variant in the matrix, not just this table.

## Local projects

All 14 local projects were attempted: 1,771 discovered files and 29 observed languages. [Inventory CSV](benchmarks/inventory.csv) records each project's language/file counts. Thirteen projects complete all 35 selected comparisons each: 21 core cases plus 14 readers against native-produced data. These cases cover every CLI action, explicit migrations, saved mutations, source JSON/text, project selection, and valid/stale revisions. The full sample matrix covers the remaining flag and format combinations.

The table shows fresh JSON report times in seconds, one repetition. Each project's CSV includes all selected actions and both database origins. `data` has no discovered source files, so its result measures startup and empty-project handling.

| Project | Files | Languages | Python s | Rust s | Ratio |
|---|---:|---:|---:|---:|---:|
| agent-habitat | 27 | 5 | 1.009 | 0.274 | 3.69× |
| atlas | 194 | 6 | 8.158 | 5.535 | 1.47× |
| beer-game-elixir | 98 | 10 | 1.656 | 0.632 | 2.62× |
| data | 0 | 0 | 0.555 | 0.002 | 279.26× |
| doc-gen | 247 | 17 | 22.067 | 8.806 | 2.51× |
| exchange-broker | 181 | 13 | 3.227 | 1.096 | 2.95× |
| local-telemetry | 6 | 3 | 0.555 | 0.008 | 70.55× |
| matato | 342 | 11 | 18.470 | 12.461 | 1.48× |
| matato-pi | 76 | 5 | 1.570 | 0.687 | 2.28× |
| mini-broker | 60 | 8 | 1.314 | 1.535 | 0.86× |
| personal-blog | 116 | 8 | 0.842 | 0.127 | 6.64× |
| quick-note | 180 | 8 | 3.978 | 2.651 | 1.50× |
| sintropy-engine | 135 | 12 | 20.781 | 3.619 | 5.74× |
| VU | 109 | 13 | timeout, 30 s | 9.832 | unverified |

Rust is slower on `mini-broker` in all four fresh analysis actions in this run: check 1.491 vs 1.276 seconds; index 1.515 vs 1.455; mutations 1.542 vs 1.346; report 1.535 vs 1.314. No regression is omitted from the CSV results.

### VU is not a passing whole-graph comparison

Python times out in baseline indexing and all four fresh analysis actions: five 30-second timeouts. That blocks 13 reference-origin reader cases. The strict harness exits 1 and records all 18 failures. Earlier diagnostic runs also exceeded 90 seconds in Python receiver-alias expansion; those runs are not final timing evidence.

Rust completes index in 9.721 seconds, report in 9.832, check in 9.332, and mutations in 11.025. Check correctly exits 1 with 713 findings; this does not imply equality to the unavailable Python check result. Native indexing reports 109 files, 3,787 symbols, 115 modules, 47 types, 3,696 callables, 4,849 nodes, 22,970 edges, and zero parse errors.

Both readers complete and match on the native-produced database: all 14 interoperability cases pass, including source, graph navigation, saved mutations, and revision checks. Four independent cases also pass. Overall VU results are 18 passes, five timeouts, and 13 blocked cases. Whole-graph analysis parity remains unverified, and no VU analysis speedup is claimed. See [VU CSV](benchmarks/project-VU.csv).

## Self-analysis

Before adding these statistics files, both implementations analyzed the whole source checkout at `0ca66c3`: 435 files, 205 modules, 285 types, 4,530 callables, zero parse errors, and zero circular import groups. Complete reports match. Both checks return the same empty findings list.

| Action | Python s | Rust s | Ratio |
|---|---:|---:|---:|
| Whole-repository report | 20.574 | 9.863 | 2.09× |
| Whole-repository check | 20.964 | 10.319 | 2.03× |

These are single direct CLI runs, without the developer wrapper. See [self CSV](benchmarks/self.csv).

## Repeat the checks

Build once and freeze both binaries before measuring. Keep those paths unchanged throughout the run.

```sh
cargo build --release --locked --manifest-path atlas-rust/Cargo.toml --bins
mkdir -p /tmp/atlas-bench-bin
cp atlas-rust/target/release/{atlas,atlas-migrate} /tmp/atlas-bench-bin/
sha256sum /tmp/atlas-bench-bin/*

atlas/.venv/bin/python atlas-rust/scripts/parity.py \
  --sample java --sample kotlin --sample go --sample rust --sample elixir \
  --sample python --sample javascript --sample typescript --sample tsx \
  --variants --warmups 0 --repetitions 1 --timeout 60 \
  --rust-bin /tmp/atlas-bench-bin/atlas \
  --rust-migrate /tmp/atlas-bench-bin/atlas-migrate
```

Repeat `--project` or use `--projects-dir` for local inputs. Repeat `--actions` with case-name filters from `--list-actions` to reproduce the selected core actions. Private projects are not public fixtures; only their aggregate counts and timing results are published.

The authoritative outputs are the final frozen-binary runs. Earlier changing-binary diagnostics and initial environment failures are not benchmark results. Local raw reports retain full evidence; public CSV files retain every final case outcome. No reference timeout, missing dependency, failed comparison, or blocked case was converted to a pass.
