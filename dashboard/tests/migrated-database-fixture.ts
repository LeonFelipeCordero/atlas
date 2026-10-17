import { copyFileSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterAll, beforeAll } from 'bun:test'
import { Database } from 'bun:sqlite'

// Copy a closed Python-migrated template, never a database shared by tests.
export function migratedDatabaseFixture() {
  let directory: string
  let template: string
  beforeAll(() => {
    directory = mkdtempSync(join(tmpdir(), 'atlas-migrated-template-'))
    template = join(directory, 'template.sqlite')
    const result = Bun.spawnSync(
      [
        'uv',
        'run',
        '--project',
        fileURLToPath(new URL('../../atlas', import.meta.url)),
        'atlas-migrate',
      ],
      { env: { ...process.env, DATABASE_PATH: template } },
    )
    if (result.exitCode !== 0) throw new Error(result.stderr.toString())
    const database = new Database(template, { readwrite: true, create: false })
    try {
      database.exec('PRAGMA wal_checkpoint(TRUNCATE)')
    } finally {
      database.close()
    }
  })
  afterAll(() => {
    if (directory) rmSync(directory, { recursive: true, force: true })
  })
  return (path: string) => {
    mkdirSync(dirname(path), { recursive: true })
    copyFileSync(template, path)
  }
}
