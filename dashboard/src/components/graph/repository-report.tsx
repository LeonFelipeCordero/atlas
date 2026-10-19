import { GraphNavigation } from './graph-navigation'
import { GraphComplexity } from './graph-complexity'
import { GraphFileComplexity } from './graph-file-complexity'
import { GraphDependencyMetrics } from './graph-dependency-metrics'
import { GraphSizeMetrics } from './graph-size-metrics'
import type { GraphView } from '@/lib/graph-data'
import type { GraphScope } from '@/lib/project-graph'
import { Button } from '@/components/ui/button'

type ReportProps = {
  expandedCycles: Array<string>
  onToggleCycle: (id: string, expanded: boolean) => void
  view: GraphView
  navigate: (index: number) => void
  onScope: (scope: GraphScope) => void
  onExplore: (scope: GraphScope, focus?: string | null) => void
}

export function RepositoryReport({
  view,
  navigate,
  onScope,
  onExplore,
  expandedCycles,
  onToggleCycle,
}: ReportProps) {
  return (
    <section className="report-workbench" aria-label="Repository report">
      <header className="report-heading">
        <div>
          <h2 id="report-title" tabIndex={-1}>
            Repository report
          </h2>
          <p>
            Read the saved analysis. Explore the project when you need location
            and connections.
          </p>
        </div>
        <Button id="report-explore" onClick={() => onExplore(view.scope)}>
          Explore project
        </Button>
      </header>
      <GraphNavigation trail={view.trail} navigate={navigate} />
      <div className="report-layout">
        <nav className="report-index" aria-label="Report sections">
          <a href="#report-analysis">Metrics &amp; complexity</a>
          <a href="#report-cycles">
            Circular dependencies <span>{view.cycles.length}</span>
          </a>
          <a href="#report-diagnostics">
            Index diagnostics <span>{view.diagnostics.length}</span>
          </a>
          <p>
            Analysis follows the selected scope. The project map is a separate
            workspace.
          </p>
        </nav>
        <div className="report-document">
          <ReportMetrics view={view} onScope={onScope} onExplore={onExplore} />
          <ReportCycles
            view={view}
            onExplore={onExplore}
            expandedCycles={expandedCycles}
            onToggleCycle={onToggleCycle}
          />
          <section id="report-diagnostics" aria-labelledby="diagnostics-title">
            <h3 id="diagnostics-title">Index diagnostics</h3>
            {!view.diagnostics.length && <p>No index diagnostics recorded.</p>}
            {view.diagnostics.map((diagnostic, index) => (
              <article className="report-entry" key={index}>
                <h4>{diagnostic.path}</h4>
                <p>
                  {diagnostic.severity} · {diagnostic.language}
                </p>
                <p>{diagnostic.message}</p>
              </article>
            ))}
          </section>
        </div>
      </div>
    </section>
  )
}

function ReportMetrics({
  view,
  onScope,
  onExplore,
}: Pick<ReportProps, 'view' | 'onScope' | 'onExplore'>) {
  const local = view.graph.nodes.filter((node) => node.role !== 'boundary')
  return (
    <section id="report-analysis" aria-labelledby="analysis-title">
      <h3 id="analysis-title">Metrics &amp; complexity</h3>
      <p className="report-note">
        Recorded measurements for this scope. Open a folder or file report to
        read its analysis in detail. Missing measurements are not zero.
      </p>
      {view.scope.kind === 'file' && (
        <GraphFileComplexity
          sum={view.details.fileComplexities[view.scope.key]}
        />
      )}
      {!local.length && <p>No items recorded at this level.</p>}
      {local.map((item) => {
        const node = view.details.nodes.find(
          (entry) => entry.stableKey === item.id,
        )
        return (
          <article className="report-entry" key={item.id}>
            <div className="report-entry-heading">
              <div>
                <h4>{item.label}</h4>
                <p>{item.path || item.detail}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onExplore(view.scope, item.id)}
                id={`report-location-${item.id}`}
                aria-label={`View ${item.path || item.label} in project`}
              >
                View in project
              </Button>
            </div>
            {node && (
              <div className="report-measurements">
                {item.kind === 'file' && (
                  <GraphFileComplexity
                    sum={view.details.fileComplexities[item.id]}
                  />
                )}
                {['function', 'method'].includes(node.type) && (
                  <GraphComplexity properties={node.properties} />
                )}
                <GraphSizeMetrics node={node} />
                <GraphDependencyMetrics node={node} />
              </div>
            )}
            {item.scope && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onScope(item.scope!)}
              >
                Read {item.label} report
              </Button>
            )}
          </article>
        )
      })}
    </section>
  )
}

function ReportCycles({
  view,
  onExplore,
  expandedCycles,
  onToggleCycle,
}: Pick<
  ReportProps,
  'view' | 'onExplore' | 'expandedCycles' | 'onToggleCycle'
>) {
  return (
    <section id="report-cycles" aria-labelledby="cycles-title">
      <h3 id="cycles-title">Circular dependencies</h3>
      <p className="report-note">
        Recorded file-import cycles, not function-call cycles.
      </p>
      {!view.cycles.length && (
        <p>No circular dependencies recorded in this scope.</p>
      )}
      {view.cycles.map((cycle) => (
        <article className="report-entry" key={cycle.group.id}>
          <h4>{cycle.group.nodeStableKeys.length} files in import cycle</h4>
          <p className="report-cycle-path">
            {cycle.group.exampleCycle
              .map((key) => cycle.labels[key] ?? key)
              .join(' → ')}
          </p>
          <details
            open={expandedCycles.includes(cycle.group.id)}
            onToggle={(event) =>
              onToggleCycle(cycle.group.id, event.currentTarget.open)
            }
          >
            <summary>Member files</summary>
            <ul>
              {cycle.group.nodeStableKeys.map((key) => (
                <li key={key}>{cycle.labels[key] ?? key}</li>
              ))}
            </ul>
          </details>
          <Button
            variant="outline"
            size="sm"
            id={`report-cycle-${cycle.group.id}`}
            onClick={() => onExplore(cycle.scope)}
          >
            View group in project
          </Button>
        </article>
      ))}
    </section>
  )
}
