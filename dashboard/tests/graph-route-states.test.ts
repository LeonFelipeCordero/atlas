import { expect, test } from 'bun:test'

function graphStates() {
  const script = `
    import { mock } from 'bun:test'
    import * as React from 'react'
    import { renderToStaticMarkup } from 'react-dom/server'
    let graph, query
    mock.module('@tanstack/react-query', () => ({
      useQuery: options => options.queryKey[0] === 'graph'
        ? (query = options, graph)
        : {data:[{id:'other',name:'Other'}, {id:'repo /?',name:'Registered',location:'/source'}]},
    }))
    mock.module('@tanstack/react-router', () => ({ Link:'a',
      createFileRoute: () => config => ({...config,useParams:()=>({repositoryId:'repo /?'})}),
    }))
    mock.module('./src/lib/api', () => ({api:async url=>url, formatDate:()=> 'DATE', repositoriesQuery:{queryKey:['repositories']}}))
    mock.module('./src/components/graph/graph-explorer', () => ({GraphExplorer:()=>React.createElement('div',null,'EXPLORER')}))
    const {Route} = await import('./src/routes/graph.$repositoryId')
    const output = []
    for (const state of [
      {isPending:true}, {error:new Error('Request failed'),data:null},
      {data:{state:'ready',rootName:'Indexed root',graphRevision:'rev',importedAt:1}},
      {isFetching:true,data:null},
    ]) {
      graph = state
      output.push({html:renderToStaticMarkup(React.createElement(Route.component)),url:await query.queryFn()})
    }
    console.log(JSON.stringify(output))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  expect(result.exitCode).toBe(0)
  return JSON.parse(result.stdout.toString()) as Array<{
    html: string
    url: string
  }>
}

test('graph route separates pending, errors, ready data and active refresh states', () => {
  const states = graphStates()
  expect(states[0].url).toBe('/api/architecture?repositoryId=repo%20%2F%3F')
  expect(states[0].html).toContain('Loading the repository graph')
  expect(states[0].html).toContain('<h1>Registered</h1>')
  expect(states[0].html).not.toContain('EXPLORER')
  expect(states[0].html).not.toContain('role="alert"')
  expect(states[1].html).toContain('Request failed')
  expect(states[1].html).not.toContain('Your repository is registered')
  expect(states[1].html).not.toContain('EXPLORER')
  expect(states[2].html).toContain('EXPLORER')
  expect(states[2].html).toContain('Indexed DATE')
  expect(states[2].html).not.toContain('needs to be re-indexed')
  expect(states[3].html).toContain('Refreshing…')
  expect(states[3].html).toContain('disabled=""')
  expect(states[3].html).not.toContain('EXPLORER')
})
