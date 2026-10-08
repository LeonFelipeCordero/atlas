import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, beforeEach, expect, test } from 'bun:test'
import { Database } from 'bun:sqlite'
import { openDatabase } from './database.servers'
import {
  getArchitecture,
  listRepositories,
  registerRepository,
  repositoryErrorResponse,
} from './repositories.servers'
import { parseArtifact } from './architecture-artifact'
import { hideTestFiles } from './graph-visibility'
import { buildProjectGraph } from './project-graph'
import type { Artifact } from './architecture-artifact'
import type { AppDatabase } from './database.servers'

let directory: string
let path: string
let database: AppDatabase

function python(...args: Array<string>) {
  const result = Bun.spawnSync([
    'uv',
    'run',
    '--project',
    fileURLToPath(new URL('../../../atlas', import.meta.url)),
    'atlas',
    ...args,
  ])
  if (result.exitCode !== 0) throw new Error(result.stderr.toString())
  return result.stdout.toString()
}

beforeEach(() => {
  directory = mkdtempSync(join(tmpdir(), 'shared-graph-database-'))
  path = join(directory, 'nested', 'test.sqlite')
  python('migrate', '--database', path)
  database = openDatabase(path)
})

afterEach(() => {
  database.close()
  rmSync(directory, { recursive: true, force: true })
})

test('UI opens a Python-migrated database without owning migrations', () => {
  const repository = registerRepository(
    { name: ' Example ', location: ' /work/example ' },
    database,
  )
  expect(repository.name).toBe('Example')
  expect(repository.location).toBe('/work/example')
  expect(repository.createdAt).toBeGreaterThan(1_000_000_000_000)
  expect(repository.importedAt).toBeNull()
  expect(listRepositories(database)).toEqual([repository])
  expect(getArchitecture(repository.id, database)).toBeNull()
  database.close()
  database = openDatabase(path)
  expect(listRepositories(database)).toEqual([repository])
  expect(
    database.query('SELECT version_num FROM alembic_version').get(),
  ).toEqual({ version_num: '0002_normalized_graphs' })
})

test('missing or unmigrated databases fail without creating a schema', () => {
  const missing = join(directory, 'missing.sqlite')
  expect(() => openDatabase(missing)).toThrow()
  expect(existsSync(missing)).toBe(false)
  const emptyPath = join(directory, 'empty.sqlite')
  const empty = new Database(emptyPath, { create: true })
  empty.close()
  const check = openDatabase(emptyPath)
  expect(() => listRepositories(check)).toThrow('no such table')
  expect(
    check.query('SELECT name FROM sqlite_master WHERE type = ?').all('table'),
  ).toEqual([])
  check.close()
})

test('name uniqueness and validation retain existing API behavior', () => {
  registerRepository({ name: 'Example', location: 'local' }, database)
  expect(() =>
    registerRepository({ name: 'EXAMPLE', location: 'other' }, database),
  ).toThrow('already exists')
  for (const input of [
    null,
    [],
    {},
    { name: 5, location: 'x' },
    { name: ' ', location: 'x' },
    { name: 'x', location: ' ' },
    { name: 'x'.repeat(201), location: 'x' },
  ])
    expect(() => registerRepository(input, database)).toThrow()
  expect(listRepositories(database)).toHaveLength(1)
  expect(() => getArchitecture('unknown', database)).toThrow(
    'Repository not found',
  )
  expect(() => getArchitecture(' ', database)).toThrow(
    'repositoryId is required',
  )
})

test('registration requires local folders and rejects duplicate canonical locations', () => {
  expect(() =>
    registerRepository(
      { name: 'Remote', location: 'https://example.com/project' },
      database,
    ),
  ).toThrow('URLs cannot be indexed')
  const source = join(directory, 'source')
  mkdirSync(source)
  const alias = join(directory, 'alias')
  symlinkSync(source, alias, 'dir')
  const repository = registerRepository(
    { name: 'Local', location: relative(process.cwd(), source) },
    database,
  )
  expect(repository.location).toBe(source)
  for (const location of [source, alias, join(source, '..', 'source')])
    expect(() =>
      registerRepository({ name: 'Duplicate', location }, database),
    ).toThrow('folder already exists')
  expect(listRepositories(database)).toEqual([repository])
})

