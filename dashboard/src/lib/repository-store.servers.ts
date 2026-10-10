import type { AppDatabase } from './database.servers'
import type { Repository } from './api'

/** Shared-file access only; schema and graph writes belong to Python. */
export class RepositoryStore {
  constructor(private readonly database: AppDatabase) {}

  register({ id, name, location, createdAt }: Omit<Repository, 'importedAt'>) {
    return this.database
      .query<Repository, [string, string, string, number]>(
        `
      INSERT INTO repositories (id, name, location, created_at) VALUES (?, ?, ?, ?)
      ON CONFLICT DO NOTHING
      RETURNING id, name, location, created_at AS createdAt, NULL AS importedAt
    `,
      )
      .get(id, name, location, createdAt)
  }

  list() {
    return this.database
      .query<Repository, []>(
        `
      SELECT r.id, r.name, r.location, r.created_at AS createdAt,
        CASE WHEN g.graph_revision IS NOT NULL THEN g.imported_at END AS importedAt
      FROM repositories r LEFT JOIN repository_graphs g ON r.id = g.repository_id
      ORDER BY r.created_at, r.id
    `,
      )
      .all()
  }
}
