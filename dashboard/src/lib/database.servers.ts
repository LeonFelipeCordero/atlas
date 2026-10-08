import { homedir } from 'node:os'
import { join, resolve } from 'node:path'
import { Database } from 'bun:sqlite'

export type AppDatabase = Database

export const defaultDatabasePath = () =>
  process.env.DATABASE_PATH ||
  join(
    process.env.XDG_DATA_HOME || join(homedir(), '.local/share'),
    'atlas/atlas.sqlite',
  )

/** Python creates and migrates the shared database before the UI starts. */
export function openDatabase(path = defaultDatabasePath()) {
  const database = new Database(resolve(path), {
    readwrite: true,
    create: false,
    strict: true,
  })
  database.run('PRAGMA busy_timeout = 30000')
  database.run('PRAGMA foreign_keys = ON')
  return database
}

let database: AppDatabase | undefined
export const getDatabase = () => (database ??= openDatabase())
