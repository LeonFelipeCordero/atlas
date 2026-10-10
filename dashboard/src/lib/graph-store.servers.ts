import { dependencyMetrics } from './graph-analysis'
import { importCycles } from './import-cycles.servers'
import { buildProjectGraph, getGraphTrail } from './project-graph'
import { cycleContainsNode, projectCycles } from './graph-cycles'
import { hideTestFiles } from './graph-visibility'
import type { AppDatabase } from './database.servers'
import type { ArtifactNode, DirectEdge } from './architecture-artifact'
import type {
  Architecture,
  GraphDetails,
  GraphDiagnostic,
  GraphStructure,
} from './graph-data'
import type { GraphScope } from './project-graph-types'
import type { FileComplexitySum } from './file-complexity'

type Metadata = {
  repositoryId: string
  importedAt: number | null
  graphRevision: string | null
  rootName: string
}
type NodeRow = Omit<ArtifactNode, 'ancestorStableKeys' | 'depth'>
type MetricRow = {
  stableKey: string
  signature: string | null
  startColumn: number | null
  endColumn: number | null
  lineCount: number | null
  parameterCount: number | null
  baseCyclomaticComplexity: number | null
  nestedCyclomaticComplexity: number | null
  loopNestedComplexity: number | null
  cyclomaticComplexity: number | null
  maxDecisionDepth: number | null
  visibility: string | null
  bytes: number | null
  sha256: string | null
}
const edgeColumns = `source_key AS sourceStableKey, target_key AS targetStableKey,
  relationship AS type, confidence, path, line, evidence, type_only AS typeOnly`
const selectedKeys = `SELECT value FROM json_each(?)`
const compactProperties = (
  row: Omit<MetricRow, 'stableKey' | 'signature' | 'startColumn' | 'endColumn'>,
) =>
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

/** Owns normalized SQL and the entire response's explicit deferred read transaction. */
export class GraphStore {
  constructor(private readonly database: AppDatabase) {}

  view(id: string, scope: GraphScope): Architecture | null | undefined {
    return this.database.transaction(() => this.readView(id, scope)).deferred()
  }

  private metadata(id: string) {
    return this.database
      .query<Metadata, [string]>(
        `
      SELECT r.id AS repositoryId, g.imported_at AS importedAt,
        g.graph_revision AS graphRevision, COALESCE(g.root_name, r.name) AS rootName
      FROM repositories r LEFT JOIN repository_graphs g ON g.repository_id = r.id
      WHERE r.id = ?
    `,
      )
      .get(id)
  }

  private topology(id: string) {
    return hierarchy(
      this.database
        .query<NodeRow, [string]>(
          `
      SELECT n.node_key AS stableKey, n.parent_key AS parentStableKey,
        n.type, n.kind, n.level, n.name, n.language,
        n.qualified_name AS qualifiedName, n.path,
        s.start_line AS startLine, s.end_line AS endLine
      FROM graph_nodes n LEFT JOIN graph_symbols s
        ON s.repository_id = n.repository_id AND s.node_key = n.node_key
      WHERE n.repository_id = ? ORDER BY n.ordinal
    `,
        )
        .all(id),
    )
  }

  private outgoing(id: string, scope: GraphScope): Array<DirectEdge> {
    const rows =
      scope.kind === 'repository'
        ? this.database
            .query<DirectEdge, [string]>(
              `
          SELECT ${edgeColumns} FROM graph_edges
          WHERE repository_id = ? AND relationship != 'CONTAINS' ORDER BY ordinal
        `,
            )
            .all(id)
        : this.database
            .query<DirectEdge, [string, string, string]>(
              `
          WITH RECURSIVE local(node_key) AS (
            SELECT node_key FROM graph_nodes WHERE repository_id = ? AND node_key = ?
            UNION ALL
            SELECT n.node_key FROM graph_nodes n JOIN local l ON n.parent_key = l.node_key
            WHERE n.repository_id = ?
          )
          SELECT ${edgeColumns} FROM graph_edges
          WHERE repository_id = ?3 AND relationship != 'CONTAINS'
            AND source_key IN (SELECT node_key FROM local) ORDER BY ordinal
        `,
            )
            .all(id, scope.key, id)
    return rows.map((row) => ({ ...row, typeOnly: Boolean(row.typeOnly) }))
  }

  private relations(id: string) {
    return this.database
      .query<Pick<DirectEdge, 'sourceStableKey' | 'targetStableKey'>, [string]>(
        `
      SELECT source_key AS sourceStableKey, target_key AS targetStableKey
      FROM graph_edges WHERE repository_id = ? AND relationship != 'CONTAINS'
      ORDER BY ordinal
    `,
      )
      .all(id)
  }

  private cycles(id: string, nodes: Array<ArtifactNode>) {
    const imports = this.database
      .query<DirectEdge, [string]>(
        `
      SELECT ${edgeColumns} FROM graph_edges
      WHERE repository_id = ? AND relationship = 'IMPORTS' AND type_only = 0
      ORDER BY ordinal
    `,
      )
      .all(id)
    return importCycles(nodes, imports)
  }

