import { homedir } from 'node:os'
import { join } from 'node:path'
import { expect, test } from 'bun:test'
import { defaultDatabasePath } from './database.servers'

test('shared default database lives in user data with explicit overrides', () => {
  const databasePath = process.env.DATABASE_PATH
  const dataHome = process.env.XDG_DATA_HOME
  try {
    delete process.env.DATABASE_PATH
    delete process.env.XDG_DATA_HOME
    expect(defaultDatabasePath()).toBe(
      join(homedir(), '.local/share/atlas/atlas.sqlite'),
    )
    process.env.XDG_DATA_HOME = '/custom/user-data'
    expect(defaultDatabasePath()).toBe(
      '/custom/user-data/atlas/atlas.sqlite',
    )
    process.env.DATABASE_PATH = '/custom/database.sqlite'
    expect(defaultDatabasePath()).toBe('/custom/database.sqlite')
  } finally {
    if (databasePath === undefined) delete process.env.DATABASE_PATH
    else process.env.DATABASE_PATH = databasePath
    if (dataHome === undefined) delete process.env.XDG_DATA_HOME
    else process.env.XDG_DATA_HOME = dataHome
  }
})
