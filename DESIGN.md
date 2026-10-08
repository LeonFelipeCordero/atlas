# Design

A light workspace for engineers mapping unfamiliar code at their desk. Restrained color: plum-tinted neutrals with a muted plum accent for actions, selection, and graph structure. Small green dots signal an imported snapshot, not an automatically current index.

System sans typography, monospace only for CLI commands and signatures. Rounded shadcn buttons, inputs, and badges. Repository rows instead of repeated cards. Thin borders separate regions; graph nodes use soft 12px corners.

The graph workspace has full path breadcrumbs above a large canvas with a searchable right-hand contents list. Folders navigate at any depth; single-child folder chains use compact path labels. Selecting an item replaces the list with connections and source details. Conventional test files stay hidden. Outgoing dependencies outside the current scope use dashed outlines and explicit Outside scope labels. Outside-repository references and outside-scope test dependencies are excluded. Indexed boundary folders/files can be explored, and boundary functions navigate to their containing file with the function selected. On narrow screens the inspector stacks below the canvas. Motion is limited to state feedback and disabled with reduced-motion preferences.

The `dashboard/src/styles.css` entry imports tokens and base styles from `dashboard/src/styles/base.css`, graph styles from `dashboard/src/styles/graph.css`, and responsive rules from `dashboard/src/styles/responsive.css`. Graph behavior lives in `dashboard/src/components/graph/`.
