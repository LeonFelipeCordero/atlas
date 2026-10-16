import { expect, test } from 'bun:test'

function serviceBoundaries() {
  const script = `
    import {mock} from 'bun:test'
    mock.module('./src/lib/persistence/repositories/factory', () => ({
      createRepositoryContext: () => ({register: value=>value, view:()=>null, close:()=>{}}),
      repositoryDatabasePath: () => '/unused',
    }))
    const {createRepositoryService,architectureScope} = await import('./src/lib/repositories.servers')
    const service = createRepositoryService()
    const result = fn => {try {return {value:fn()}} catch(error) {return {error:error.message,status:error.status}}}
    const input = {name:'n'.repeat(200),location:'l'.repeat(4096)}
    const output = [
      result(()=>service.registerRepository(input)),
      result(()=>service.registerRepository({...input,name:'n'.repeat(201)})),
      result(()=>service.registerRepository({...input,location:'l'.repeat(4097)})),
      result(()=>service.registerRepository('text')),
      result(()=>service.registerRepository(Object.assign([], {name:'array',location:'path'}))),
      result(()=>service.registerRepository(null)),
      result(()=>service.getArchitecture('i'.repeat(200))),
      result(()=>architectureScope(new URLSearchParams({kind:'file',key:'k'.repeat(4096)}))),
      result(()=>architectureScope(new URLSearchParams({kind:'file',key:'k'.repeat(4097)}))),
      result(()=>architectureScope(new URLSearchParams({kind:'folder',key:'src'}))),
      result(()=>architectureScope(new URLSearchParams({kind:'unknown',key:'key'}))),
    ]
    console.log(JSON.stringify(output))
  `
  const result = Bun.spawnSync(['bun', '--eval', script])
  expect(result.exitCode).toBe(0)
  return JSON.parse(result.stdout.toString()) as Array<{
    value?: {
      name?: string
      location?: string
      key?: string
      kind?: string
    } | null
    error?: string
    status?: number
  }>
}

test('repository validation accepts exact maximum lengths and rejects nonobject inputs', () => {
  const states = serviceBoundaries()
  expect(states[0].value?.name).toHaveLength(200)
  expect(states[0].value?.location).toHaveLength(4096)
  expect(states[1]).toEqual({
    error: 'name must be at most 200 characters',
    status: 400,
  })
  expect(states[2]).toEqual({
    error: 'location must be at most 4096 characters',
    status: 400,
  })
  for (const state of states.slice(3, 6))
    expect(state).toEqual({
      error: 'Expected an object with name and location',
      status: 400,
    })
  expect(states[6]).toEqual({ value: null })
  expect(states[7].value?.key).toHaveLength(4096)
  expect(states[8]).toEqual({
    error: 'key must be at most 4096 characters',
    status: 400,
  })
  expect(states[9]).toEqual({ value: { kind: 'folder', key: 'src' } })
  expect(states[10]).toEqual({ error: 'Invalid graph scope', status: 400 })
})