test('registration follows symlinks before parent segments like Python indexing', () => {
  const first = join(directory, 'first')
  const second = join(directory, 'second')
  mkdirSync(first)
  mkdirSync(join(second, 'nested'), { recursive: true })
  symlinkSync(join(second, 'nested'), join(first, 'alias'), 'dir')
  const location = `${first}/alias/..`
  const repository = registerRepository(
    { name: 'Symlink parent', location },
    database,
  )
  expect(repository.location).toBe(second)
  const summary = JSON.parse(
    python('index', '-f', location, '--database', path),
  )
  expect(summary.repositoryId).toBe(repository.id)
  expect(listRepositories(database)).toHaveLength(1)
  expect(() =>
    registerRepository({ name: 'Duplicate', location: second }, database),
  ).toThrow('folder already exists')
})

test('Python indexes repositories registered by the UI, and the UI sees reindex writes', () => {
  const source = join(directory, 'source')
  mkdirSync(source)
  const file = join(source, 'main.py')
  writeFileSync(file, 'def run():\n    return 1\n')
  const repository = registerRepository(
    { name: 'Shared', location: source },
    database,
  )
  const summary = JSON.parse(python('index', '-f', source, '--database', path))
  const first = getArchitecture(repository.id, database)!
  expect(summary.repositoryId).toBe(repository.id)
  expect(first.artifact.schemaVersion).toBe(2)
  expect(first.artifact).toMatchObject({ stats: { files: 1 } })
  expect(first.artifact.nodes.some((node) => node.name === 'run')).toBe(true)
  writeFileSync(file, 'def replacement():\n    return 2\n')
  python('index', '--folder', source, '--database', path)
  const replacement = getArchitecture(repository.id, database)!
  expect(
    replacement.artifact.nodes.some((node) => node.name === 'replacement'),
  ).toBe(true)
  expect(replacement.artifact.nodes.some((node) => node.name === 'run')).toBe(
    false,
  )
  expect(listRepositories(database)[0].importedAt).toBe(replacement.importedAt)
  expect(
    database.query('SELECT count(*) AS count FROM repository_graphs').get(),
  ).toEqual({ count: 1 })
  expect(existsSync(join(source, 'graph.json'))).toBe(false)
  expect(() => getArchitecture(repository.name, database)).toThrow(
    'Repository not found',
  )

  // Folder selection is independent of names; API lookups still use IDs.
  const otherSource = join(directory, 'other-source')
  mkdirSync(otherSource)
  const idNamed = registerRepository(
    { name: repository.id, location: otherSource },
    database,
  )
  writeFileSync(join(otherSource, 'main.py'), 'def id_named():\n    return 3\n')
  const selected = JSON.parse(
    python('index', '-f', otherSource, '--database', path),
  )
  expect(selected.repositoryId).toBe(idNamed.id)
  const idNamedGraph = getArchitecture(idNamed.id, database)!
  expect(
    idNamedGraph.artifact.nodes.some((node) => node.name === 'id_named'),
  ).toBe(true)
  expect(getArchitecture(repository.id, database)).toEqual(replacement)
  expect(
    database
      .query(
        'SELECT repository_id FROM repository_graphs ORDER BY repository_id',
      )
      .all(),
  ).toEqual(
    [repository.id, idNamed.id]
      .sort()
      .map((repository_id) => ({ repository_id })),
  )
})

