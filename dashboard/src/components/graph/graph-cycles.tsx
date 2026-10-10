import type { GraphNode } from '@/lib/project-graph'
import type { ViewCycle } from '@/lib/graph-data'
import { Button } from '@/components/ui/button'

export type CycleProps = {
  cycles: Array<ViewCycle> | undefined
  activeCycle: ViewCycle | null
  onCycle: (cycle: ViewCycle) => void
  onCycleScope: (cycle: ViewCycle) => void
}

export function GraphCycles({
  item,
  cycles,
  activeCycle,
  onCycle,
  onCycleScope,
}: CycleProps & { item?: GraphNode }) {
  const linked = cycles?.filter(
    (cycle) => !item || cycle.linkedNodeIds.includes(item.id),
  )
  if (!linked?.length) return null
  return (
    <section className="graph-cycles" aria-label="Circular dependencies">
      <div className="section-heading">
        <h4>
          {item?.kind === 'folder'
            ? 'Contains circular dependencies'
            : 'Circular dependencies'}
        </h4>
        <span>{linked.length}</span>
      </div>
      {item?.kind === 'function' && (
        <p className="sidebar-hint">
          File-import cycles for this function’s owning file, not the function
          itself.
        </p>
      )}
      {linked.map((cycle) => (
        <div className="cycle-item" key={cycle.group.id}>
          <button
            className="cycle-select"
            aria-pressed={activeCycle?.group.id === cycle.group.id}
            onClick={() => onCycle(cycle)}
          >
            <strong>
              {cycle.group.nodeStableKeys.length}{' '}
              {cycle.group.nodeStableKeys.length === 1 ? 'file' : 'files'} in
              import cycle
            </strong>
            <span>
              {cycle.group.exampleCycle
                .map((key) => cycle.labels[key] ?? key)
                .join(' → ')}
            </span>
          </button>
          {activeCycle?.group.id === cycle.group.id && (
            <p className="sidebar-hint" role="status">
              Member files and containing folders highlighted. Only recorded
              cycle imports are emphasized.
            </p>
          )}
          {cycle.outsideCount > 0 && (
            <p className="sidebar-hint">
              {cycle.outsideCount}{' '}
              {cycle.outsideCount === 1 ? 'file outside' : 'files outside'} this
              scope
            </p>
          )}
          <Button variant="ghost" size="sm" onClick={() => onCycleScope(cycle)}>
            Show full group
          </Button>
        </div>
      ))}
    </section>
  )
}
