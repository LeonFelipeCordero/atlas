import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GraphWorkspace } from './graph-workspace'
import { scopeQuery } from './project-navigator'
import type { GraphView } from '@/lib/graph-data'
import type { GraphNode, GraphScope } from '@/lib/project-graph'
import { Button } from '@/components/ui/button'

export function GraphExplorer({ initial }: { initial: GraphView }) {
  const [scope, setScope] = useState<GraphScope>({ kind: 'repository' })
  const [selected, setSelected] = useState<string | null>(null)
  const [cycleId, setCycleId] = useState<string | null>(null)
  const view = useQuery(scopeQuery(initial, scope))
  const failed =
    view.error ||
    (view.data && view.data.state !== 'ready') ||
    view.data === null
  const status = failed ? (
    <div className="error-message" role="alert">
      <p>{view.error?.message ?? 'This graph needs to be re-indexed.'}</p>
      <Button variant="outline" onClick={() => void view.refetch()}>
        Try again
      </Button>
      <Button
        variant="outline"
        onClick={() => setScope({ kind: 'repository' })}
      >
        Back to repository
      </Button>
    </div>
  ) : !view.data ? (
    <div className="loading-state" role="status">
      Loading the repository graph…
    </div>
  ) : null
  const data = view.data?.state === 'ready' ? view.data : initial
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
      initial={initial}
      status={status}
      requestedScope={scope}
      view={data}
      onScope={(next) => {
        setScope(next)
        select(null)
      }}
      navigate={navigate}
      selected={selected}
      focusId={cycleId !== null ? null : selected}
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
