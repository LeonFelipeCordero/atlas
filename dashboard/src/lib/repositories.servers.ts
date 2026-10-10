import {
  createRepositoryContext,
  repositoryDatabasePath,
} from './persistence/repositories/factory'
import { GraphScopeError } from './project-graph'
import type { GraphScope } from './project-graph-types'
import type { RepositoryPort } from './repository-ports'

export class RepositoryError extends Error {
  constructor(
    message: string,
    public readonly status: 400 | 404 | 409,
  ) {
    super(message)
    this.name = 'RepositoryError'
  }
}

const requiredText = (value: unknown, field: string, maxLength: number) => {
  if (typeof value !== 'string' || !value.trim())
    throw new RepositoryError(`${field} is required`, 400)
  const text = value.trim()
  if (text.length > maxLength)
    throw new RepositoryError(
      `${field} must be at most ${maxLength} characters`,
      400,
    )
  return text
}

function register(store: RepositoryPort, input: unknown) {
  if (!input || typeof input !== 'object' || Array.isArray(input))
    throw new RepositoryError('Expected an object with name and location', 400)
  const data = input as Record<string, unknown>
  const name = requiredText(data.name, 'name', 200)
  const location = requiredText(data.location, 'location', 4096)
  const repository = store.register({
    id: crypto.randomUUID(),
    name,
    location,
    createdAt: Date.now(),
  })
  if (!repository)
    throw new RepositoryError('A repository with this name already exists', 409)
  return repository
}

/** Service owns repository construction/lifetime. Consumers receive only DTOs and operations. */
export function createRepositoryService(path?: string) {
  const repository = createRepositoryContext(path)
  return {
    registerRepository: (input: unknown) => register(repository, input),
    listRepositories: () => repository.list(),
    getArchitecture(
      repositoryId: string,
      scope: GraphScope = { kind: 'repository' },
    ) {
      const id = requiredText(repositoryId, 'repositoryId', 200)
      const graph = repository.view(id, scope)
      if (graph === undefined)
        throw new RepositoryError('Repository not found', 404)
      return graph
    },
    close: () => repository.close(),
  }
}

export type RepositoryService = ReturnType<typeof createRepositoryService>
export const defaultDatabasePath = () => repositoryDatabasePath()
let service: RepositoryService | undefined
const getService = () => (service ??= createRepositoryService())
export const registerRepository = (input: unknown) =>
  getService().registerRepository(input)
export const listRepositories = () => getService().listRepositories()
export const getArchitecture = (id: string, scope?: GraphScope) =>
  getService().getArchitecture(id, scope)

export function architectureScope(parameters: URLSearchParams): GraphScope {
  const kind = parameters.get('kind') ?? 'repository'
  if (kind === 'repository') return { kind }
  if (kind !== 'folder' && kind !== 'file')
    throw new RepositoryError('Invalid graph scope', 400)
  return { kind, key: requiredText(parameters.get('key'), 'key', 4096) }
}

export const repositoryErrorResponse = (error: unknown) => {
  if (error instanceof GraphScopeError)
    return Response.json({ error: error.message }, { status: 400 })
  if (error instanceof RepositoryError)
    return Response.json({ error: error.message }, { status: error.status })
  console.error(error)
  return Response.json({ error: 'Internal server error' }, { status: 500 })
}
