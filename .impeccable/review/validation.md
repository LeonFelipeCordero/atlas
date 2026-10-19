# Proposal B validation

Branch: `proposal/project-navigator`, based on `31a3e7b`, PR target `main`.

The saved Atlas demo is unchanged. Browser runs use a private SQLite copy of the existing index, repository `2398a7ad-b8ee-4b86-a611-20c913cd928d`. The folder screenshot shows `atlas/src/atlas`; Report shows `atlas/src/atlas/indexer.py`. All values come from that index. No backend, schema, fixture, or README changes.

## Checks

- `cd dashboard && bun run build`: pass. Existing dependency directive warnings remain.
- `cd dashboard && bun test`: 202 pass, 0 fail. An initial cold run timed out in an unrelated service-export test; the standard full rerun passed.
- `cd dashboard && bun run typecheck`: pass.
- `cd dashboard && bun lint --fix`: pass.
- `CARGO_TARGET_DIR=dashboard/tests/rust-fixture/target cargo run --manifest-path atlas-rust/Cargo.toml --locked --bin atlas -- check --f .`: all checks passed. Reuses the dashboard integration build cache; analyzes the entire repository.
- Impeccable detector: run once on changed UI targets, no findings.
- Fresh finish review: requested readable initial zoom, removal of repeated report filename, and layout documentation. Verdict pass scored all three resolved; disposition `ship` at that scope.

## Browser evidence

Local Brave, isolated runner sessions, `http://127.0.0.1:4312/graph/2398a7ad-b8ee-4b86-a611-20c913cd928d`.

- Folder navigation → Report → explicit return to Map: pass.
- File navigation → Report → recorded complexity and dependency metrics, expanded navigator retained: pass.
- 390px Project disclosure → file → close navigator → Report: pass.

All final scenarios show zero console errors, no failed HTTP requests, and successful app/session cleanup. Browser assertions cover visible accessibility snapshots; they do not inspect WebSocket traffic.

Screenshots: `desktop.png` (1440×1100 structural Map), `report.png` (1440×1100 Report), `mobile.png` (390×844 Report). These are viewport captures, not full-page captures. Temporary runner artifacts are removed after retaining these non-sensitive demo screenshots.

## Tradeoff

The persistent navigator uses horizontal space, but removes the competing permanent right sidebar. Large graphs start at readable zoom and can extend beyond the canvas; pan or use Fit view for an overview. Root filtering is intentionally scoped to root entries, while folders load lazily. On narrow screens the navigator is a disclosure, not an overlay. Report preserves the existing analysis and cycles without painting them onto the map.
