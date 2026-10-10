import { defaultDatabasePath, openConnection } from './connection'
import { GraphStore } from './graph-store'
import { RepositoryStore } from './repository-store'
import type { RepositoryPort } from '../../repository-ports'

/** Only service factories may call this. ORM/driver handles remain captured inside repositories. */
export function createRepositoryContext(path?: string): RepositoryPort {
  const connection = openConnection(path)
  const repositories = new RepositoryStore(connection.database)
  const graphs = new GraphStore(connection.database)
  return {
    register: (id, name, location, createdAt) =>
      repositories.register(id, name, location, createdAt),
    list: () => repositories.list(),
    view: (id, scope) => graphs.view(id, scope),
    close: () => connection.close(),
  }
}

export const repositoryDatabasePath = () => defaultDatabasePath()
