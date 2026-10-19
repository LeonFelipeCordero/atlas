import { Suspense, lazy, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Network } from 'lucide-react'
import { GraphSidebar } from './graph-sidebar'
import { GraphNavigation } from './graph-navigation'
import { RepositoryReport } from './repository-report'
import type { ComponentProps } from 'react'
import type { Architecture, GraphView } from '@/lib/graph-data'
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
  ...actions
}: {
  view: GraphView
  navigate: (index: number) => void
  selected: string | null
  focusId: string | null
  onSelect: (id: string | null) => void
  onOpen: (node: GraphNode) => void
}) {
  const { trail, graph, details } = view
  const current = trail[trail.length - 1]
  return (
    <section className="explorer" aria-label="Project graph">
      <GraphNavigation trail={trail} navigate={navigate} />
      <div className="graph-workspace">
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
        <GraphSidebar
          structureOnly
          key={JSON.stringify(current.scope)}
          graph={graph}
          details={details}
          scope={current.scope}
          cycles={undefined}
          activeCycle={null}
          onCycle={() => {}}
          onCycleScope={() => {}}
          {...actions}
        />
      </div>
    </section>
  )
}

export function GraphExplorer({ initial }: { initial: GraphView }) {
  const [report, setReport] = useState(true)
  const [expandedCycles, setExpandedCycles] = useState<Array<string>>([])
  const [returnContext, setReturnContext] = useState({
    scope: initial.scope,
    scroll: 0,
    originId: 'report-title',
  })
  const [scope, setScope] = useState<GraphScope>({ kind: 'repository' })
  const [selected, setSelected] = useState<string | null>(null)
  const view = useGraphView(initial, scope)
  if (
    view.error ||
    (view.data && view.data.state !== 'ready') ||
    view.data === null
  )
    return (
      <GraphLoadError
        message={view.error?.message}
        retry={() => {
          void view.refetch()
        }}
        back={() => setScope({ kind: 'repository' })}
      />
    )
  if (!view.data)
    return (
      <div className="loading-state" role="status">
        Loading the repository graph…
      </div>
    )
  const data = view.data
  const open = (node: GraphNode) => {
    const destination = node.destination
    const nextScope = destination?.scope ?? node.scope
    if (!nextScope) return
    setScope(nextScope)
    setSelected(destination?.focusId ?? null)
  }
  const navigate = (index: number) => {
    setScope(data.trail[index].scope)
    setSelected(null)
  }
  const explore = (destination: GraphScope, focus: string | null = null) => {
    setReturnContext({
      scope,
      scroll: window.scrollY,
      originId: document.activeElement?.id || 'report-title',
    })
    setScope(destination)
    setSelected(focus)
    setReport(false)
    window.scrollTo(0, 0)
  }
  if (report)
    return (
      <RepositoryReport
        view={data}
        navigate={navigate}
        onScope={setScope}
        onExplore={explore}
        expandedCycles={expandedCycles}
        onToggleCycle={(id, expanded) =>
          setExpandedCycles((ids) =>
            expanded
              ? [...new Set([...ids, id])]
              : ids.filter((key) => key !== id),
          )
        }
      />
    )
  return (
    <>
      <div className="project-return">
        <Button
          variant="outline"
          onClick={() => {
            setScope(returnContext.scope)
            setReport(true)
            restoreReadingPosition(returnContext.scroll, returnContext.originId)
          }}
        >
          Return to report
        </Button>
        <p>Project map · folders, files, functions, and connections</p>
      </div>
      <GraphWorkspace
        view={data}
        navigate={navigate}
        selected={selected}
        focusId={selected}
        onSelect={setSelected}
        onOpen={open}
      />
    </>
  )
}

function restoreReadingPosition(scroll: number, originId: string) {
  requestAnimationFrame(() => {
    window.scrollTo(0, scroll)
    document.getElementById(originId)?.focus({ preventScroll: true })
  })
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

function GraphLoadError({
  message,
  retry,
  back,
}: {
  message?: string
  retry: () => void
  back: () => void
}) {
  return (
    <div className="error-message" role="alert">
      <p>{message ?? 'This graph needs to be re-indexed.'}</p>
      <Button variant="outline" onClick={retry}>
        Try again
      </Button>
      <Button variant="outline" onClick={back}>
        Back to repository
      </Button>
    </div>
  )
}
