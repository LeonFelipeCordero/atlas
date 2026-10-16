import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphCycles } from '../src/components/graph/graph-cycles'
import type { ViewCycle } from '../src/lib/graph-data'
import type { GraphNode } from '../src/lib/project-graph'

function cycle(id: string, keys: Array<string>, outsideCount = 0): ViewCycle {
  return {
    group: {
      id,
      nodeStableKeys: keys,
      exampleCycle: [...keys, keys[0]],
      edges: [],
    },
    nodeIds: keys,
    edges: [],
    outsideCount,
    scope: { kind: 'repository' },
    labels: { a: 'Alpha' },
    linkedNodeIds: ['selected'],
  }
}

function render(
  cycles?: Array<ViewCycle>,
  kind?: GraphNode['kind'],
  active = false,
) {
  const item = kind ? ({ id: 'selected', kind } as GraphNode) : undefined
  return renderToStaticMarkup(
    <GraphCycles
      cycles={cycles}
      item={item}
      activeCycle={active ? cycles![0] : null}
      onCycle={() => {}}
      onCycleScope={() => {}}
    />,
  )
}

test('cycle list distinguishes missing data, selection, labels and outside boundaries', () => {
  expect(render()).toBe('')
  expect(render([])).toBe('')
  const single = cycle('one', ['a'])
  const multiple = cycle('two', ['a', 'b'], 2)
  const hidden = { ...cycle('hidden', ['z']), linkedNodeIds: [] }
  const list = render([single, multiple, hidden])
  expect(list).toContain('>3</span>')
  expect(list).toContain('1 file in import cycle')
  expect(list).toContain('2 files in import cycle')
  expect(list).toContain('Alpha → b → Alpha')
  expect(list).toContain('2 files outside this scope')
  expect(list).not.toContain('0 files outside')
  const folder = render([single, hidden], 'folder', true)
  expect(folder).toContain('Contains circular dependencies')
  expect(folder).toContain('>1</span>')
  expect(folder).toContain('aria-pressed="true"')
  expect(folder).toContain('Member files and containing folders highlighted')
  expect(folder).not.toContain('function’s owning file')
  const callable = render([{ ...single, outsideCount: 1 }], 'function')
  expect(callable).toContain(
    'File-import cycles for this function’s owning file',
  )
  expect(callable).toContain('1 file outside this scope')
  expect(callable).toContain('aria-pressed="false"')
  expect(callable).not.toContain(
    'Member files and containing folders highlighted',
  )
  expect(render([hidden], 'file')).toBe('')
  expect(render([single], 'file')).not.toContain('function’s owning file')
})
