import { realpathSync } from 'node:fs'
import { homedir } from 'node:os'
import { isAbsolute } from 'node:path'
import { getDatabase } from './database.servers'
import { RepositoryStore } from './repository-store.servers'
import type { AppDatabase } from './database.servers'

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

const expandHome = (location: string) =>
  location.replace(/^~(?=\/|$)/, () => homedir())

function canonicalFolder(location: string) {
  const folder = expandHome(location)
  const absolute = isAbsolute(folder) ? folder : `${process.cwd()}/${folder}`
  try {
    // Resolve each symlink before the next segment can collapse a parent (..).
    return absolute
      .split('/')
      .reduce((parent, part) => realpathSync(`${parent}/${part}`), '/')
  } catch (error) {
    if (
      !['ENOENT', 'ENOTDIR'].includes(
        (error as NodeJS.ErrnoException).code ?? '',
      )
    )
      throw error
    // Keep unresolved paths intact for Python's later non-strict resolution.
    return absolute
  }
}

export function registerRepository(
  input: unknown,
  database: AppDatabase = getDatabase(),
) {
  if (!input || typeof input !== 'object' || Array.isArray(input))
    throw new RepositoryError('Expected an object with name and location', 400)
  const data = input as Record<string, unknown>
  const name = requiredText(data.name, 'name', 200)
  const location = requiredText(data.location, 'location', 4096)
  if (location.includes('://'))
    throw new RepositoryError(
      'Use a local folder path; URLs cannot be indexed',
      400,
    )
  const store = new RepositoryStore(database)
  const folder = canonicalFolder(location)
  if (
    store
      .list()
      .some(
        (entry) =>
          isAbsolute(expandHome(entry.location)) &&
          canonicalFolder(entry.location) === folder,
      )
  )
    throw new RepositoryError(
      'A repository with this folder already exists',
      409,
    )
  const repository = store.register(
    crypto.randomUUID(),
    name,
    folder,
    Date.now(),
  )
  if (!repository)
    throw new RepositoryError('A repository with this name already exists', 409)
  return repository
}

export const listRepositories = (database: AppDatabase = getDatabase()) =>
  new RepositoryStore(database).list()

export function getArchitecture(
  repositoryId: string,
  database: AppDatabase = getDatabase(),
) {
  const id = requiredText(repositoryId, 'repositoryId', 200)
  const store = new RepositoryStore(database)
  if (!store.exists(id)) throw new RepositoryError('Repository not found', 404)
  return store.graph(id)
}

export const repositoryErrorResponse = (error: unknown) => {
  if (error instanceof RepositoryError)
    return Response.json({ error: error.message }, { status: error.status })
  console.error(error)
  return Response.json({ error: 'Internal server error' }, { status: 500 })
}
