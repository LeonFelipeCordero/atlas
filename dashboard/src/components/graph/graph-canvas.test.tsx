import { expect, test } from 'bun:test'

// Keep hook and React Flow mocks in a separate process.
function canvasStates() {
  const script = `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    const centers = [], fits = []
    mock.module('react', () => ({ ...React, useMemo: (fn) => fn(), useEffect: (fn) => fn() }))
    mock.module('@xyflow/react', () => ({
      Background: 'background', BackgroundVariant: { Dots: 'dots' }, Controls: 'controls',
      Handle: 'handle', MarkerType: { ArrowClosed: 'arrowclosed' },
      Position: { Top: 'top', Left: 'left', Right: 'right', Bottom: 'bottom' },
      ReactFlow: 'flow', ReactFlowProvider: 'provider',
      useReactFlow: () => ({ setCenter: (...args) => centers.push(args), fitView: (options) => fits.push(options) }),
    }))
    const { default: GraphCanvas } = await import('./src/components/graph/graph-canvas')
    const nodes = ['a', 'b', 'c', 'd'].map((id) => ({
      id, label: id, kind: 'file', path: id, detail: '', scope: null,
    }))
    const edges = [['a', 'b'], ['b', 'c'], ['c', 'a']].map(([source, target]) => ({
      id: source + target, source, target, count: 2, relationships: { IMPORTS: 2 },
    }))
    function render(selected) {
      const wrapper = GraphCanvas({
        graph: { nodes, edges }, selected, focusId: selected,
        onSelect: () => {}, onOpen: () => {},
      })
      const canvas = wrapper.props.children
      return canvas.type(canvas.props).props
    }
    const normal = render(null)
    const node = normal.nodeTypes.code({ data: normal.nodes[0].data, selected: false })
    const handles = node.props.children.filter((child) => child.type === 'handle').map((child) => child.props)
    const selected = render('b')
    console.log(JSON.stringify({
      edges: normal.edges, handles, selected: selected.edges,
      nodes: selected.nodes.map(({ id, selected, data }) => ({ id, selected, muted: data.muted })),
      normalNodes: normal.nodes.map(({ selected, data }) => ({ selected, muted: data.muted })),
      centers, fits,
    }))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  if (result.exitCode !== 0) throw new Error(result.stderr.toString())
  return JSON.parse(result.stdout.toString())
}

test('canvas wires top-to-bottom handles and smoothstep edges into React Flow', () => {
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
      sourceHandle: 'source-bottom',
      targetHandle: 'target-top',
    },
    {
      id: 'bc',
      type: 'smoothstep',
      sourceHandle: 'source-bottom',
      targetHandle: 'target-top',
    },
    {
      id: 'ca',
      type: 'smoothstep',
      sourceHandle: 'source-bottom',
      targetHandle: 'target-left',
    },
  ])
  expect(
    edges.every(
      (edge: { label: string; markerEnd: { type: string } }) =>
        edge.label === '2' && edge.markerEnd.type === 'arrowclosed',
    ),
  ).toBe(true)
})

test('selection retains node and edge highlighting and focuses the selected node', () => {
  const { selected, nodes, normalNodes, centers, fits } = canvasStates()
  expect(
    selected.find((edge: { id: string }) => edge.id === 'ab').style.strokeWidth,
  ).toBe(2.5)
  expect(
    selected.find((edge: { id: string }) => edge.id === 'ca').style.opacity,
  ).toBe(0.12)
  expect(
    selected.find((edge: { id: string }) => edge.id === 'bc'),
  ).toMatchObject({
    label: '2',
    ariaLabel: '2 relationships from b to c',
    style: { strokeWidth: 2.5, opacity: 0.75 },
  })
  expect(nodes).toEqual([
    { id: 'a', selected: false, muted: false },
    { id: 'b', selected: true, muted: false },
    { id: 'c', selected: false, muted: false },
    { id: 'd', selected: false, muted: true },
  ])
  expect(normalNodes).toEqual(Array(4).fill({ selected: false, muted: false }))
  expect(centers).toEqual([
    [expect.any(Number), expect.any(Number), { zoom: 1 }],
  ])
  expect(fits).toEqual([{ padding: 0.15 }])
})
