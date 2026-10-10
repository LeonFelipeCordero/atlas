import { posix } from 'node:path'
import ts from 'typescript-ast'

export const repositoryRoot = 'src/lib/persistence/repositories/'
export const serviceFile = 'src/lib/repositories.servers.ts'
const infrastructure = `${repositoryRoot}connection.ts`
const factory = `${repositoryRoot}factory`
const factoryNames = new Set([
  'createRepositoryContext',
  'repositoryDatabasePath',
])
const drivers =
  /^(?:bun:sqlite|node:sqlite|better-sqlite3|sqlite3|sqlite|drizzle-orm|@prisma\/client|prisma|typeorm|sequelize|knex|kysely|pg|postgres|mysql2?|mongodb)(?:\/|$)/
const rawMethods = new Set([
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
const ormMethods = new Set([
  'select',
  'selectDistinct',
  'insert',
  'transaction',
])
const statement =
  /^\s*(?:select\s+.+\s+from\b|insert\s+into\b|update\s+.+\s+set\b|delete\s+from\b|with\s+(?:recursive\s+)?\w+\s*\(|pragma\s|create\s+(?:table|index)\b|alter\s+table\b|drop\s+(?:table|index)\b)/i
const rawOrmNames = new Set([
  'sql',
  'SQL',
  'StringChunk',
  'SQLWrapper',
  'SQLChunk',
])
const rawOrmMembers = new Set([
  'queryChunks',
  'getSQL',
  'toQuery',
  'buildQueryFromSourceParams',
  'inlineParams',
  'shouldInlineParams',
  'append',
])
const pragmas = new Set([
  'PRAGMA busy_timeout = 30000',
  'PRAGMA foreign_keys = ON',
])

function modulePath(file: string, name: string) {
  return name.startsWith('@/')
    ? posix.normalize(`src/${name.slice(2)}`)
    : name.startsWith('.')
      ? posix.normalize(posix.join(posix.dirname(file), name))
      : name
}
function moduleReferences(node: ts.Node): Array<ts.Expression | ts.TypeNode> {
  if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node))
    return node.moduleSpecifier ? [node.moduleSpecifier] : []
  if (
    ts.isImportEqualsDeclaration(node) &&
    ts.isExternalModuleReference(node.moduleReference)
  )
    return node.moduleReference.expression
      ? [node.moduleReference.expression]
      : []
  if (ts.isImportTypeNode(node)) return [node.argument]
  if (
    ts.isCallExpression(node) &&
    (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
      (ts.isIdentifier(node.expression) &&
        ['require', 'load', 'loader'].includes(node.expression.text)))
  )
    return node.arguments.length ? [node.arguments[0]] : []
  return []
}
function literal(node: ts.Node): string | undefined {
  if (ts.isLiteralTypeNode(node)) return literal(node.literal)
  return ts.isStringLiteralLike(node) ? node.text : undefined
}
function property(node: ts.Node): string | undefined {
  if (ts.isPropertyAccessExpression(node)) return node.name.text
  if (ts.isElementAccessExpression(node) && node.argumentExpression)
    return literal(node.argumentExpression)
  if (
    ts.isMethodDeclaration(node) ||
    ts.isPropertyAssignment(node) ||
    ts.isShorthandPropertyAssignment(node) ||
    ts.isPropertyDeclaration(node) ||
    ts.isMethodSignature(node) ||
    ts.isPropertySignature(node)
  )
    return ts.isComputedPropertyName(node.name)
      ? literal(node.name.expression)
      : (literal(node.name) ?? node.name.getText())
  if (ts.isBindingElement(node))
    return node.propertyName && ts.isStringLiteralLike(node.propertyName)
      ? node.propertyName.text
      : (node.propertyName?.getText() ?? node.name.getText())
  return undefined
}
function allowedPragma(node: ts.Node, file: string) {
  if (
    file !== infrastructure ||
    !ts.isStringLiteral(node) ||
    !pragmas.has(node.text)
  )
    return false
  const call = node.parent
  return (
    ts.isCallExpression(call) &&
    ts.isPropertyAccessExpression(call.expression) &&
    call.expression.expression.getText() === 'driver' &&
    call.expression.name.text === 'run' &&
    call.arguments.length === 1
  )
}

function checkModule(
  file: string,
  node: ts.Node,
  name: string,
  report: (node: ts.Node, message: string) => void,
) {
  const repository = file.startsWith(repositoryRoot)
  const resolved = modulePath(file, name)
  const repositoryModule =
    resolved.includes(repositoryRoot) ||
    resolved.endsWith(repositoryRoot.slice(0, -1))
  if (
    /(?:^|\/)repository-ports(?:\.ts)?$/.test(resolved) &&
    !repository &&
    file !== serviceFile
  )
    report(node, 'repository port dependency outside service/repository')
  if (repositoryModule && file === serviceFile) {
    const declaration = node.parent
    const clause = ts.isImportDeclaration(declaration)
      ? declaration.importClause
      : undefined
    const named = clause?.namedBindings
    if (
      resolved.replace(/\.ts$/, '') !== factory ||
      clause?.name ||
      !named ||
      !ts.isNamedImports(named) ||
      named.elements.some(
        (binding) =>
          !factoryNames.has((binding.propertyName ?? binding.name).text),
      )
    )
      report(node, 'service may import only exact domain repository factory')
  }
  if (
    (repositoryModule ||
      /(?:database|(?:graph|repository)-store)(?:\.servers)?(?:\.ts)?$/.test(
        resolved,
      )) &&
    !repository &&
    file !== serviceFile
  )
    report(node, 'repository import outside service')
  if (drivers.test(name) && !repository)
    report(node, 'driver/ORM import outside repository')
  if (
    drivers.test(name) &&
    !name.startsWith('drizzle-orm') &&
    file !== infrastructure
  )
    report(node, 'driver import outside exact infrastructure file')
  if (name === 'bun' || name === 'node:module' || name === 'module')
    report(node, 'alternate driver/module loader bypass')
  if (/\.(?:sqlite|sqlite3|db)$/.test(name))
    report(node, 'database file import bypass')
  if (ts.isExportDeclaration(node.parent) && repositoryModule)
    report(node, 'repository reexport')
  if (name.startsWith('drizzle-orm')) checkOrmModule(node, report)
}

function checkOrmModule(node: ts.Node, report: Reporter) {
  const declaration = node.parent
  if (
    ts.isImportDeclaration(declaration) &&
    declaration.importClause?.namedBindings &&
    ts.isNamespaceImport(declaration.importClause.namedBindings)
  )
    report(node, 'raw ORM namespace import')
  if (ts.isExportDeclaration(declaration) && !declaration.exportClause)
    report(node, 'raw ORM wildcard reexport')
  const visit = (child: ts.Node) => {
    if (ts.isIdentifier(child) && rawOrmNames.has(child.text))
      report(child, 'raw ORM SQL import/type/reexport')
    ts.forEachChild(child, visit)
  }
  visit(declaration)
}

function rootName(node: ts.Expression): string | undefined {
  if (ts.isIdentifier(node)) return node.text
  if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node))
    return rootName(node.expression)
  return undefined
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
  const factories = new Set(['createRepositoryContext', 'openConnection'])
  const visit = (node: ts.Node) => {
    if (
      ts.isImportSpecifier(node) &&
      factories.has((node.propertyName ?? node.name).text)
    )
      factories.add(node.name.text)
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.initializer
    ) {
      const value = node.initializer
      if (
        sensitive.has(rootName(value) ?? '') ||
        (ts.isCallExpression(value) &&
          factories.has(rootName(value.expression) ?? ''))
      )
        sensitive.add(node.name.text)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return sensitive
}

