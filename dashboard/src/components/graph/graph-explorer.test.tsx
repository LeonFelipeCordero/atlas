import { expect, test } from 'bun:test'

// Isolate hook mocks so interaction checks cannot affect other Bun tests.
function explorerStates() {
  const script = `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    const values = []
    let cursor = 0
    let showCycle = true
    const cycle = { group: { id: 'cycle' }, scope: { kind: 'folder', key: 'app' } }
    const initial = {
      state: 'ready', repositoryId: 'repo', graphRevision: 'revision',
      scope: { kind: 'repository' }, graph: { nodes: [], edges: [] },
      trail: [{ label: 'Repository', scope: { kind: 'repository' } }],
      details: { nodes: [], fileComplexities: {} }, cycles: [cycle],
    }
    mock.module('react', () => ({
      ...React,
      useState: (initialValue) => {
        const index = cursor++
        if (index === values.length) values.push(initialValue)
        return [values[index], (value) => { values[index] = value }]
      },
    }))
    mock.module('@tanstack/react-query', () => ({
      useQuery: (options) => ({
        data: { ...initial, scope: options.queryKey.at(-1), cycles: showCycle ? [cycle] : [] },
      }),
    }))
    const { GraphExplorer } = await import('./src/components/graph/graph-explorer')
    const states = []
    function render() {
      cursor = 0
      const props = GraphExplorer({ initial }).props
      states.push({
        selected: props.selected, focusId: props.focusId,
        cycle: props.activeCycle?.group.id ?? null, scope: props.view.scope,
      })
      return props
    }
    let actions = render()
    if (actions.mode !== 'explore') throw new Error('Explore must be the default')
    actions.onSelect('run')
    actions = render()
    actions.onMode('report')
    cursor = 0
    const report = GraphExplorer({ initial }).props
    if (report.mode !== 'report' || report.selected !== 'run') throw new Error('Report lost selection')
    report.onMode('explore')
    cursor = 0
    const explore = GraphExplorer({ initial }).props
    if (explore.mode !== 'explore' || explore.selected !== 'run') throw new Error('Explore lost selection')
    actions.onCycle(cycle)
    actions = render()
    showCycle = false
    actions = render()
    actions.onOpen({ destination: { scope: { kind: 'file', key: 'service' }, focusId: 'stop' } })
    actions = render()
    showCycle = true
    actions.onCycleScope(cycle)
    actions = render()
    actions.navigate(0)
    actions = render()
    actions.onOpen({ scope: { kind: 'folder', key: 'lib' } })
    actions = render()
    actions.onSelect('lib-file')
    actions = render()
    actions.onSelect(null)
    render()
    console.log(JSON.stringify(states))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  if (result.exitCode !== 0) throw new Error(result.stderr.toString())
  return JSON.parse(result.stdout.toString()) as Array<{
    selected: string | null
    focusId: string | null
    cycle: string | null
    scope: { kind: string; key?: string }
  }>
}

test('selection, cycles, boundary destinations and breadcrumbs retain focus behavior', () => {
  const repository = { kind: 'repository' }
  const folder = { kind: 'folder', key: 'lib' }
  expect(explorerStates()).toEqual([
    { selected: null, focusId: null, cycle: null, scope: repository },
    { selected: 'run', focusId: 'run', cycle: null, scope: repository },
    { selected: 'run', focusId: 'run', cycle: 'cycle', scope: repository },
    { selected: 'run', focusId: 'run', cycle: null, scope: repository },
    {
      selected: 'stop',
      focusId: 'stop',
      cycle: null,
      scope: { kind: 'file', key: 'service' },
    },
    {
      selected: null,
      focusId: null,
      cycle: 'cycle',
      scope: { kind: 'folder', key: 'app' },
    },
    { selected: null, focusId: null, cycle: null, scope: repository },
    { selected: null, focusId: null, cycle: null, scope: folder },
    { selected: 'lib-file', focusId: 'lib-file', cycle: null, scope: folder },
    { selected: null, focusId: null, cycle: null, scope: folder },
  ])
})
