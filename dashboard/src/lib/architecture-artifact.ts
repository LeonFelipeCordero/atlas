export type NodeComplexity = {
  cyclomaticComplexity?: number
  baseCyclomaticComplexity?: number
  nestedCyclomaticComplexity?: number
  loopNestedComplexity?: number
  maxDecisionDepth?: number
}

export type NodeSizeMetrics = {
  lineCount?: number
  parameterCount?: number
}

export type NodeDependencyMetrics = {
  fanIn?: number
  fanOut?: number
  transitiveChangeImpact?: number
}

export type ArtifactNode = {
  stableKey: string
  type: string
  kind: string
  level: string
  name: string
  qualifiedName?: string
  path: string | null
  language: string | null
  parentStableKey: string | null
  ancestorStableKeys: Array<string>
  depth: number
  signature?: string | null
  startLine?: number | null
  startColumn?: number | null
  endLine?: number | null
  endColumn?: number | null
  properties?: Record<string, unknown> &
    NodeComplexity &
    NodeDependencyMetrics &
    NodeSizeMetrics
}

export type DirectEdge = {
  sourceStableKey: string
  targetStableKey: string
  type: string
  confidence: 'EXTRACTED' | 'INFERRED'
  path?: string | null
  line?: number | null
  evidence?: string | null
  sourceType?: string
  sourceKind?: string
  sourceLevel?: string
  targetType?: string
  targetKind?: string
  targetLevel?: string
}

export type CircularDependency = {
  id: string
  nodeStableKeys: Array<string>
  exampleCycle: Array<string>
  edges: Array<DirectEdge>
}