type Reporter = (node: ts.Node, message: string) => void
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
function accessOwner(node: ts.Node): ts.Expression | undefined {
  if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node))
    return node.expression
  if (ts.isBindingElement(node) && ts.isVariableDeclaration(node.parent.parent))
    return node.parent.parent.initializer
  return undefined
}

function checkAccess(
  node: ts.Node,
  file: string,
  sensitive: Set<string>,
  report: Reporter,
) {
  const repository = file.startsWith(repositoryRoot)
  const member = property(node)
  const pragmaCall =
    member === 'run' &&
    ts.isCallExpression(node.parent) &&
    node.parent.arguments.length === 1 &&
    allowedPragma(node.parent.arguments[0], file)
  if (member && rawMethods.has(member) && !pragmaCall)
    report(node, 'raw driver/query access')
  if (member && ormMethods.has(member) && !repository)
    report(node, 'ORM/driver call outside repository')
  if (
    file === infrastructure &&
    member &&
    (ormMethods.has(member) || ['update', 'delete'].includes(member))
  )
    report(node, 'connection infrastructure cannot query domain data')
  if (member === 'SQL') report(node, 'Bun SQL driver bypass')
  if (member && (rawOrmMembers.has(member) || rawOrmNames.has(member)))
    report(node, 'raw ORM query chunk/wrapper access')
  if (ts.isIdentifier(node) && rawOrmNames.has(node.text))
    report(node, 'raw ORM SQL constructor/type')
  if (
    member &&
    ['register', 'list', 'view'].includes(member) &&
    ts.isPropertyAccessExpression(node) &&
    sensitive.has(rootName(node.expression) ?? '') &&
    !repository &&
    file !== serviceFile
  )
    report(node, 'repository operation outside service')
  if (
    ts.isBindingElement(node) &&
    node.propertyName &&
    ts.isComputedPropertyName(node.propertyName) &&
    accessOwner(node) &&
    sensitive.has(rootName(accessOwner(node)!) ?? '')
  )
    report(node, 'computed persistence destructuring bypass')
  const computed =
    ts.isElementAccessExpression(node) &&
    literal(node.argumentExpression) === undefined
  if (computed && sensitive.has(rootName(node.expression) ?? ''))
    report(node, 'computed persistence/reflection binding bypass')
  if (
    member &&
    ['update', 'delete'].includes(member) &&
    accessOwner(node) &&
    sensitive.has(rootName(accessOwner(node)!) ?? '') &&
    !repository
  )
    report(node, 'ORM write outside repository')
  if (
    computed &&
    (ts.isCallExpression(node.parent) || ts.isNewExpression(node.parent)) &&
    node.parent.expression === node
  )
    report(node, 'computed method/constructor bypass')
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
  const repository = file.startsWith(repositoryRoot)
  const errors: Array<string> = []
  const report = (node: ts.Node, message: string) =>
    errors.push(
      `${file}:${source.getLineAndCharacterOfPosition(node.getStart()).line + 1}: ${message}`,
    )
  const sensitive = sensitiveBindings(source)
  const visit = (node: ts.Node) => {
    for (const reference of moduleReferences(node)) {
      const name = literal(reference)
      if (name === undefined)
        report(reference, 'nonliteral module loading bypass')
      else checkModule(file, reference, name, report)
    }
    checkSql(node, file, report)
    checkAccess(node, file, sensitive, report)
    if (
      ts.isIdentifier(node) &&
      ['eval', 'Function', 'require', 'createRequire', 'Reflect'].includes(
        node.text,
      )
    )
      report(node, 'runtime code/module loader/reflection bypass')
    if (
      ts.isIdentifier(node) &&
      factoryNames.has(node.text) &&
      !repository &&
      file !== serviceFile
    )
      report(node, 'repository factory use outside service')
    if (
      ts.isIdentifier(node) &&
      [
        'RepositoryStore',
        'GraphStore',
        'GraphQueries',
        'openConnection',
        'AppDatabase',
        'Database',
        'DatabaseSync',
      ].includes(node.text) &&
      !repository
    )
      report(node, 'repository/connection implementation outside repository')
    ts.forEachChild(node, visit)
  }
  visit(source)
  return errors
}

