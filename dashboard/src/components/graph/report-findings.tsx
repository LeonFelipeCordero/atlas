import type { GraphView, ViewCycle } from '@/lib/graph-data'
import { Button } from '@/components/ui/button'

export function ReportFindings({
  view,
  onCycleScope,
}: {
  view: GraphView
  onCycleScope: (cycle: ViewCycle) => void
}) {
  return (
    <section className="report-findings" aria-label="Recorded findings">
      <h3>Recorded findings</h3>
      <p>
        {view.cycles.length} import cycle{' '}
        {view.cycles.length === 1 ? 'group' : 'groups'} touching this scope ·{' '}
        {view.diagnostics.length} repository{' '}
        {view.diagnostics.length === 1 ? 'diagnostic' : 'diagnostics'}
      </p>
      <p className="sidebar-hint">
        Configured thresholds and check violations are not included in this
        saved graph response. Metric values below are measurements, not
        pass/fail results.
      </p>
      {view.cycles.length === 0 && (
        <p className="sidebar-hint">
          No file-import cycles recorded for this scope. This is not a clean
          bill of health.
        </p>
      )}
      {view.cycles.map((cycle) => (
        <CycleFinding
          key={cycle.group.id}
          cycle={cycle}
          onScope={onCycleScope}
        />
      ))}
      <details className="report-source" open={view.diagnostics.length > 0}>
        <summary>Repository diagnostics · {view.diagnostics.length}</summary>
        <p className="sidebar-hint">
          Diagnostics cover the entire repository, regardless of the current
          scope.
        </p>
        {view.diagnostics.length ? (
          <ul className="report-connections">
            {view.diagnostics.map((diagnostic, index) => (
              <li key={index}>
                <strong>
                  {diagnostic.severity} · {diagnostic.path}
                </strong>
                <span>
                  {diagnostic.language} · {diagnostic.message}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p>
            No diagnostics recorded. Missing measurements are still shown as
            unavailable.
          </p>
        )}
      </details>
    </section>
  )
}

function CycleFinding({
  cycle,
  onScope,
}: {
  cycle: ViewCycle
  onScope: (cycle: ViewCycle) => void
}) {
  const label = (key: string) => cycle.labels[key] ?? key
  return (
    <details className="report-source">
      <summary>
        {cycle.group.nodeStableKeys.length} files in import cycle ·{' '}
        {label(cycle.group.nodeStableKeys[0])}
      </summary>
      <p>
        These files form a mutually reachable import group. The example route is
        not necessarily the whole group. Type-only imports are excluded.
      </p>
      <p className="report-cycle-route">
        {cycle.group.exampleCycle.map(label).join(' → ')}
      </p>
      <p>
        {cycle.outsideCount} {cycle.outsideCount === 1 ? 'file' : 'files'}{' '}
        outside this scope
      </p>
      <ul>
        {cycle.group.nodeStableKeys.map((key) => (
          <li key={key}>{label(key)}</li>
        ))}
      </ul>
      <details className="report-source">
        <summary>Import evidence · {cycle.group.edges.length}</summary>
        <ul className="report-connections">
          {cycle.group.edges.map((edge, index) => (
            <li key={index}>
              <strong>
                {label(edge.sourceStableKey)} → {label(edge.targetStableKey)}
              </strong>
              <span>
                {edge.confidence} · {edge.path || 'Location not recorded'}
                {edge.line != null && `:${edge.line}`}
              </span>
              {edge.evidence && <code>{edge.evidence}</code>}
            </li>
          ))}
        </ul>
      </details>
      <Button variant="outline" size="sm" onClick={() => onScope(cycle)}>
        Report on full group
      </Button>
    </details>
  )
}
