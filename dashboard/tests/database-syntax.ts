import ts from 'typescript-ast'
import { infrastructure, pragmas } from './database-policy'

export type Reporter = (node: ts.Node, message: string) => void

function loaderCall(node: ts.Node): node is ts.CallExpression {
  if (!ts.isCallExpression(node)) return false
  return (
    node.expression.kind === ts.SyntaxKind.ImportKeyword ||
    (ts.isIdentifier(node.expression) &&
      ['require', 'load', 'loader'].includes(node.expression.text))
  )
}
export function moduleReferences(
  node: ts.Node,
): Array<ts.Expression | ts.TypeNode> {
  if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node))
    return node.moduleSpecifier ? [node.moduleSpecifier] : []
  if (ts.isImportEqualsDeclaration(node)) return importEqualsReferences(node)
  if (ts.isImportTypeNode(node)) return [node.argument]
  if (loaderCall(node)) return node.arguments.length ? [node.arguments[0]] : []
  return []
}
function importEqualsReferences(node: ts.ImportEqualsDeclaration) {
  if (!ts.isExternalModuleReference(node.moduleReference)) return []
  return node.moduleReference.expression
    ? [node.moduleReference.expression]
    : []
}
export function literal(node: ts.Node): string | undefined {
  if (ts.isLiteralTypeNode(node)) return literal(node.literal)
  return ts.isStringLiteralLike(node) ? node.text : undefined
}
function namedProperty(
  node: ts.Node,
): node is ts.Node & { name: ts.PropertyName } {
  return (
    ts.isMethodDeclaration(node) ||
    ts.isPropertyAssignment(node) ||
    ts.isShorthandPropertyAssignment(node) ||
    ts.isPropertyDeclaration(node) ||
    ts.isMethodSignature(node) ||
    ts.isPropertySignature(node)
  )
}
function bindingProperty(node: ts.BindingElement) {
  return node.propertyName && ts.isStringLiteralLike(node.propertyName)
    ? node.propertyName.text
    : (node.propertyName?.getText() ?? node.name.getText())
}
export function property(node: ts.Node): string | undefined {
  if (ts.isPropertyAccessExpression(node)) return node.name.text
  if (ts.isElementAccessExpression(node))
    return literal(node.argumentExpression)
  if (namedProperty(node))
    return ts.isComputedPropertyName(node.name)
      ? literal(node.name.expression)
      : (literal(node.name) ?? node.name.getText())
  if (ts.isBindingElement(node)) return bindingProperty(node)
  return undefined
}
export function allowedPragma(node: ts.Node, file: string) {
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
export function rootName(node: ts.Expression): string | undefined {
  if (ts.isIdentifier(node)) return node.text
  if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node))
    return rootName(node.expression)
  return undefined
}
export function accessOwner(node: ts.Node): ts.Expression | undefined {
  if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node))
    return node.expression
  if (ts.isBindingElement(node) && ts.isVariableDeclaration(node.parent.parent))
    return node.parent.parent.initializer
  return undefined
}