/** Follow inferred/public types too: a service cannot reexport or return a repository/ORM handle. */
export function auditServiceExports(
  program: ts.Program,
  source: ts.SourceFile,
): Array<string> {
  const checker = program.getTypeChecker()
  const symbol = checker.getSymbolAtLocation(source)
  if (!symbol) return []
  const seen = new Set<ts.Type>()
  const errors: Array<string> = []
  const inspect = (type: ts.Type, name: string) => {
    if (seen.has(type)) return
    seen.add(type)
    if (type.flags & (ts.TypeFlags.Any | ts.TypeFlags.Unknown)) {
      errors.push(`${name}: opaque service export`)
      return
    }
    const declarations = [
      ...(type.getSymbol()?.declarations ?? []),
      ...(type.aliasSymbol?.declarations ?? []),
    ]
    if (
      declarations.some(
        (node) =>
          ts.isTypeAliasDeclaration(node) &&
          node.name.text === 'RepositoryPort',
      ) ||
      declarations.some(
        (node) =>
          (ts.isClassDeclaration(node) ||
            ts.isInterfaceDeclaration(node) ||
            ts.isTypeAliasDeclaration(node) ||
            ts.isFunctionDeclaration(node)) &&
          /persistence\/repositories\/|node_modules\/(?:drizzle-orm|bun-types\/sqlite)/.test(
            node.getSourceFile().fileName,
          ),
      )
    ) {
      errors.push(`${name}: persistence handle escapes service`)
      return
    }
    if (type.isUnionOrIntersection())
      type.types.forEach((part) => inspect(part, name))
    // Only walk application-defined objects; built-in Error/Array/Map members are not domain handles.
    if (
      declarations.some((node) =>
        node.getSourceFile().fileName.includes('/src/'),
      )
    )
      type
        .getProperties()
        .filter((member) =>
          member.declarations?.some((node) =>
            node.getSourceFile().fileName.includes('/src/'),
          ),
        )
        .forEach((member) =>
          inspect(checker.getTypeOfSymbolAtLocation(member, source), name),
        )
    const signatures = [
      ...type.getCallSignatures(),
      ...type.getConstructSignatures(),
    ]
    signatures.forEach((signature) => {
      inspect(signature.getReturnType(), name)
      signature.parameters.forEach((parameter) => {
        const argument = checker.getTypeOfSymbolAtLocation(parameter, source)
        if (!(argument.flags & ts.TypeFlags.Unknown)) inspect(argument, name)
      })
    })
    const arguments_ = [
      ...(type.aliasTypeArguments ?? []),
      ...(type.flags & ts.TypeFlags.Object &&
      (type as ts.ObjectType).objectFlags & ts.ObjectFlags.Reference
        ? checker.getTypeArguments(type as ts.TypeReference)
        : []),
    ]
    arguments_
      .filter(
        (argument) =>
          type.aliasSymbol?.name !== 'Record' ||
          !(argument.flags & ts.TypeFlags.Unknown),
      )
      .forEach((argument) => inspect(argument, name))
  }
  checker.getExportsOfModule(symbol).forEach((exported) => {
    seen.clear()
    inspect(
      exported.flags & (ts.SymbolFlags.TypeAlias | ts.SymbolFlags.Interface)
        ? checker.getDeclaredTypeOfSymbol(exported)
        : checker.getTypeOfSymbolAtLocation(exported, source),
      exported.name,
    )
  })
  return errors
}
