import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const directory = mkdtempSync(join(tmpdir(), 'atlas-test-'))

process.env.DATABASE_PATH = join(directory, 'db')
process.on('exit', () => rmSync(directory, { recursive: true, force: true }))
