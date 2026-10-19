import { Suspense, lazy, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Network } from 'lucide-react'
import { GraphSidebar } from './graph-sidebar'
import { GraphNavigation } from './graph-navigation'
import { GraphModeNavigation } from './graph-mode-navigation'
import { GraphFileComplexity } from './graph-file-complexity'
import type { ComponentProps } from 'react'
import type { Architecture, GraphView, ViewCycle } from '@/lib/graph-data'
import type { GraphNode, GraphScope } from '@/lib/project-graph'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'

const GraphCanvas = lazy(() => import('./graph-canvas'))

function EmptyGraph({ isFile, back }: { isFile: boolean; back?: () => void }) {
  return (
    <div className="empty-graph">
      <Network size={32} />
      <h3>
        {isFile
          ? 'No functions in this file'
          : 'Nothing indexed in this folder'}
      </h3>
      <p>
        {isFile
          ? 'Configuration, styles, and documentation may not contain callable symbols.'
          : 'Only items recorded in the saved index appear here.'}
      </p>
      {back && (
        <Button variant="outline" onClick={back}>
          Back to parent
        </Button>
      )}
    </div>
  )
}

function GraphViewport({
  isFile,
  back,
  ...props
}: ComponentProps<typeof GraphCanvas> & {
  isFile: boolean
  back?: () => void
}) {
  if (!props.graph.nodes.length)
    return <EmptyGraph isFile={isFile} back={back} />
  return (
    <Suspense
      fallback={
        <div className="loading-state" role="status">
          Drawing your graph…
        </div>
      }
    >
      <GraphCanvas {...props} />
    </Suspense>
  )
}

function GraphWorkspace({
  view,
  navigate,
  mode,
  onMode,
  ...actions
}: {
  view: GraphView
  mode: 'explore' | 'report'
  onMode: (mode: 'explore' | 'report') => void
  navigate: (index: number) => void
  selected: string | null
  focusId: string | null
  activeCycle: ViewCycle | null
  onSelect: (id: string | null) => void
  onOpen: (node: GraphNode) => void
  onCycle: (cycle: ViewCycle) => void
  onCycleScope: (cycle: ViewCycle) => void
}) {
  const { trail, graph, cycles, details } = view
  const current = trail[trail.length - 1]
  return (
    <section className="explorer" aria-label="Project graph">
      <GraphModeNavigation mode={mode} onMode={onMode} />
      <GraphNavigation trail={trail} navigate={navigate} />
      {mode === 'report' && (
        <div className="report-intro">
          <div>
            <h2>Report</h2>
            <p>
              Inspect an item for complexity, size, and dependency metrics.
              Circular dependencies show recorded file imports.
            </p>
          </div>
          <Button variant="outline" onClick={() => onMode('explore')}>
            Explore this scope
          </Button>
        </div>
      )}
      {mode === 'report' && current.scope.kind === 'file' && (
        <GraphFileComplexity
          sum={details.fileComplexities[current.scope.key]}
          compact
        />
      )}
      <div
        className={mode === 'explore' ? 'graph-workspace' : 'report-workspace'}
      >
        {mode === 'explore' && (
          <div
            className="graph-canvas"
            role="region"
            aria-label={`${current.label} dependency graph`}
          >
            <GraphViewport
              key={JSON.stringify(current.scope)}
              graph={graph}
              selected={actions.selected}
              focusId={actions.focusId}
              activeCycle={null}
              onSelect={actions.onSelect}
              onOpen={actions.onOpen}
              isFile={current.scope.kind === 'file'}
              back={
                trail.length > 1 ? () => navigate(trail.length - 2) : undefined
              }
            />
          </div>
        )}
        <GraphSidebar
          key={JSON.stringify(current.scope)}
          graph={graph}
          details={details}
          scope={current.scope}
          cycles={mode === 'report' ? cycles : undefined}
          {...actions}
          report={mode === 'report'}
          onOpen={(node) => {
            actions.onOpen(node)
            onMode('explore')
          }}
        />
      </div>
    </section>
  )
}

function useGraphView(initial: GraphView, scope: GraphScope) {
  return useQuery({
    queryKey: [
      'graph-view',
      initial.repositoryId,
      initial.graphRevision,
      scope,
    ],
    queryFn: () => {
      const parameters = new URLSearchParams({
        repositoryId: initial.repositoryId,
        kind: scope.kind,
      })
      if (scope.kind !== 'repository') parameters.set('key', scope.key)
      return api<Architecture | null>(`/api/architecture?${parameters}`)
    },
    initialData: scope.kind === 'repository' ? initial : undefined,
    retry: false,
  })
}

export function GraphExplorer({ initial }: { initial: GraphView }) {
  const [scope, setScope] = useState<GraphScope>({ kind: 'repository' })
  const [selected, setSelected] = useState<string | null>(null)
  const [cycleId, setCycleId] = useState<string | null>(null)
  const [mode, setMode] = useState<'explore' | 'report'>('explore')
  const view = useGraphView(initial, scope)
  if (
    view.error ||
    (view.data && view.data.state !== 'ready') ||
    view.data === null
  )
    return (
      <div className="error-message" role="alert">
        <p>{view.error?.message ?? 'This graph needs to be re-indexed.'}</p>
        <Button
          variant="outline"
          onClick={() => {
            void view.refetch()
          }}
        >
          Try again
        </Button>
        <Button
          variant="outline"
          onClick={() => setScope({ kind: 'repository' })}
        >
          Back to repository
        </Button>
      </div>
    )
  if (!view.data)
    return (
      <div className="loading-state" role="status">
        Loading the repository graph…
      </div>
    )
  const data = view.data
  const activeCycle =
    data.cycles.find((cycle) => cycle.group.id === cycleId) ?? null
  const select = (id: string | null) => {
    setCycleId(null)
    setSelected(id)
  }
  const open = (node: GraphNode) => {
    const destination = node.destination
    const nextScope = destination?.scope ?? node.scope
    if (!nextScope) return
    setScope(nextScope)
    setCycleId(null)
    setSelected(destination?.focusId ?? null)
  }
  const navigate = (index: number) => {
    setScope(data.trail[index].scope)
    select(null)
  }
  return (
    <GraphWorkspace
      view={data}
      navigate={navigate}
      mode={mode}
      onMode={setMode}
      selected={selected}
      focusId={selected}
      activeCycle={activeCycle}
      onSelect={select}
      onOpen={open}
      onCycle={(cycle) => {
        setCycleId(cycle.group.id)
      }}
      onCycleScope={(cycle) => {
        setScope(cycle.scope)
        setSelected(null)
        setCycleId(cycle.group.id)
      }}
    />
  )
}
