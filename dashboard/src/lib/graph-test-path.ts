/** Conventional test paths, at any depth, including monorepo packages. */
export function isTestPath(path: string, folder = false): boolean {
  const parts = path.replaceAll('\\', '/').split('/').filter(Boolean)
  const directories = folder ? parts : parts.slice(0, -1)
  if (
    directories.some((part) =>
      /^(?:test|tests|spec|specs|__tests__|integrationTest|integrationTests|androidTest|testFixtures)$/.test(
        part,
      ),
    )
  )
    return true
  if (folder) return false
  const name = parts.at(-1) ?? ''
  return (
    /\.(?:test|spec)\.[^.]+$/.test(name) ||
    /^(?:test_.+|.+_test)\.py$/.test(name) ||
    /_test\.(?:go|exs|rb|rs|dart)$/.test(name) ||
    /_spec\.rb$/.test(name) ||
    /.+(?:Test|Tests|TestCase|Spec)\.(?:java|kt|kts|scala|groovy|cs)$/.test(
      name,
    )
  )
}
