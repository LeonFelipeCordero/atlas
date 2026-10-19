import { useState } from 'react'
import { FileText, Map, PanelLeft } from 'lucide-react'
import { GraphNavigation } from './graph-navigation'
import { GraphSidebar } from './graph-sidebar'
import { GraphViewport } from './graph-viewport'
import { ProjectNavigator } from './project-navigator'
import type { ReactNode } from 'react'
import type { GraphView, ViewCycle } from '@/lib/graph-data'
import type { GraphNode, GraphScope } from '@/lib/project-graph'
import { Button } from '@/components/ui/button'

type Props = {
  status?: ReactNode
  requestedScope?: GraphScope
  initial: GraphView
  view: GraphView
  navigate: (index: number) => void
  onScope: (scope: GraphScope) => void
  selected: string | null
  focusId: string | null
  activeCycle: ViewCycle | null
  onSelect: (id: string | null) => void
  onOpen: (node: GraphNode) => void
  onCycle: (cycle: ViewCycle) => void
  onCycleScope: (cycle: ViewCycle) => void
}

export function GraphWorkspace({
  initial,
  view,
  navigate,
  onScope,
  status,
  requestedScope,
  ...actions
}: Props) {
  const [area, setArea] = useState<'map' | 'report'>('map')
  const [navigatorOpen, setNavigatorOpen] = useState(false)
  const { trail } = view
  return (
    <section
      className="explorer project-workspace"
      aria-label="Project workspace"
      data-navigator-open={navigatorOpen}
    >
      <ProjectNavigator
        initial={initial}
        trail={trail}
        scope={requestedScope ?? view.scope}
        selected={actions.selected}
        onScope={onScope}
        onOpen={actions.onOpen}
        onSelect={actions.onSelect}
      />
      <div className="scope-workspace">
        <div className="scope-location">
          <Button
            className="navigator-disclosure"
            variant="ghost"
            size="sm"
            aria-expanded={navigatorOpen}
            onClick={() => setNavigatorOpen(!navigatorOpen)}
          >
            <PanelLeft size={16} />
            Project
          </Button>
          <GraphNavigation trail={trail} navigate={navigate} />
        </div>
        <div className="workspace-toolbar">
          <div className="workspace-switch" role="group" aria-label="Work area">
            <button
              aria-pressed={area === 'map'}
              onClick={() => setArea('map')}
            >
              <Map size={16} />
              Map
            </button>
            <button
              aria-pressed={area === 'report'}
              onClick={() => setArea('report')}
            >
              <FileText size={16} />
              Report
            </button>
          </div>
          <p>
            {area === 'map'
              ? 'Structure & connections'
              : 'Analysis from the saved index'}
          </p>
        </div>
        {status ||
          (area === 'map' ? (
            <GraphMap
              view={view}
              navigate={navigate}
              onScope={onScope}
              {...actions}
            />
          ) : (
            <GraphReport
              view={view}
              navigate={navigate}
              onScope={onScope}
              {...actions}
              onShowMap={() => setArea('map')}
            />
          ))}
      </div>
    </section>
  )
}

type AreaProps = Omit<Props, 'initial' | 'status' | 'requestedScope'>

function GraphMap({ view, navigate, ...actions }: AreaProps) {
  const { trail, graph, details } = view
  const current = trail[trail.length - 1]
  return (
    <div className="map-area">
      <div
        className="graph-canvas"
        role="region"
        aria-label={`${current.label} dependency graph`}
      >
        <GraphViewport
          key={JSON.stringify(current.scope)}
          graph={graph}
          selected={actions.selected}
          focusId={actions.selected}
          onSelect={actions.onSelect}
          onOpen={actions.onOpen}
          isFile={current.scope.kind === 'file'}
          back={trail.length > 1 ? () => navigate(trail.length - 2) : undefined}
        />
      </div>
      <details
        className="map-inspector"
        open={actions.selected !== null || undefined}
      >
        <summary>
          {actions.selected
            ? 'Selected item · connections'
            : `Contents & connections · ${graph.nodes.length} items`}
        </summary>
        <GraphSidebar
          key={JSON.stringify(current.scope)}
          graph={graph}
          details={details}
          scope={current.scope}
          cycles={undefined}
          {...actions}
          analysis={false}
          activeCycle={null}
        />
      </details>
    </div>
  )
}

function GraphReport({
  view,
  onScope,
  onShowMap,
  ...actions
}: AreaProps & { onShowMap: () => void }) {
  const { trail, graph, cycles, details } = view
  const current = trail[trail.length - 1]
  const source = (node: GraphNode) => {
    actions.onOpen(node)
    onShowMap()
  }
  return (
    <section className="report-area" aria-label="Scope report">
      <div className="report-heading">
        <h2>
          Report <span>/ {current.label}</span>
        </h2>
        <p>
          Select an item to inspect its recorded analysis. Open its source scope
          to return to the map.
        </p>
        <Button variant="outline" size="sm" onClick={onShowMap}>
          {actions.selected ? 'View selected item on map' : 'View scope on map'}
        </Button>
      </div>
      <GraphSidebar
        key={JSON.stringify(current.scope)}
        graph={graph}
        details={details}
        scope={current.scope}
        cycles={cycles}
        {...actions}
        onOpen={source}
        onCycleMember={(key) => {
          onScope({ kind: 'file', key })
          onShowMap()
        }}
      />
      {view.diagnostics.length > 0 && (
        <section className="report-diagnostics" aria-label="Index diagnostics">
          <h3>Index diagnostics</h3>
          {view.diagnostics.map((diagnostic, index) => (
            <p key={index}>
              <strong>{diagnostic.path}</strong> · {diagnostic.severity}:{' '}
              {diagnostic.message}
            </p>
          ))}
        </section>
      )}
    </section>
  )
}
