---
version: 1
slug: "dashboard-src-components-graph-graph-workspace-tsx"
primary_target: "dashboard/src/components/graph/graph-workspace.tsx"
related_targets: ["dashboard/src/components/graph/project-navigator.tsx","dashboard/src/styles/project-workspace.css"]
---

# Project navigator

Mode: Operate. Scope: the graph workspace, not the repository list or saved demo.

## Direction contract

THESIS: Project structure stays visible while the engineer moves between structural browsing and recorded analysis. Reject a top-level tab swap that retains the original right sidebar.

OWN-WORLD: Keep the incumbent light plum surfaces, system sans type, soft borders, rounded controls, and graph node geometry. No new palette or fabricated report data.

STORY: Browse a folder, locate a file, inspect its connections, then read its report without losing the expanded project tree. Explicit report actions return to the relevant map scope.

FIRST VIEWPORT: A 246px left navigator anchors a fluid work area. Breadcrumbs establish location above compact Map and Report controls. The map owns the full remaining width; a collapsible inspector sits below it. On narrow screens a Project disclosure reveals the same navigator. The signature interaction is a stable expanded tree across work-area changes.

FORM: User-pinned proposal B; code-led implementation in the established visual world. No seed or new visual identity.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
