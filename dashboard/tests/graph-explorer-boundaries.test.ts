import { expect, test } from 'bun:test'

function explorerBoundaries() {
  const script = `
    import { mock } from 'bun:test'
    const React = { ...await import('react') }
    let scope, response, options, updates = []
    mock.module('react', () => ({ ...React, useState: initial => [
      initial?.kind === 'repository' ? scope : initial, value => updates.push(value),
    ] }))
    mock.module('@tanstack/react-query', () => ({ useQuery: value => { options = value; return response } }))
    mock.module('./src/lib/api', () => ({ api: async url => url }))
    const { GraphExplorer } = await import('./src/components/graph/graph-explorer')
    const { renderToStaticMarkup } = await import('react-dom/server')
    const root = {kind:'repository'}
    const folder = {kind:'folder',key:'src'}
    const file = {kind:'file',key:'source'}
    const initial = {state:'ready', repositoryId:'repo', graphRevision:'rev',
      scope:root, graph:{nodes:[],edges:[]}, cycles:[],
      trail:[{label:'Repository',scope:root}],
      details:{nodes:[],fileComplexities:{source:{functions:0,measured:0,total:0}}},
    }
    const output = []
    for (const current of [root,folder,file]) {
      scope = current
      const trail = [{label:'Repository',scope:root}]
      if (current.kind !== 'repository') trail.push({label:current.key,scope:current})
      response = {data:{...initial,scope:current,trail}}
      updates = []
      const element = GraphExplorer({initial})
      const html = renderToStaticMarkup(element)
      const workspace = element.type(element.props)
      const viewport = workspace.props.children[2].props.children[0].props.children
      viewport.props.back?.()
      output.push({html,url:await options.queryFn(),initial:options.initialData === initial, updates})
    }
    for (const value of [{data:undefined},{data:null},{data:{state:'needsReindex'}},{error:new Error('Network unavailable')}]) {
      scope = root; response = value
      output.push({html:renderToStaticMarkup(GraphExplorer({initial}))})
    }
    console.log(JSON.stringify(output))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  expect(result.exitCode, result.stderr.toString()).toBe(0)
  return JSON.parse(result.stdout.toString()) as Array<{
    html: string
    url?: string
    initial?: boolean
    updates?: Array<unknown>
  }>
}

test('explorer query scopes and empty-state parent boundaries retain their contracts', () => {
  const states = explorerBoundaries()
  expect(states[0].url).toBe(
    '/api/architecture?repositoryId=repo&kind=repository',
  )
  expect(states[1].url).toBe(
    '/api/architecture?repositoryId=repo&kind=folder&key=src',
  )
  expect(states[2].url).toBe(
    '/api/architecture?repositoryId=repo&kind=file&key=source',
  )
  expect(states.slice(0, 3).map((state) => state.initial)).toEqual([
    true,
    false,
    false,
  ])
  expect(states[0].html).toContain('Nothing indexed in this folder')
  expect(states[0].html).not.toContain('Back to parent')
  expect(states[1].html).toContain('Back to parent')
  expect(states[0].updates).toEqual([])
  expect(states[1].updates).toEqual([{ kind: 'repository' }, null, null])
  expect(states[2].updates).toEqual([{ kind: 'repository' }, null, null])
  expect(states[1].html).not.toContain('file-complexity-bar')
  expect(states[2].html).toContain('No functions in this file')
  expect(states[2].html).toContain('file-complexity-bar')
  expect(states[2].html).toContain('Back to parent')
  expect(states[3].html).toContain('Loading the repository graph')
  expect(states[3].html).not.toContain('role="alert"')
  for (const state of states.slice(4)) {
    expect(state.html).toContain('role="alert"')
    expect(state.html).toContain('Try again')
  }
  expect(states[4].html).toContain('This graph needs to be re-indexed.')
  expect(states[5].html).toContain('This graph needs to be re-indexed.')
  expect(states[6].html).toContain('Network unavailable')
})
