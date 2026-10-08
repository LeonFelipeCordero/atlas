import { Suspense, lazy, useCallback, useMemo, useState } from 'react'
import { Network } from 'lucide-react'
import { GraphSidebar } from './graph-sidebar'
import { GraphNavigation } from './graph-navigation'
import { GraphFileComplexity } from './graph-file-complexity'
import type { ComponentProps } from 'react'
import type { Artifact } from '@/lib/architecture-artifact'
import type { GraphNode, GraphScope } from '@/lib/project-graph'
import { buildProjectGraph, getGraphTrail } from '@/lib/project-graph'
import { Button } from '@/components/ui/button'
import { projectCycles } from '@/lib/graph-cycles'
import { hideTestFiles } from '@/lib/graph-visibility'

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

export function GraphExplorer({ artifact }: { artifact: Artifact }) {
  const [scope, setScope] = useState<GraphScope>({ kind: 'repository' })
  const visibleArtifact = useMemo(() => hideTestFiles(artifact), [artifact])
  const trail = useMemo(
    () => getGraphTrail(visibleArtifact, scope),
    [visibleArtifact, scope],
  )
  const [selected, setSelected] = useState<string | null>(null)
  const [cycleId, setCycleId] = useState<string | null>(null)
  const [focusId, setFocusId] = useState<string | null>(null)
  const current = trail[trail.length - 1]
  const graph = useMemo(
    () => buildProjectGraph(visibleArtifact, current.scope),
    [visibleArtifact, current.scope],
  )
  const cycles = useMemo(
    () => projectCycles(artifact, graph, current.scope),
    [artifact, graph, current.scope],
  )
  const activeCycle =
    cycles?.find((cycle) => cycle.group.id === cycleId) ?? null
  const select = (id: string | null) => {
    setCycleId(null)
    setSelected(id)
    setFocusId(id)
  }
  const open = useCallback(
    (node: GraphNode) => {
      const destination = node.destination
      const nextScope = destination?.scope ?? node.scope
      if (!nextScope) return
      setCycleId(null)
      setScope(nextScope)
      setSelected(destination?.focusId ?? null)
      setFocusId(destination?.focusId ?? null)
    },
    [setScope],
  )
  const navigate = (index: number) => {
    setCycleId(null)
    setScope(trail[index].scope)
    setSelected(null)
    setFocusId(null)
  }
  return (
    <section className="explorer" aria-label="Project graph">
      <GraphNavigation trail={trail} navigate={navigate} />
      {current.scope.kind === 'file' && (
        <GraphFileComplexity
          artifact={artifact}
          fileKey={current.scope.key}
          compact
        />
      )}
      <div className="graph-workspace">
        <div
          className="graph-canvas"
          role="region"
          aria-label={`${current.label} dependency graph`}
        >
          <GraphViewport
            key={JSON.stringify(current.scope)}
            graph={graph}
            selected={selected}
            focusId={focusId}
            activeCycle={activeCycle}
            onSelect={select}
            onOpen={open}
            isFile={current.scope.kind === 'file'}
            back={
              trail.length > 1 ? () => navigate(trail.length - 2) : undefined
            }
          />
        </div>
        <GraphSidebar
          key={JSON.stringify(current.scope)}
          graph={graph}
          artifact={artifact}
          selected={selected}
          scope={current.scope}
          cycles={cycles}
          activeCycle={activeCycle}
          onCycle={(cycle) => {
            setCycleId(cycle.group.id)
            setFocusId(null)
          }}
          onCycleScope={(cycle) => {
            setScope(cycle.scope)
            setSelected(null)
            setFocusId(null)
            setCycleId(cycle.group.id)
          }}
          onSelect={select}
          onOpen={open}
        />
      </div>
    </section>
  )
}
