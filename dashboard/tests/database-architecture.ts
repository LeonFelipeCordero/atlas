import ts from 'typescript-ast'
import { checkAccess } from './database-access-policy'
import { checkModule } from './database-module-policy'
import {
  factoryNames,
  repositoryRoot,
  serviceFile,
  statement,
} from './database-policy'
import {
  allowedPragma,
  literal,
  moduleReferences,
  rootName,
} from './database-syntax'
import type { Reporter } from './database-syntax'

export { repositoryRoot, serviceFile } from './database-policy'
export { auditServiceExports } from './database-service-exports'

type Bindings = { sensitive: Set<string>; factories: Set<string> }
function sensitiveValue(
  value: ts.Expression,
  { sensitive, factories }: Bindings,
) {
  return (
    sensitive.has(rootName(value) ?? '') ||
    (ts.isCallExpression(value) &&
      factories.has(rootName(value.expression) ?? ''))
  )
}
function trackBinding(node: ts.Node, bindings: Bindings) {
  if (
    ts.isImportSpecifier(node) &&
    bindings.factories.has((node.propertyName ?? node.name).text)
  )
    bindings.factories.add(node.name.text)
  if (
    !ts.isVariableDeclaration(node) ||
    !ts.isIdentifier(node.name) ||
    !node.initializer
  )
    return
  if (sensitiveValue(node.initializer, bindings))
    bindings.sensitive.add(node.name.text)
}
function sensitiveBindings(source: ts.SourceFile) {
  const sensitive = new Set([
    'db',
    'database',
    'driver',
    'connection',
    'Bun',
    'Object',
    'globalThis',
    'service',
    'context',
    'store',
    'repository',
    'process',
  ])
  const bindings = {
    sensitive,
    factories: new Set(['createRepositoryContext', 'openConnection']),
  }
  const visit = (node: ts.Node) => {
    trackBinding(node, bindings)
    ts.forEachChild(node, visit)
  }
  visit(source)
  return sensitive
}
function checkSql(node: ts.Node, file: string, report: Reporter) {
  if (
    ts.isStringLiteralLike(node) &&
    statement.test(node.text) &&
    !allowedPragma(node, file)
  )
    report(node, 'raw SQL text')
  if (ts.isTemplateExpression(node) && statement.test(node.head.text))
    report(node, 'raw SQL template')
  if (ts.isTaggedTemplateExpression(node))
    report(node, 'tagged query/template bypass')
}
function checkIdentifier(node: ts.Node, file: string, report: Reporter) {
  if (!ts.isIdentifier(node)) return
  if (
    ['eval', 'Function', 'require', 'createRequire', 'Reflect'].includes(
      node.text,
    )
  )
    report(node, 'runtime code/module loader/reflection bypass')
  if (file.startsWith(repositoryRoot)) return
  if (factoryNames.has(node.text) && file !== serviceFile)
    report(node, 'repository factory use outside service')
  if (
    [
      'RepositoryStore',
      'GraphStore',
      'GraphQueries',
      'openConnection',
      'AppDatabase',
      'Database',
      'DatabaseSync',
    ].includes(node.text)
  )
    report(node, 'repository/connection implementation outside repository')
}
function checkReferences(node: ts.Node, file: string, report: Reporter) {
  for (const reference of moduleReferences(node)) {
    const name = literal(reference)
    if (name === undefined)
      report(reference, 'nonliteral module loading bypass')
    else checkModule(reference, { file, name, report })
  }
}
/** Syntax traversal, not grep: every import form, binding alias, and computed access is checked. */
export function auditSource(file: string, text: string): Array<string> {
  const source = ts.createSourceFile(
    file,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  )
  const errors: Array<string> = []
  const report = (node: ts.Node, message: string) =>
    errors.push(
      `${file}:${source.getLineAndCharacterOfPosition(node.getStart()).line + 1}: ${message}`,
    )
  const sensitive = sensitiveBindings(source)
  const visit = (node: ts.Node) => {
    checkReferences(node, file, report)
    checkSql(node, file, report)
    checkAccess(node, { file, sensitive, report })
    checkIdentifier(node, file, report)
    ts.forEachChild(node, visit)
  }
  visit(source)
  return errors
}
