import type { AppDatabase } from './database.servers'
import type { ImportedGraph, Repository } from './api'

type StoredGraph = {
  repositoryId: string
  importedAt: number
  artifact: string
}

/** Shared-file access only; schema and graph writes belong to Python. */
export class RepositoryStore {
  constructor(private readonly database: AppDatabase) {}

  register(id: string, name: string, location: string, createdAt: number) {
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
      SELECT r.id, r.name, r.location, r.created_at AS createdAt, g.imported_at AS importedAt
      FROM repositories r LEFT JOIN repository_graphs g ON r.id = g.repository_id
      ORDER BY r.created_at, r.id
    `,
      )
      .all()
  }

  exists(id: string) {
    return (
      this.database
        .query<{ id: string }, [string]>(
          'SELECT id FROM repositories WHERE id = ?',
        )
        .get(id) !== null
    )
  }

  graph(id: string): ImportedGraph | null {
    const row = this.database
      .query<StoredGraph, [string]>(
        `
      SELECT repository_id AS repositoryId, imported_at AS importedAt, artifact
      FROM repository_graphs WHERE repository_id = ?
    `,
      )
      .get(id)
    return row ? { ...row, artifact: JSON.parse(row.artifact) } : null
  }
}
