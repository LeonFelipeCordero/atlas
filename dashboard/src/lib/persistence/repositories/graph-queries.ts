import { and, eq, inArray, ne, notLike, or } from 'drizzle-orm'
import {
  graphDecorators,
  graphDiagnostics,
  graphEdges,
  graphFiles,
  graphMetrics,
  graphNodes,
  graphSymbols,
  repositories,
  repositoryGraphs,
} from './schema'
import type { AppDatabase } from './connection'
import type { ArtifactNode } from '../../architecture-artifact'
import type { GraphScope } from '../../project-graph-types'

const identity = (
  table: typeof graphMetrics | typeof graphSymbols | typeof graphFiles,
) =>
  and(
    eq(table.repositoryId, graphNodes.repositoryId),
    eq(table.stableKey, graphNodes.stableKey),
  )

// Bound parameters instead of JSON/raw SQL; keep large scopes below SQLite's variable limit.
export function selectedRows<T>(
  keys: Array<string>,
  read: (batch: Array<string>) => Array<T>,
): Array<T> {
  const rows: Array<T> = []
  for (let start = 0; start < keys.length; start += 500)
    rows.push(...read(keys.slice(start, start + 500)))
  return rows
}

export class GraphQueries {
  constructor(private readonly database: AppDatabase) {}

  metadata(id: string) {
    const row = this.database
      .select({
        repositoryId: repositories.id,
        name: repositories.name,
        importedAt: repositoryGraphs.importedAt,
        graphRevision: repositoryGraphs.graphRevision,
        rootName: repositoryGraphs.rootName,
      })
      .from(repositories)
      .leftJoin(
        repositoryGraphs,
        eq(repositoryGraphs.repositoryId, repositories.id),
      )
      .where(eq(repositories.id, id))
      .get()
    return row ? { ...row, rootName: row.rootName ?? row.name } : undefined
  }

  topology(id: string) {
    return this.database
      .select({
        stableKey: graphNodes.stableKey,
        parentStableKey: graphNodes.parentStableKey,
        type: graphNodes.type,
        kind: graphNodes.kind,
        level: graphNodes.level,
        name: graphNodes.name,
        language: graphNodes.language,
        qualifiedName: graphNodes.qualifiedName,
        path: graphNodes.path,
        startLine: graphSymbols.startLine,
        endLine: graphSymbols.endLine,
      })
      .from(graphNodes)
      .leftJoin(graphSymbols, identity(graphSymbols))
      .where(eq(graphNodes.repositoryId, id))
      .orderBy(graphNodes.ordinal)
      .all()
  }

  outgoing(id: string, scope: GraphScope, nodes: Array<ArtifactNode>) {
    const read = (keys?: Array<string>) =>
      this.database
        .select()
        .from(graphEdges)
        .where(
          and(
            eq(graphEdges.repositoryId, id),
            ne(graphEdges.type, 'CONTAINS'),
            keys ? inArray(graphEdges.sourceStableKey, keys) : undefined,
          ),
        )
        .orderBy(graphEdges.ordinal)
        .all()
    const rows =
      scope.kind === 'repository'
        ? read()
        : selectedRows(
            nodes
              .filter(
                (node) =>
                  node.stableKey === scope.key ||
                  node.ancestorStableKeys.includes(scope.key),
              )
              .map((node) => node.stableKey),
            read,
          )
    return rows
      .sort((a, b) => a.ordinal - b.ordinal)
      .map(
        ({ ordinal: _ordinal, repositoryId: _repositoryId, ...edge }) => edge,
      )
  }

  relations(id: string) {
    return this.database
      .select({
        sourceStableKey: graphEdges.sourceStableKey,
        targetStableKey: graphEdges.targetStableKey,
      })
      .from(graphEdges)
      .where(
        and(eq(graphEdges.repositoryId, id), ne(graphEdges.type, 'CONTAINS')),
      )
      .orderBy(graphEdges.ordinal)
      .all()
  }

  imports(id: string) {
    return this.database
      .select()
      .from(graphEdges)
      .where(
        and(
          eq(graphEdges.repositoryId, id),
          eq(graphEdges.type, 'IMPORTS'),
          eq(graphEdges.typeOnly, false),
        ),
      )
      .orderBy(graphEdges.ordinal)
      .all()
  }

  metrics(id: string, keys: Array<string>) {
    return selectedRows(keys, (batch) =>
      this.database
        .select({
          stableKey: graphNodes.stableKey,
          lineCount: graphMetrics.lineCount,
          parameterCount: graphMetrics.parameterCount,
          baseCyclomaticComplexity: graphMetrics.baseCyclomaticComplexity,
          nestedCyclomaticComplexity: graphMetrics.nestedCyclomaticComplexity,
          loopNestedComplexity: graphMetrics.loopNestedComplexity,
          cyclomaticComplexity: graphMetrics.cyclomaticComplexity,
          maxDecisionDepth: graphMetrics.maxDecisionDepth,
          visibility: graphSymbols.visibility,
          signature: graphSymbols.signature,
          startColumn: graphSymbols.startColumn,
          endColumn: graphSymbols.endColumn,
          bytes: graphFiles.bytes,
          sha256: graphFiles.sha256,
        })
        .from(graphNodes)
        .leftJoin(graphMetrics, identity(graphMetrics))
        .leftJoin(graphSymbols, identity(graphSymbols))
        .leftJoin(graphFiles, identity(graphFiles))
        .where(
          and(
            eq(graphNodes.repositoryId, id),
            inArray(graphNodes.stableKey, batch),
          ),
        )
        .orderBy(graphNodes.ordinal)
        .all(),
    )
  }

  decorators(id: string, keys: Array<string>) {
    return selectedRows(keys, (batch) =>
      this.database
        .select({
          stableKey: graphDecorators.stableKey,
          decorator: graphDecorators.decorator,
        })
        .from(graphDecorators)
        .where(
          and(
            eq(graphDecorators.repositoryId, id),
            inArray(graphDecorators.stableKey, batch),
          ),
        )
        .orderBy(graphDecorators.stableKey, graphDecorators.ordinal)
        .all(),
    )
  }

  complexities(id: string, keys: Array<string>) {
    return selectedRows(keys, (batch) =>
      this.database
        .select({
          stableKey: graphMetrics.stableKey,
          total: graphMetrics.cyclomaticComplexity,
        })
        .from(graphMetrics)
        .where(
          and(
            eq(graphMetrics.repositoryId, id),
            inArray(graphMetrics.stableKey, batch),
          ),
        )
        .all(),
    )
  }

  diagnostics(id: string) {
    return this.database
      .select({
        severity: graphDiagnostics.severity,
        path: graphDiagnostics.path,
        language: graphDiagnostics.language,
        message: graphDiagnostics.message,
      })
      .from(graphDiagnostics)
      .where(
        and(
          eq(graphDiagnostics.repositoryId, id),
          or(
            ne(graphDiagnostics.severity, 'warning'),
            notLike(graphDiagnostics.message, 'Mutation candidates: %'),
          ),
        ),
      )
      .orderBy(graphDiagnostics.ordinal)
      .all()
  }
}