  private details(
    id: string,
    keys: Array<string>,
    topology: Array<ArtifactNode>,
  ): GraphDetails {
    const encoded = JSON.stringify(keys)
    const properties = new Map<
      string,
      NonNullable<ArtifactNode['properties']>
    >()
    const symbols = new Map<
      string,
      Pick<ArtifactNode, 'signature' | 'startColumn' | 'endColumn'>
    >()
    const metrics = dependencyMetrics(topology, this.relations(id))
    const rows = this.database
      .query<MetricRow, [string, string]>(
        `
      SELECT n.node_key AS stableKey, m.line_count AS lineCount, m.parameter_count AS parameterCount,
        m.base_complexity AS baseCyclomaticComplexity, m.nested_complexity AS nestedCyclomaticComplexity,
        m.loop_complexity AS loopNestedComplexity, m.total_complexity AS cyclomaticComplexity,
        m.max_decision_depth AS maxDecisionDepth, s.visibility, s.signature,
        s.start_column AS startColumn, s.end_column AS endColumn, f.byte_count AS bytes, f.sha256
      FROM graph_nodes n
      LEFT JOIN graph_node_metrics m ON m.repository_id = n.repository_id AND m.node_key = n.node_key
      LEFT JOIN graph_symbols s ON s.repository_id = n.repository_id AND s.node_key = n.node_key
      LEFT JOIN graph_files f ON f.repository_id = n.repository_id AND f.node_key = n.node_key
      WHERE n.repository_id = ? AND n.node_key IN (${selectedKeys}) ORDER BY n.ordinal
    `,
      )
      .all(id, encoded)
    for (const {
      stableKey,
      signature,
      startColumn,
      endColumn,
      ...row
    } of rows) {
      properties.set(stableKey, {
        ...compactProperties(row),
        ...metrics.get(stableKey),
      })
      symbols.set(stableKey, { signature, startColumn, endColumn })
    }
    const decorators = this.database
      .query<{ stableKey: string; decorator: string }, [string, string]>(
        `
      SELECT node_key AS stableKey, decorator FROM graph_node_decorators
      WHERE repository_id = ? AND node_key IN (${selectedKeys}) ORDER BY node_key, ordinal
    `,
      )
      .all(id, encoded)
    for (const row of decorators) {
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
    return { nodes, fileComplexities: this.fileComplexities(id, encoded) }
  }

  private fileComplexities(
    id: string,
    encoded: string,
  ): Record<string, FileComplexitySum> {
    const rows = this.database
      .query<
        FileComplexitySum & { stableKey: string },
        [string, string, string, string]
      >(
        `
      WITH RECURSIVE owned(file_key, node_key) AS (
        SELECT node_key, node_key FROM graph_nodes WHERE repository_id = ? AND level = 'file'
          AND node_key IN (${selectedKeys})
        UNION ALL
        SELECT o.file_key, n.node_key FROM graph_nodes n JOIN owned o ON n.parent_key = o.node_key
        WHERE n.repository_id = ? AND n.level != 'file'
      )
      SELECT o.file_key AS stableKey,
        COUNT(CASE WHEN n.type IN ('function', 'method') THEN 1 END) AS functions,
        COUNT(CASE WHEN n.type IN ('function', 'method') THEN m.total_complexity END) AS measured,
        COALESCE(SUM(CASE WHEN n.type IN ('function', 'method') THEN m.total_complexity END), 0) AS total
      FROM owned o JOIN graph_nodes n ON n.repository_id = ? AND n.node_key = o.node_key
      LEFT JOIN graph_node_metrics m ON m.repository_id = n.repository_id AND m.node_key = n.node_key
      GROUP BY o.file_key
    `,
      )
      .all(id, encoded, id, id)
    return Object.fromEntries(
      rows.map(({ stableKey, ...sum }) => [stableKey, sum]),
    )
  }

  private diagnostics(id: string) {
    return this.database
      .query<GraphDiagnostic, [string]>(
        `
      SELECT severity, path, language, message FROM graph_diagnostics
      WHERE repository_id = ? ORDER BY ordinal
    `,
      )
      .all(id)
  }

  private readView(
    id: string,
    scope: GraphScope,
  ): Architecture | null | undefined {
    const metadata = this.metadata(id)
    if (!metadata) return undefined
    if (metadata.importedAt === null) return null
    const { repositoryId, importedAt, rootName, graphRevision } = metadata
    if (graphRevision === null)
      return { state: 'needsReindex', repositoryId, importedAt, rootName }
    const nodes = this.topology(id)
    const structure: GraphStructure = { nodes, edges: this.outgoing(id, scope) }
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
    const groups = this.cycles(id, nodes)
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
      diagnostics: this.diagnostics(id),
    }
  }
}
