import type { Repository } from './api'
import type { Architecture } from './graph-data'
import type { GraphScope } from './project-graph-types'

/** Domain-only persistence protocol; no connection, ORM or repository implementation types. */
export type RepositoryPort = {
  register: (input: Omit<Repository, 'importedAt'>) => Repository | undefined
  list: () => Array<Repository>
  view: (id: string, scope: GraphScope) => Architecture | null | undefined
  close: () => void
}
