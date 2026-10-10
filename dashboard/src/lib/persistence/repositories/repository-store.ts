import { eq } from 'drizzle-orm'
import { repositories, repositoryGraphs } from './schema'
import type { AppDatabase } from './connection'

/** Shared-file access only; schema and graph writes belong to Python. */
export class RepositoryStore {
  constructor(private readonly database: AppDatabase) {}

  register(id: string, name: string, location: string, createdAt: number) {
    const row = this.database
      .insert(repositories)
      .values({ id, name, location, createdAt })
      .onConflictDoNothing()
      .returning()
      .get()
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