test('folder reports register and update graphs visible to the UI', () => {
  const source = join(directory, 'source')
  mkdirSync(source)
  const file = join(source, 'main.py')
  writeFileSync(file, 'def first():\n    return 1\n')
  expect(python('report', '-f', source, '--database', path)).toBe(
    'No findings.\n',
  )
  const repository = listRepositories(database)[0]
  expect(repository.name).toBe('source')
  expect(repository.location).toBe(source)
  expect(
    getArchitecture(repository.id, database)!.artifact.nodes.some(
      (node) => node.name === 'first',
    ),
  ).toBe(true)
  writeFileSync(file, 'def replacement():\n    return 2\n')
  python('report', '--f', source, '--database', path)
  expect(listRepositories(database)).toHaveLength(1)
  expect(
    getArchitecture(repository.id, database)!.artifact.nodes.some(
      (node) => node.name === 'replacement',
    ),
  ).toBe(true)
})

test('Python src imports become dashboard arrows even when the report has no findings', () => {
  const source = join(directory, 'python-source')
  const app = join(source, 'src', 'app')
  mkdirSync(app, { recursive: true })
  writeFileSync(join(app, '__init__.py'), '')
  writeFileSync(
    join(app, 'main.py'),
    'from app import worker as w\ndef run():\n    w.work()\n',
  )
  writeFileSync(join(app, 'worker.py'), 'def work(): pass\n')
  expect(python('report', '-f', source, '--database', path)).toBe(
    'No findings.\n',
  )
  const repository = listRepositories(database)[0]
  const artifact = parseArtifact(
    getArchitecture(repository.id, database)!.artifact,
  )
  const graph = buildProjectGraph(artifact, {
    kind: 'folder',
    key: 'module:src/app',
  })
  expect(graph.edges).toHaveLength(1)
  expect(graph.edges[0]).toMatchObject({
    source: 'file:src/app/main.py',
    target: 'file:src/app/worker.py',
    relationships: { IMPORTS: 1, CALLS: 1 },
  })
})

test('indexed metrics survive Python/Bun storage and keep hidden test dependents', () => {
  const source = join(directory, 'impact-source')
  mkdirSync(source)
  writeFileSync(join(source, 'core.py'), 'def core():\n    return 1\n')
  writeFileSync(
    join(source, 'main.py'),
    'from core import core\ndef main():\n    return core()\n',
  )
  writeFileSync(
    join(source, 'test_main.py'),
    'from main import main\ndef test_main():\n    return main()\n',
  )
  python('report', '-f', source, '--database', path)
  const repository = listRepositories(database)[0]
  const artifact = parseArtifact(
    getArchitecture(repository.id, database)!.artifact,
  )
  const visible = hideTestFiles(artifact)
  const core = visible.nodes.find((node) => node.name === 'core.py')!
  expect(core.properties).toMatchObject({
    fanIn: 1,
    fanOut: 0,
    transitiveChangeImpact: 2,
  })
  expect(artifact.nodes.some((node) => node.name === 'test_main.py')).toBe(true)
  expect(visible.nodes.some((node) => node.name === 'test_main.py')).toBe(false)
  const graph = buildProjectGraph(visible, { kind: 'repository' })
  expect(
    graph.edges.filter((edge) => edge.target === core.stableKey),
  ).toHaveLength(1)
})

test('reading saved graph JSON preserves all fields', () => {
  const repository = registerRepository(
    { name: 'Legacy', location: 'local' },
    database,
  )
  const artifact: Artifact = {
    schemaVersion: 2,
    repository: { name: 'Legacy' },
    nodes: [],
    edges: [],
    future: { values: [1, null, 'value'] },
  }
  database
    .query('INSERT INTO repository_graphs VALUES (?, ?, ?)')
    .run(repository.id, JSON.stringify(artifact), 123)
  expect(getArchitecture(repository.id, database)).toEqual({
    repositoryId: repository.id,
    artifact,
    importedAt: 123,
  })
})

test('error responses remain JSON with the expected status', async () => {
  let error: unknown
  try {
    getArchitecture('unknown', database)
  } catch (caught) {
    error = caught
  }
  const response = repositoryErrorResponse(error)
  expect(response.status).toBe(404)
  expect(await response.json()).toEqual({ error: 'Repository not found' })
})
