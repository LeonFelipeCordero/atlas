export const repositoryRoot = 'src/lib/persistence/repositories/'
export const serviceFile = 'src/lib/repositories.servers.ts'
export const infrastructure = `${repositoryRoot}connection.ts`
export const factory = `${repositoryRoot}factory`
export const factoryNames = new Set([
  'createRepositoryContext',
  'repositoryDatabasePath',
])
export const drivers =
  /^(?:bun:sqlite|node:sqlite|better-sqlite3|sqlite3|sqlite|drizzle-orm|@prisma\/client|prisma|typeorm|sequelize|knex|kysely|pg|postgres|mysql2?|mongodb)(?:\/|$)/
export const rawMethods = new Set([
  'query',
  'prepare',
  'exec',
  'execute',
  'raw',
  'sql',
  'run',
  '$client',
  '$with',
  'getDatabase',
  'openDatabase',
  'getBuiltinModule',
  'getOwnPropertyDescriptor',
  'getOwnPropertyDescriptors',
  'getOwnPropertyNames',
  'getOwnPropertySymbols',
  'getPrototypeOf',
  'defineProperty',
  'defineProperties',
  'setPrototypeOf',
])
export const ormMethods = new Set([
  'select',
  'selectDistinct',
  'insert',
  'transaction',
])
export const statement =
  /^\s*(?:select\s+.+\s+from\b|insert\s+into\b|update\s+.+\s+set\b|delete\s+from\b|with\s+(?:recursive\s+)?\w+\s*\(|pragma\s|create\s+(?:table|index)\b|alter\s+table\b|drop\s+(?:table|index)\b)/i
export const rawOrmNames = new Set([
  'sql',
  'SQL',
  'StringChunk',
  'SQLWrapper',
  'SQLChunk',
])
export const rawOrmMembers = new Set([
  'queryChunks',
  'getSQL',
  'toQuery',
  'buildQueryFromSourceParams',
  'inlineParams',
  'shouldInlineParams',
  'append',
])
export const pragmas = new Set([
  'PRAGMA busy_timeout = 30000',
  'PRAGMA foreign_keys = ON',
])
