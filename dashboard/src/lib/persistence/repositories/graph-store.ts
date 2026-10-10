import { dependencyMetrics } from '../../graph-analysis'
import { importCycles } from '../../import-cycles.servers'
import { buildProjectGraph, getGraphTrail } from '../../project-graph'
import { cycleContainsNode, projectCycles } from '../../graph-cycles'
import { hideTestFiles } from '../../graph-visibility'
import { GraphQueries } from './graph-queries'
import type { AppDatabase } from './connection'
import type { ArtifactNode } from '../../architecture-artifact'
import type {
  Architecture,
  GraphDetails,
  GraphStructure,
} from '../../graph-data'
import type { GraphScope } from '../../project-graph-types'
import type { FileComplexitySum } from '../../file-complexity'

type NodeRow = Omit<ArtifactNode, 'ancestorStableKeys' | 'depth'>
const compactProperties = (row: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(row).filter(([, value]) => value !== null))

function hierarchy(rows: Array<NodeRow>): Array<ArtifactNode> {
  const lookup = new Map(rows.map((row) => [row.stableKey, row]))
  return rows.map((row) => {
    const ancestors: Array<string> = []
    let parent = row.parentStableKey
    while (parent !== null) {
      ancestors.push(parent)
      parent = lookup.get(parent)!.parentStableKey
    }
    return {
      ...row,
      ancestorStableKeys: ancestors.reverse(),
      depth: ancestors.length,
    }
  })
}

/** All normalized reads in one explicit deferred ORM transaction/WAL snapshot. */
export class GraphStore {
  private readonly queries: GraphQueries
  constructor(private readonly database: AppDatabase) {
    this.queries = new GraphQueries(database)
  }

  view(id: string, scope: GraphScope): Architecture | null | undefined {
    return this.database.transaction(
      (transaction) => new GraphStore(transaction).readView(id, scope),
      { behavior: 'deferred' },
    )
  }

  private details(
    id: string,
    keys: Array<string>,
    topology: Array<ArtifactNode>,
  ): GraphDetails {
    const properties = new Map<
      string,
      NonNullable<ArtifactNode['properties']>
    >()
    const symbols = new Map<
      string,
      Pick<ArtifactNode, 'signature' | 'startColumn' | 'endColumn'>
    >()
    const metrics = dependencyMetrics(topology, this.queries.relations(id))
    for (const {
      stableKey,
      signature,
      startColumn,
      endColumn,
      ...row
    } of this.queries.metrics(id, keys)) {
      properties.set(stableKey, {
        ...compactProperties(row),
        ...metrics.get(stableKey),
      })
      symbols.set(stableKey, { signature, startColumn, endColumn })
    }
    for (const row of this.queries.decorators(id, keys)) {
      const values = properties.get(row.stableKey)!
      const list = (values.decorators ??= []) as Array<string>
      list.push(row.decorator)
    }
    const keySet = new Set(keys)
    const nodes = topology
      .filter((node) => keySet.has(node.stableKey))
      .map((node) => ({
        ...node,
        ...symbols.get(node.stableKey),
        properties: properties.get(node.stableKey),
      }))
    return {
      nodes,
      fileComplexities: this.fileComplexities(id, keySet, topology),
    }
  }

  private fileComplexities(
    id: string,
    keys: Set<string>,
    topology: Array<ArtifactNode>,
  ): Record<string, FileComplexitySum> {
    const lookup = new Map(topology.map((node) => [node.stableKey, node]))
    const sums = new Map(
      topology
        .filter((node) => keys.has(node.stableKey) && node.level === 'file')
        .map((node) => [
          node.stableKey,
          { functions: 0, measured: 0, total: 0 },
        ]),
    )
    const functions = topology
      .filter((node) => ['function', 'method'].includes(node.type))
      .map((node) => ({
        node,
        file: [
          node.stableKey,
          ...node.ancestorStableKeys.slice().reverse(),
        ].find((key) => lookup.get(key)?.level === 'file'),
      }))
      .filter(({ file }) => file !== undefined && sums.has(file))
    const measurements = new Map(
      this.queries
        .complexities(
          id,
          functions.map(({ node }) => node.stableKey),
        )
        .map((row) => [row.stableKey, row.total]),
    )
    for (const { node, file } of functions) {
      const sum = sums.get(file!)!
      const total = measurements.get(node.stableKey)
      sum.functions += 1
      if (total !== null && total !== undefined) {
        sum.measured += 1
        sum.total += total
      }
    }
    return Object.fromEntries(sums)
  }

  private readView(
    id: string,
    scope: GraphScope,
  ): Architecture | null | undefined {
    const metadata = this.queries.metadata(id)
    if (!metadata) return undefined
    if (metadata.importedAt === null) return null
    const { repositoryId, importedAt, rootName, graphRevision } = metadata
    if (graphRevision === null)
      return { state: 'needsReindex', repositoryId, importedAt, rootName }
    const nodes = hierarchy(this.queries.topology(id))
    const structure: GraphStructure = {
      nodes,
      edges: this.queries.outgoing(id, scope, nodes),
    }
    const visible = hideTestFiles(structure)
    const graph = buildProjectGraph(visible, scope)
    const external = new Set(
      nodes
        .filter((node) => node.type === 'external' || node.level === 'external')
        .map((node) => node.stableKey),
    )
    const internal = new Set(
      visible.nodes
        .filter(
          (node) =>
            ![node.stableKey, ...node.ancestorStableKeys].some((key) =>
              external.has(key),
            ),
        )
        .map((node) => node.stableKey),
    )
    const relations = visible.edges.filter(
      (edge) =>
        internal.has(edge.sourceStableKey) &&
        internal.has(edge.targetStableKey),
    )
    const trail = getGraphTrail(
      { nodes: visible.nodes, repository: { name: rootName } },
      scope,
    )
    const groups = importCycles(nodes, this.queries.imports(id))
    const cycles = (
      projectCycles(
        { ...structure, circularDependencies: { version: 1, groups } },
        graph,
        scope,
      ) ?? []
    ).map((cycle) => ({
      ...cycle,
      labels: Object.fromEntries(
        nodes
          .filter((node) => cycle.group.nodeStableKeys.includes(node.stableKey))
          .map((node) => [node.stableKey, node.path || node.name]),
      ),
      linkedNodeIds: graph.nodes
        .filter((node) => cycleContainsNode(structure, cycle.group, node))
        .map((node) => node.id),
    }))
    const keys = [
      ...new Set([
        ...graph.nodes.map((node) => node.id),
        ...(scope.kind === 'repository' ? [] : [scope.key]),
      ]),
    ]
    const details = this.details(id, keys, nodes)
    for (const node of graph.nodes) {
      const original = details.nodes.find(
        (entry) => entry.stableKey === node.id,
      )
      if (node.kind === 'function') node.properties = original?.properties
    }
    return {
      state: 'ready',
      repositoryId,
      importedAt,
      graphRevision,
      rootName,
      scope,
      graph,
      relations,
      trail,
      details,
      cycles,
      diagnostics: this.queries.diagnostics(id),
    }
  }
}
