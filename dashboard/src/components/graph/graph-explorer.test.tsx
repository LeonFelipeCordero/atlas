import { expect, test } from 'bun:test'

test('report leads to a structure-only map and restores the reading scope and position', () => {
  const result = Bun.spawnSync([
    'bun',
    '--eval',
    `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    const values = []
    let cursor = 0
    let scroll = null
    let focused = null
    globalThis.window = { scrollY: 420, scrollTo: (_, y) => { scroll = y } }
    globalThis.document = { activeElement: { id: 'report-cycle-cycle' }, getElementById: (id) => ({ focus() { focused = id } }) }
    globalThis.requestAnimationFrame = (fn) => fn()
    mock.module('react', () => ({ ...React, useState: (initial) => {
      const index = cursor++
      if (index === values.length) values.push(initial)
      return [values[index], (value) => { values[index] = typeof value === 'function' ? value(values[index]) : value }]
    } }))
    const initial = { scope: { kind: 'repository' }, repositoryId: 'repo', graphRevision: '1',
      graph: { nodes: [], edges: [] }, trail: [{ label: 'repo', scope: { kind: 'repository' } }],
      details: { nodes: [], fileComplexities: {} }, cycles: [], state: 'ready' }
    mock.module('@tanstack/react-query', () => ({ useQuery: (options) => ({ data: { ...initial, scope: options.queryKey.at(-1) } }) }))
    const { GraphExplorer } = await import('./src/components/graph/graph-explorer')
    const render = () => { cursor = 0; return GraphExplorer({ initial }) }
    let report = render()
    const beginsWithReport = report.type.name === 'RepositoryReport'
    report.props.onToggleCycle('cycle', true)
    report.props.onScope({ kind: 'folder', key: 'src' })
    report = render()
    report.props.onExplore({ kind: 'file', key: 'src/a.ts' }, 'function-a')
    const map = render()
    const workspace = map.props.children[1]
    const selected = workspace.props.selected
    const noOverlay = !('activeCycle' in workspace.props)
    workspace.props.onOpen({ scope: { kind: 'folder', key: 'other' } })
    render().props.children[0].props.children[0].props.onClick()
    report = render()
    console.log(JSON.stringify({ beginsWithReport, selected, noOverlay, scope: report.props.view.scope, scroll, focused, expandedCycles: report.props.expandedCycles }))
  `,
  ])
  if (result.exitCode) throw new Error(result.stderr.toString())
  expect(JSON.parse(result.stdout.toString())).toEqual({
    beginsWithReport: true,
    selected: 'function-a',
    noOverlay: true,
    scope: { kind: 'folder', key: 'src' },
    scroll: 420,
    focused: 'report-cycle-cycle',
    expandedCycles: ['cycle'],
  })
})
