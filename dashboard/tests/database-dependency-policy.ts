import ts from 'typescript-ast'
import { repositoryRoot, serviceFile } from './database-architecture'

function ownsRepositoryDependencies(file: string) {
  const normalized = file.replaceAll('\\', '/')
  return (
    normalized.includes(`/${repositoryRoot}`) ||
    normalized.startsWith(repositoryRoot) ||
    normalized.endsWith(`/${serviceFile}`) ||
    normalized === serviceFile
  )
}

function applicationDeclaration(node: ts.Node) {
  return /(?:^|\/)src\//.test(node.getSourceFile().fileName)
}

function structuralPort(type: ts.Type, checker: ts.TypeChecker) {
  return ['register', 'list', 'view', 'close'].every((name) => {
    const member = type.getProperty(name)
    const declaration = member?.valueDeclaration ?? member?.declarations?.[0]
    return (
      member &&
      declaration &&
      checker.getTypeOfSymbolAtLocation(member, declaration).getCallSignatures()
        .length > 0
    )
  })
}

function referencedTypes(type: ts.Type, checker: ts.TypeChecker) {
  const references =
    type.flags & ts.TypeFlags.Object &&
    (type as ts.ObjectType).objectFlags & ts.ObjectFlags.Reference
      ? checker.getTypeArguments(type as ts.TypeReference)
      : []
  return [...(type.aliasTypeArguments ?? []), ...references]
}

function dependencyBinding(node: ts.Node) {
  return (
    ts.isParameter(node) ||
    ts.isVariableDeclaration(node) ||
    ts.isPropertyDeclaration(node) ||
    ts.isPropertyAccessExpression(node) ||
    ts.isElementAccessExpression(node)
  )
}

function dependencyInspector(checker: ts.TypeChecker) {
  const inspect = (type: ts.Type, seen = new Set<ts.Type>()): boolean => {
    if (
      seen.has(type) ||
      type.flags & (ts.TypeFlags.Any | ts.TypeFlags.Unknown)
    )
      return false
    seen.add(type)
    const declarations = [
      ...(type.getSymbol()?.declarations ?? []),
      ...(type.aliasSymbol?.declarations ?? []),
    ]
    if (
      declarations.some((node) =>
        /(?:^|\/)repository-ports\.ts$/.test(node.getSourceFile().fileName),
      )
    )
      return true
    if (type.isUnionOrIntersection())
      return type.types.some((part) => inspect(part, seen))
    // Structural aliases and inferred factory results are ports too, not just named types.
    if (structuralPort(type, checker)) return true
    if (
      referencedTypes(type, checker).some((argument) => inspect(argument, seen))
    )
      return true
    if (
      [...type.getCallSignatures(), ...type.getConstructSignatures()].some(
        (signature) =>
          inspect(signature.getReturnType(), seen) ||
          signature.parameters.some(
            (parameter) =>
              parameter.valueDeclaration &&
              inspect(
                checker.getTypeOfSymbolAtLocation(
                  parameter,
                  parameter.valueDeclaration,
                ),
                seen,
              ),
          ),
      )
    )
      return true
    return type.getProperties().some((member) => {
      const declaration = member.declarations?.find(applicationDeclaration)
      return (
        declaration &&
        inspect(checker.getTypeOfSymbolAtLocation(member, declaration), seen)
      )
    })
  }
  return inspect
}

function argumentValue(node: ts.Expression): ts.Expression {
  return ts.isAsExpression(node) ||
    ts.isTypeAssertionExpression(node) ||
    ts.isParenthesizedExpression(node) ||
    ts.isSatisfiesExpression(node)
    ? argumentValue(node.expression)
    : node
}

function dependencyInitializer(symbol: ts.Symbol) {
  const declaration = symbol.valueDeclaration
  return declaration &&
    (ts.isVariableDeclaration(declaration) ||
      ts.isPropertyDeclaration(declaration))
    ? declaration.initializer
    : undefined
}

function dependencyAssignments(source: ts.SourceFile, checker: ts.TypeChecker) {
  const assignments = new Map<ts.Symbol, Array<ts.Expression>>()
  const visit = (node: ts.Node) => {
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.EqualsToken
    ) {
      const symbol = checker.getSymbolAtLocation(node.left)
      if (symbol)
        assignments.set(symbol, [
          ...(assignments.get(symbol) ?? []),
          node.right,
        ])
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return assignments
}

function valueInspector(
  checker: ts.TypeChecker,
  containsDependency: (type: ts.Type) => boolean,
  source: ts.SourceFile,
) {
  const assignments = dependencyAssignments(source, checker)
  const inspect = (
    node: ts.Expression,
    seen = new Set<ts.Symbol>(),
  ): boolean => {
    const value = argumentValue(node)
    if (containsDependency(checker.getTypeAtLocation(value))) return true
    const symbol = checker.getSymbolAtLocation(value)
    if (!symbol || seen.has(symbol)) return false
    seen.add(symbol)
    const initializer = dependencyInitializer(symbol)
    const values = [
      ...(assignments.get(symbol) ?? []),
      ...(initializer ? [initializer] : []),
    ]
    return values.some((value) => inspect(value, seen))
  }
  return inspect
}

function externalCall(
  node: ts.CallExpression | ts.NewExpression,
  checker: ts.TypeChecker,
) {
  const declaration = checker.getResolvedSignature(node)?.declaration
  return (
    !declaration ||
    !ownsRepositoryDependencies(declaration.getSourceFile().fileName)
  )
}

/** Type/dependency check across the program, including private helpers and constructors. */
export function auditRepositoryDependencies(
  program: ts.Program,
  source: ts.SourceFile,
) {
  const checker = program.getTypeChecker()
  const containsDependency = dependencyInspector(checker)
  const containsValue = valueInspector(checker, containsDependency, source)
  const owner = ownsRepositoryDependencies(source.fileName)
  const errors: Array<string> = []
  const report = (node: ts.Node, message: string) =>
    errors.push(
      `${source.fileName}:${source.getLineAndCharacterOfPosition(node.getStart()).line + 1}: ${message}`,
    )
  const visit = (node: ts.Node) => {
    if (
      !owner &&
      dependencyBinding(node) &&
      containsDependency(checker.getTypeAtLocation(node))
    )
      report(node, 'repository dependency outside service/repository')
    if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
      const dependency = node.arguments?.some((argument) =>
        containsValue(argument),
      )
      if (dependency && externalCall(node, checker))
        report(
          node,
          'repository dependency delegated outside service/repository',
        )
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return errors
}
