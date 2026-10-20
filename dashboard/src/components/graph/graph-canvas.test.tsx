import { expect, test } from 'bun:test'

// Keep hook and React Flow mocks in a separate process.
function canvasStates() {
  const script = `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    mock.module('react', () => ({ ...React, useMemo: (fn) => fn(), useEffect: () => {} }))
    mock.module('@xyflow/react', () => ({
      Background: 'background', BackgroundVariant: { Dots: 'dots' }, Controls: 'controls',
      Handle: 'handle', MarkerType: { ArrowClosed: 'arrowclosed' },
      Position: { Top: 'top', Left: 'left', Right: 'right', Bottom: 'bottom' },
      ReactFlow: 'flow', ReactFlowProvider: 'provider', useReactFlow: () => ({}),
    }))
    const { default: GraphCanvas } = await import('./src/components/graph/graph-canvas')
    const nodes = ['a', 'b', 'c'].map((id) => ({
      id, label: id, kind: 'file', path: id, detail: '', scope: null,
    }))
    const edges = [['a', 'b'], ['b', 'c'], ['c', 'a']].map(([source, target]) => ({
      id: source + target, source, target, count: 2, relationships: { IMPORTS: 2 },
    }))
    function render(selected, activeCycle = null) {
      const wrapper = GraphCanvas({
        graph: { nodes, edges }, selected, activeCycle, focusId: null,
        onSelect: () => {}, onOpen: () => {},
      })
      const canvas = wrapper.props.children
      return canvas.type(canvas.props).props
    }
    const normal = render(null)
    const node = normal.nodeTypes.code({ data: normal.nodes[0].data, selected: false })
    const handles = node.props.children.filter((child) => child.type === 'handle').map((child) => child.props)
    const selected = render('b')
    const cycle = render(null, {
      nodeIds: ['a', 'c'], edges: [{ id: 'ac', source: 'a', target: 'c' }, edges[2]],
    })
    console.log(JSON.stringify({
      edges: normal.edges, handles, selected: selected.edges,
      cycle: cycle.edges, cycleNodes: cycle.nodes.map(({ id, selected, data }) => ({ id, selected, muted: data.muted })),
    }))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  if (result.exitCode !== 0) throw new Error(result.stderr.toString())
  return JSON.parse(result.stdout.toString())
}

test('canvas wires historical handles and smoothstep edges into React Flow', () => {
  const { edges, handles } = canvasStates()
  expect(handles).toEqual([
    { id: 'target-top', type: 'target', position: 'top' },
    { id: 'target-left', type: 'target', position: 'left' },
    { id: 'source-right', type: 'source', position: 'right' },
    { id: 'source-bottom', type: 'source', position: 'bottom' },
  ])
  expect(
    edges.map(
      ({ id, type, sourceHandle, targetHandle }: Record<string, string>) => ({
        id,
        type,
        sourceHandle,
        targetHandle,
      }),
    ),
  ).toEqual([
    {
      id: 'ab',
      type: 'smoothstep',
      sourceHandle: 'source-right',
      targetHandle: 'target-left',
    },
    {
      id: 'bc',
      type: 'smoothstep',
      sourceHandle: 'source-right',
      targetHandle: 'target-left',
    },
    {
      id: 'ca',
      type: 'smoothstep',
      sourceHandle: 'source-right',
      targetHandle: 'target-top',
    },
  ])
  expect(
    edges.every(
      (edge: { label: string; markerEnd: { type: string } }) =>
        edge.label === '2' && edge.markerEnd.type === 'arrowclosed',
    ),
  ).toBe(true)
})

test('selection and cycle-only edges retain highlighting and directional routing', () => {
  const { selected, cycle, cycleNodes } = canvasStates()
  expect(
    selected.find((edge: { id: string }) => edge.id === 'ab').style.strokeWidth,
  ).toBe(2.5)
  expect(
    selected.find((edge: { id: string }) => edge.id === 'ca').style.opacity,
  ).toBe(0.12)
  expect(cycle.find((edge: { id: string }) => edge.id === 'ac')).toMatchObject({
    source: 'a',
    target: 'c',
    type: 'smoothstep',
    label: 'Cycle import',
    sourceHandle: 'source-right',
    targetHandle: 'target-left',
    style: { strokeWidth: 2.5 },
  })
  expect(cycle.find((edge: { id: string }) => edge.id === 'ca')).toMatchObject({
    sourceHandle: 'source-right',
    targetHandle: 'target-top',
    label: 'Cycle import',
  })
  expect(cycleNodes).toEqual([
    { id: 'a', selected: true, muted: false },
    { id: 'b', selected: false, muted: true },
    { id: 'c', selected: true, muted: false },
  ])
})
