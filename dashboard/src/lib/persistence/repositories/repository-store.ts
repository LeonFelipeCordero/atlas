import { eq } from 'drizzle-orm'
import { repositories, repositoryGraphs } from './schema'
import type { AppDatabase } from './connection'
import type { Repository } from '../../api'

/** Shared-file access only; schema and graph writes belong to Python. */
export class RepositoryStore {
  constructor(private readonly database: AppDatabase) {}

  register({ id, name, location, createdAt }: Omit<Repository, 'importedAt'>) {
    const row = this.database
      .insert(repositories)
      .values({ id, name, location, createdAt })
      .onConflictDoNothing()
      .returning()
      .all()
      .at(0)
    return row ? { ...row, importedAt: null } : undefined
  }

  list() {
    return this.database
      .select({
        id: repositories.id,
        name: repositories.name,
        location: repositories.location,
        createdAt: repositories.createdAt,
        graphRevision: repositoryGraphs.graphRevision,
        importedAt: repositoryGraphs.importedAt,
      })
      .from(repositories)
      .leftJoin(
        repositoryGraphs,
        eq(repositories.id, repositoryGraphs.repositoryId),
      )
      .orderBy(repositories.createdAt, repositories.id)
      .all()
      .map(({ graphRevision, importedAt, ...row }) => ({
        ...row,
        importedAt: graphRevision === null ? null : importedAt,
      }))
  }
}
