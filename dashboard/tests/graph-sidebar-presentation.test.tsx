import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphSidebar } from '../src/components/graph/graph-sidebar'
import type { GraphDetails } from '../src/lib/graph-data'
import type { GraphNode, ProjectGraph } from '../src/lib/project-graph'

const nodes: Array<GraphNode> = [
  {
    id: 'a',
    label: 'Alpha',
    path: 'alpha.ts',
    kind: 'file',
    detail: 'fallback',
    scope: { kind: 'file', key: 'a' },
  },
  {
    id: 'b',
    label: 'Beta',
    path: '',
    kind: 'function',
    detail: 'callable detail',
    scope: null,
    destination: { scope: { kind: 'file', key: 'a' }, focusId: 'b' },
    role: 'boundary',
  },
  {
    id: 'c',
    label: 'Gamma',
    path: 'gamma.ts',
    kind: 'file',
    detail: '',
    scope: null,
  },
  {
    id: 'f',
    label: 'Folder',
    path: 'src',
    kind: 'folder',
    detail: '',
    scope: { kind: 'folder', key: 'f' },
  },
]
const graph: ProjectGraph = {
  nodes,
  edges: [
    {
      id: 'ab',
      source: 'a',
      target: 'b',
      count: 1,
      relationships: { CALLS: 1 },
    },
    {
      id: 'ca',
      source: 'c',
      target: 'a',
      count: 1,
      relationships: { CALLS: 1 },
    },
    {
      id: 'bc',
      source: 'b',
      target: 'c',
      count: 1,
      relationships: { CALLS: 1 },
    },
  ],
}
const details: GraphDetails = {
  nodes: [],
  fileComplexities: {
    a: { functions: 0, measured: 0, total: 0 },
    c: { functions: 0, measured: 0, total: 0 },
  },
}

function sidebar(selected: string | null, view = graph, extra = details) {
  return renderToStaticMarkup(
    <GraphSidebar
      graph={view}
      details={extra}
      selected={selected}
      onSelect={() => {}}
      onOpen={() => {}}
      cycles={undefined}
      activeCycle={null}
      onCycle={() => {}}
      onCycleScope={() => {}}
    />,
  )
}

test('sidebar renders local and boundary destinations without inventing navigation', () => {
  const html = sidebar(null)
  expect(html).toContain('aria-label="Graph contents"')
  expect(html.match(/lucide-folder/g)).toHaveLength(1)
  expect(html.match(/class="[^"]*lucide-file-code[^"]*"/g)).toHaveLength(2)
  expect(html.match(/lucide-braces/g)).toHaveLength(1)
  expect(html).toContain('Outside scope · callable detail')
  expect(html).toContain('aria-label="Open Beta"')
  expect(html).toContain('aria-label="Open alpha.ts"')
  expect(html).toContain('aria-label="Open src"')
  expect(html).not.toContain('aria-label="Open gamma.ts"')
  expect(html).not.toContain('No items at this level')
  expect(sidebar(null, { nodes: [], edges: [] })).toContain(
    'No items at this level.',
  )
})

test('sidebar selects the exact item and shows incoming and outgoing connections only', () => {
  const html = sidebar('a')
  expect(html).toContain('<h3>alpha.ts</h3>')
  expect(html).toContain('Explore file')
  expect(html).toContain('<span>2</span>')
  expect(html).toContain('Uses <strong>Beta</strong>')
  expect(html).toContain('Used by <strong>Gamma</strong>')
  expect(html).not.toContain('No connections recorded here')
  const callable = sidebar('b')
  expect(callable).toContain('<h3>Beta</h3>')
  expect(callable).toContain('function · Outside scope')
  expect(callable).toContain('Go to function')
  const isolated = sidebar('f')
  expect(isolated).toContain('No connections recorded here')
  expect(isolated).not.toContain('Outside scope')
  expect(sidebar('c')).not.toContain('open-selected')
  expect(sidebar('missing')).toContain('aria-label="Graph contents"')
})

test('callable titles include source lines only when the original node supplies one', () => {
  const view = { nodes: [{ ...nodes[1], path: 'alpha.ts' }], edges: [] }
  expect(sidebar('b', view)).toContain('<h3>alpha.ts · Beta</h3>')
  const original = {
    stableKey: 'b',
    startLine: 7,
  } as GraphDetails['nodes'][number]
  expect(
    sidebar('b', view, { nodes: [original], fileComplexities: {} }),
  ).toContain('<h3>alpha.ts:7 · Beta</h3>')
})
