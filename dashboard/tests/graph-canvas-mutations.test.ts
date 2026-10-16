import { expect, test } from 'bun:test'

function canvasStates() {
  const script = `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    const effects = []
    mock.module('react', () => ({ ...React, useMemo: f => f(), useEffect: f => f() }))
    mock.module('@xyflow/react', () => ({
      Background: 'div', BackgroundVariant: { Dots: 'dots' }, Controls: 'div',
      Handle: 'span', Position: { Left: 'left', Right: 'right' },
      MarkerType: { ArrowClosed: 'arrowclosed' }, ReactFlow: 'div', ReactFlowProvider: 'div',
      useReactFlow: () => ({
        setCenter: (...args) => effects.push(['center', ...args]),
        fitView: options => effects.push(['fit', options]),
      }),
    }))
    const { default: GraphCanvas } = await import('./src/components/graph/graph-canvas')
    const { renderToStaticMarkup } = await import('react-dom/server')
    const graph = {
      nodes: ['a', 'b', 'c', 'd'].map(id => ({
        id, label: id.toUpperCase(), kind: 'file', path: id === 'd' ? '' : id,
        detail: 'file · details', scope: id === 'a' ? {kind:'file',key:id} : null,
        destination: id === 'b' ? { scope: {kind:'file',key:'a'}, focusId:'b' } : undefined,
        role: id === 'd' ? 'boundary' : undefined,
      })),
      edges: [['ab','a','b',2],['bc','b','c',1]].map(([id,source,target,count]) =>
        ({id,source,target,count,relationships:{CALLS:count}})),
    }
    const cycle = {nodeIds:['a','c'], edges:[{id:'ab',source:'a',target:'b'}, {id:'ca',source:'c',target:'a'}]}
    const states = [null,'a','c'].map(selected => ({selected, activeCycle:null}))
    states.push({selected:'b', activeCycle:cycle})
    const output = states.map(state => {
      const actions = []
      const wrapper = GraphCanvas({graph, ...state, focusId:state.selected,
        onSelect:id => actions.push(['select',id]), onOpen:node => actions.push(['open',node.id])})
      const canvas = wrapper.props.children.type(wrapper.props.children.props).props
      canvas.onNodeClick(null,canvas.nodes[0])
      canvas.onNodeDoubleClick(null,canvas.nodes[1])
      canvas.onPaneClick()
      canvas.onEdgeClick(null,canvas.edges[1])
      return { nodes:canvas.nodes.map(n => ({id:n.id, position:n.position, selected:n.selected, muted:n.data.muted, label:n.ariaLabel})),
        edges:canvas.edges, actions,
        html:canvas.nodes.map(n => renderToStaticMarkup(React.createElement(canvas.nodeTypes.code, {data:n.data,selected:n.selected}))),
      }
    })
    console.log(JSON.stringify({output,effects}))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  expect(result.exitCode).toBe(0)
  return JSON.parse(result.stdout.toString())
}

test('canvas preserves selection, cycle edges, labels and node actions', () => {
  const { output, effects } = canvasStates()
  expect(output[0].nodes.map((n: any) => [n.selected, n.muted])).toEqual([
    [false, false],
    [false, false],
    [false, false],
    [false, false],
  ])
  expect(output[1].nodes.map((n: any) => [n.selected, n.muted])).toEqual([
    [true, false],
    [false, false],
    [false, true],
    [false, true],
  ])
  expect(output[2].nodes.map((n: any) => [n.selected, n.muted])).toEqual([
    [false, true],
    [false, false],
    [true, false],
    [false, true],
  ])
  expect(output[3].nodes.map((n: any) => [n.selected, n.muted])).toEqual([
    [true, false],
    [false, true],
    [true, false],
    [false, true],
  ])
  expect(
    output[0].edges.map((e: any) => [
      e.label ?? null,
      e.style.strokeWidth,
      e.style.opacity,
    ]),
  ).toEqual([
    ['2', 1.4, 0.75],
    [null, 1.4, 0.75],
  ])
  expect(
    output[1].edges.map((e: any) => [e.style.strokeWidth, e.style.opacity]),
  ).toEqual([
    [2.5, 0.75],
    [1.4, 0.12],
  ])
  expect(output[2].edges.map((e: any) => e.style.strokeWidth)).toEqual([
    1.4, 2.5,
  ])
  expect(
    output[3].edges.map((e: any) => [e.id, e.label ?? null, e.style.opacity]),
  ).toEqual([
    ['ab', 'Cycle import', 0.75],
    ['bc', null, 0.12],
    ['ca', 'Cycle import', 0.75],
  ])
  expect(output[0].html[0]).toContain('Explore file')
  expect(output[0].html[0]).toContain('aria-label="Explore a"')
  expect(output[0].html[1]).toContain('Go to function')
  expect(output[0].html[2]).toContain('node-kind')
  expect(output[0].html[3]).toContain('is-boundary')
  expect(output[0].nodes[3].label).toBe(
    'file: D. Outside scope dependency. Select to inspect connections.',
  )
  expect(output[0].actions).toEqual([
    ['select', 'a'],
    ['open', 'b'],
    ['select', null],
    ['select', 'b'],
  ])
  expect(effects[0]).toEqual(['fit', { padding: 0.15 }])
  expect(effects[1]).toEqual([
    'center',
    output[1].nodes[0].position.x + 110,
    output[1].nodes[0].position.y + 39,
    { zoom: 1 },
  ])
  expect(effects[2]).toEqual([
    'center',
    output[2].nodes[2].position.x + 110,
    output[2].nodes[2].position.y + 39,
    { zoom: 1 },
  ])
  expect(effects[3]).toEqual([
    'fit',
    { nodes: [{ id: 'a' }, { id: 'c' }], padding: 0.25 },
  ])
})