export type Artifact = {
  circularDependencies?: { version: 1; groups: Array<CircularDependency> }
  schemaVersion: 2
  repository: {
    name: string
    path?: string
    indexedAt?: string
    languages?: Array<string>
    [key: string]: unknown
  }
  nodes: Array<ArtifactNode>
  edges: Array<DirectEdge>
  // Precomputed views and reporting data are preserved, not used for navigation.
  views?: unknown
  stats?: unknown
  diagnostics?: unknown
  metadata?: unknown
  [key: string]: unknown
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
const isText = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0
const isTextArray = (value: unknown): value is Array<string> =>
  Array.isArray(value) && Array.from(value).every(isText)
const isNullableText = (value: unknown) =>
  value === null || typeof value === 'string'
const isInteger = (value: unknown, minimum: number) =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum

function requireValid(
  valid: boolean,
  location: string,
  expected: string,
): asserts valid {
  if (!valid) throw new Error(`Invalid artifact: ${location} ${expected}`)
}

function validatePositions(value: Record<string, unknown>, at: string) {
  for (const key of ['startLine', 'endLine', 'startColumn', 'endColumn']) {
    if (value[key] == null) continue
    requireValid(
      isInteger(value[key], key.endsWith('Line') ? 1 : 0),
      `${at}.${key}`,
      'must be a valid source position',
    )
  }
  validatePositionOrder(value as ArtifactNode, at)
}

function validatePositionOrder(node: ArtifactNode, at: string) {
  if (node.startLine != null && node.endLine != null) {
    requireValid(
      node.endLine >= node.startLine,
      `${at}.endLine`,
      'must not precede startLine',
    )
    if (
      node.startLine === node.endLine &&
      node.startColumn != null &&
      node.endColumn != null
    ) {
      requireValid(
        node.endColumn >= node.startColumn,
        `${at}.endColumn`,
        'must not precede startColumn',
      )
    }
  }
}

function validateNode(value: unknown, index: number): ArtifactNode {
  const at = `nodes[${index}]`
  requireValid(isRecord(value), at, 'must be an object')
  for (const key of ['stableKey', 'type', 'kind', 'level']) {
    requireValid(
      isText(value[key]),
      `${at}.${key}`,
      'must be a non-empty string',
    )
  }
  // Some unresolved external modules in schema v2 have an empty display name.
  requireValid(typeof value.name === 'string', `${at}.name`, 'must be a string')
  for (const key of ['path', 'language']) {
    requireValid(
      isNullableText(value[key]),
      `${at}.${key}`,
      'must be a string or null',
    )
  }
  requireValid(
    value.parentStableKey === null || isText(value.parentStableKey),
    `${at}.parentStableKey`,
    'must be a non-empty string or null',
  )
  requireValid(
    isTextArray(value.ancestorStableKeys),
    `${at}.ancestorStableKeys`,
    'must be an array of non-empty strings',
  )
  requireValid(
    isInteger(value.depth, 0),
    `${at}.depth`,
    'must be a non-negative integer',
  )
  validateNodeOptions(value, at)
  validatePositions(value, at)
  return value as ArtifactNode
}

function validateNodeOptions(value: Record<string, unknown>, at: string) {
  if (value.qualifiedName !== undefined) {
    requireValid(
      typeof value.qualifiedName === 'string',
      `${at}.qualifiedName`,
      'must be a string',
    )
  }
  if (value.signature !== undefined) {
    requireValid(
      isNullableText(value.signature),
      `${at}.signature`,
      'must be a string or null',
    )
  }
  if (value.properties !== undefined) {
    requireValid(
      isRecord(value.properties),
      `${at}.properties`,
      'must be an object',
    )
    validateComplexity(value.properties, at)
  }
}

function validateComplexity(properties: Record<string, unknown>, at: string) {
  for (const key of [
    'cyclomaticComplexity',
    'baseCyclomaticComplexity',
    'nestedCyclomaticComplexity',
    'loopNestedComplexity',
    'maxDecisionDepth',
    'fanIn',
    'fanOut',
    'transitiveChangeImpact',
    'lineCount',
    'parameterCount',
  ]) {
    if (properties[key] === undefined) continue
    const minimum = [
      'cyclomaticComplexity',
      'baseCyclomaticComplexity',
    ].includes(key)
      ? 1
      : 0
    requireValid(
      isInteger(properties[key], minimum),
      `${at}.properties.${key}`,
      `must be an integer of at least ${minimum}`,
    )
  }
}

function validateParentWalk(
  node: ArtifactNode,
  nodes: Map<string, ArtifactNode>,
  complete: Set<string>,
) {
  const chain = new Set<string>()
  let current: ArtifactNode | undefined = node
  while (current && !complete.has(current.stableKey)) {
    requireValid(
      !chain.has(current.stableKey),
      `node "${current.stableKey}"`,
      'has a parent cycle',
    )
    chain.add(current.stableKey)
    current =
      current.parentStableKey === null
        ? undefined
        : nodes.get(current.parentStableKey)
  }
  chain.forEach((key) => complete.add(key))
}

function validateAncestors(
  node: ArtifactNode,
  nodes: Map<string, ArtifactNode>,
) {
  const parent =
    node.parentStableKey === null ? undefined : nodes.get(node.parentStableKey)
  const ancestors = parent
    ? [...parent.ancestorStableKeys, parent.stableKey]
    : []
  requireValid(
    node.ancestorStableKeys.length === ancestors.length &&
      node.ancestorStableKeys.every((key, index) => key === ancestors[index]),
    `node "${node.stableKey}".ancestorStableKeys`,
    'must match its parent chain',
  )
  requireValid(
    node.depth === ancestors.length,
    `node "${node.stableKey}".depth`,
    'must match its parent chain',
  )
}

function validateHierarchy(nodes: Map<string, ArtifactNode>) {
  for (const node of nodes.values()) {
    requireValid(
      node.parentStableKey === null || nodes.has(node.parentStableKey),
      `node "${node.stableKey}".parentStableKey`,
      `references missing node "${node.parentStableKey}"`,
    )
  }
  // Iterative parent walks visit each node once, even for very deep trees.
  const complete = new Set<string>()
  for (const node of nodes.values()) validateParentWalk(node, nodes, complete)
  for (const node of nodes.values()) validateAncestors(node, nodes)
}

function validateEdge(
  value: unknown,
  index: number,
  nodes: Map<string, ArtifactNode>,
) {
  const at = `edges[${index}]`
  requireValid(isRecord(value), at, 'must be an object')
  for (const key of ['sourceStableKey', 'targetStableKey', 'type']) {
    requireValid(
      isText(value[key]),
      `${at}.${key}`,
      'must be a non-empty string',
    )
  }
  for (const key of ['sourceStableKey', 'targetStableKey']) {
    requireValid(
      nodes.has(value[key] as string),
      `${at}.${key}`,
      `references missing node "${value[key]}"`,
    )
  }
  requireValid(
    value.confidence === 'EXTRACTED' || value.confidence === 'INFERRED',
    `${at}.confidence`,
    'must be EXTRACTED or INFERRED',
  )
  validateEdgeOptions(value, at)
}

function validateEdgeOptions(value: Record<string, unknown>, at: string) {
  for (const key of ['path', 'evidence']) {
    if (value[key] === undefined) continue
    requireValid(
      isNullableText(value[key]),
      `${at}.${key}`,
      'must be a string or null',
    )
  }
  for (const key of [
    'sourceType',
    'sourceKind',
    'sourceLevel',
    'targetType',
    'targetKind',
    'targetLevel',
  ]) {
    if (value[key] === undefined) continue
    requireValid(
      isText(value[key]),
      `${at}.${key}`,
      'must be a non-empty string',
    )
  }
  requireValid(
    value.line == null || isInteger(value.line, 1),
    `${at}.line`,
    'must be a positive integer or null',
  )
}

function validateCycles(value: unknown, nodes: Map<string, ArtifactNode>) {
  if (value === undefined) return
  const at = 'circularDependencies'
  requireValid(isRecord(value), at, 'must be an object')
  requireValid(value.version === 1, at, 'version must be 1')
  requireValid(Array.isArray(value.groups), at, 'groups must be an array')
  const ids = new Set<string>()
  for (const group of value.groups) validateCycleGroup(group, nodes, ids)
}

function validateCycleGroup(
  group: unknown,
  nodes: Map<string, ArtifactNode>,
  ids: Set<string>,
) {
  const at = 'circularDependencies'
  requireValid(isRecord(group), at, 'group must be an object')
  requireValid(
    isText(group.id) && !ids.has(group.id),
    at,
    'group id must be unique',
  )
  ids.add(group.id)
  requireValid(
    isTextArray(group.nodeStableKeys) && group.nodeStableKeys.length > 0,
    at,
    'members must be non-empty',
  )
  const members = new Set(group.nodeStableKeys)
  requireValid(
    members.size === group.nodeStableKeys.length,
    at,
    'members must be unique',
  )
  validateCycleMembers(members, nodes)
  requireValid(
    Array.isArray(group.edges) && group.edges.length > 0,
    at,
    'edges must be non-empty',
  )
  const pairs = validateCycleEdges(group.edges, members, nodes)
  validateCycleExample(group.exampleCycle, pairs)
}

function validateCycleMembers(
  members: Set<string>,
  nodes: Map<string, ArtifactNode>,
) {
  for (const key of members)
    requireValid(
      nodes.get(key)?.type === 'file',
      'circularDependencies',
      'members must reference files',
    )
}

function validateCycleEdges(
  edges: Array<unknown>,
  members: Set<string>,
  nodes: Map<string, ArtifactNode>,
) {
  const pairs = new Set<string>()
  for (const [index, edge] of edges.entries()) {
    validateEdge(edge, index, nodes)
    const dependency = edge as DirectEdge
    requireValid(
      dependency.type === 'IMPORTS' &&
        members.has(dependency.sourceStableKey) &&
        members.has(dependency.targetStableKey),
      'circularDependencies',
      'edges must be imports between members',
    )
    pairs.add(
      JSON.stringify([dependency.sourceStableKey, dependency.targetStableKey]),
    )
  }
  return pairs
}

function validateCycleExample(chain: unknown, pairs: Set<string>) {
  const at = 'circularDependencies'
  requireValid(
    isTextArray(chain) && chain.length >= 2,
    at,
    'example must be a closed chain',
  )
  requireValid(
    chain[0] === chain[chain.length - 1],
    at,
    'example must be closed',
  )
  for (let index = 1; index < chain.length; index++)
    requireValid(
      pairs.has(JSON.stringify([chain[index - 1], chain[index]])),
      at,
      'example must follow group edges',
    )
}

/** Validate the imported graph without rebuilding or discarding artifact metadata. */
export function parseArtifact(value: unknown): Artifact {
  requireValid(isRecord(value), 'document', 'must be an object')
  requireValid(value.schemaVersion === 2, 'schemaVersion', 'must be 2')
  requireValid(isRecord(value.repository), 'repository', 'must be an object')
  requireValid(
    isText(value.repository.name),
    'repository.name',
    'must be a non-empty string',
  )
  for (const key of ['path', 'indexedAt']) {
    if (value.repository[key] === undefined) continue
    requireValid(
      isText(value.repository[key]),
      `repository.${key}`,
      'must be a non-empty string',
    )
  }
  if (value.repository.languages !== undefined) {
    requireValid(
      isTextArray(value.repository.languages),
      'repository.languages',
      'must be an array of non-empty strings',
    )
  }
  requireValid(Array.isArray(value.nodes), 'nodes', 'must be an array')
  requireValid(Array.isArray(value.edges), 'edges', 'must be an array')
  const nodes = new Map<string, ArtifactNode>()
  for (const [index, entry] of value.nodes.entries()) {
    const node = validateNode(entry, index)
    requireValid(
      !nodes.has(node.stableKey),
      `nodes[${index}].stableKey`,
      `duplicates key "${node.stableKey}"`,
    )
    nodes.set(node.stableKey, node)
  }
  validateHierarchy(nodes)
  for (const [index, edge] of value.edges.entries())
    validateEdge(edge, index, nodes)
  validateCycles(value.circularDependencies, nodes)
  return value as Artifact
}
