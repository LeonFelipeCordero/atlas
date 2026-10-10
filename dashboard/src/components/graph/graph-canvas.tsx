import { useEffect, useMemo } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react'
import { ArrowRight, Braces, FileCode2, Folder } from 'lucide-react'
import { layoutGraph } from './graph-layout'
import type { ProjectedCycle } from '@/lib/graph-cycles'
import type { Node, NodeProps } from '@xyflow/react'
import type { GraphEdge, GraphNode, ProjectGraph } from '@/lib/project-graph'
import '@xyflow/react/dist/style.css'

type CodeNode = Node<
  { item: GraphNode; open: (node: GraphNode) => void; muted: boolean },
  'code'
>

const nodeIcons = { folder: Folder, file: FileCode2, function: Braces }

function CodeNodeAction({
  item,
  open,
}: {
  item: GraphNode
  open: (node: GraphNode) => void
}) {
  if (!item.scope && !item.destination)
    return <span className="node-kind">{item.detail.split(' · ')[0]}</span>
  return (
    <button
      className="nodrag nopan node-open"
      onClick={(event) => {
        event.stopPropagation()
        open(item)
      }}
      aria-label={`Explore ${item.path || item.label}`}
    >
      {item.destination ? 'Go to function' : `Explore ${item.kind}`}
      <ArrowRight size={13} />
    </button>
  )
}

function CodeGraphNode({ data, selected }: NodeProps<CodeNode>) {
  const Icon = nodeIcons[data.item.kind]
  return (
    <div
      className={`code-node ${selected ? 'is-selected' : ''} ${data.muted ? 'is-muted' : ''} ${data.item.role === 'boundary' ? 'is-boundary' : ''}`}
    >
      <Handle type="target" position={Position.Left} />
      <div className="code-node-heading">
        <Icon size={18} />
        <strong title={data.item.label}>{data.item.label}</strong>
      </div>
      <CodeNodeAction item={data.item} open={data.open} />
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

const nodeTypes = { code: CodeGraphNode }
type Props = {
  graph: ProjectGraph
  selected: string | null
  focusId: string | null
  activeCycle: ProjectedCycle | null
  onSelect: (id: string | null) => void
  onOpen: (node: GraphNode) => void
}

function canvasEdges(
  graph: ProjectGraph,
  selected: string | null,
  cycle: ProjectedCycle | null,
) {
  const highlighted = new Set(cycle?.edges.map((edge) => edge.id))
  const edges = [...graph.edges]
  for (const edge of cycle?.edges ?? []) {
    if (!edges.some((existing) => existing.id === edge.id))
      edges.push({ ...edge, count: 1, relationships: { IMPORTS: 1 } })
  }
  return edges.map((edge) => {
    const active = cycle
      ? highlighted.has(edge.id)
      : edge.source === selected || edge.target === selected
    return canvasEdge({
      edge,
      active,
      cycleImport: Boolean(cycle && active),
      hasSelection: Boolean(cycle || selected),
    })
  })
}

function edgeLabel(edge: GraphEdge, cycleImport: boolean) {
  if (cycleImport) return 'Cycle import'
  return edge.count > 1 ? String(edge.count) : undefined
}

type CanvasEdgeOptions = {
  edge: GraphEdge
  active: boolean
  cycleImport: boolean
  hasSelection: boolean
}

function canvasEdge({
  edge,
  active,
  cycleImport,
  hasSelection,
}: CanvasEdgeOptions) {
  const color = active ? 'var(--primary)' : 'var(--graph-edge)'
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'default',
    markerEnd: { type: MarkerType.ArrowClosed, color },
    label: edgeLabel(edge, cycleImport),
    labelStyle: { fill: 'var(--muted-foreground)', fontSize: 11 },
    labelBgStyle: { fill: 'var(--background)' },
    style: {
      stroke: color,
      strokeWidth: active ? 2.5 : 1.4,
      opacity: hasSelection && !active ? 0.12 : 0.75,
    },
    ariaLabel: `${cycleImport ? 'Cycle import' : `${edge.count} relationships`} from ${edge.source} to ${edge.target}`,
  }
}

type CanvasNodeOptions = {
  item: GraphNode
  position: { x: number; y: number }
  onOpen: Props['onOpen']
  selected: string | null
  related: Set<string>
  activeCycle: ProjectedCycle | null
}

function canvasNode({
  item,
  position,
  onOpen,
  selected,
  related,
  activeCycle,
}: CanvasNodeOptions) {
  return {
    id: item.id,
    type: 'code' as const,
    position,
    data: {
      item,
      open: onOpen,
      muted: Boolean(
        activeCycle
          ? !activeCycle.nodeIds.includes(item.id)
          : selected && selected !== item.id && !related.has(item.id),
      ),
    },
    selected: activeCycle
      ? activeCycle.nodeIds.includes(item.id)
      : item.id === selected,
    ariaLabel: `${item.kind}: ${item.path || item.label}.${item.role === 'boundary' ? ' Outside scope dependency.' : ''} Select to inspect connections.`,
  }
}

function Canvas({
  graph,
  selected,
  focusId,
  activeCycle,
  onSelect,
  onOpen,
}: Props) {
  const positions = useMemo(() => layoutGraph(graph), [graph])
  const related = useMemo(
    () =>
      new Set(
        graph.edges
          .filter(
            (edge) => edge.source === selected || edge.target === selected,
          )
          .flatMap((edge) => [edge.source, edge.target]),
      ),
    [graph, selected],
  )
  const { setCenter, fitView } = useReactFlow()
  useEffect(() => {
    if (activeCycle?.nodeIds.length) {
      void fitView({
        nodes: activeCycle.nodeIds.map((id) => ({ id })),
        padding: 0.25,
      })
      return
    }
    const position = focusId ? positions.get(focusId) : undefined
    if (position) {
      void setCenter(position.x + 110, position.y + 39, { zoom: 1 })
      return
    }
    void fitView({ padding: 0.15 })
  }, [activeCycle, focusId, positions, setCenter, fitView])
  const nodes = useMemo(
    () =>
      graph.nodes.map((item) =>
        canvasNode({
          item,
          position: positions.get(item.id)!,
          onOpen,
          selected,
          related,
          activeCycle,
        }),
      ),
    [graph, positions, onOpen, selected, related, activeCycle],
  )
  const edges = useMemo(
    () => canvasEdges(graph, selected, activeCycle),
    [graph, selected, activeCycle],
  )
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      minZoom={0.03}
      maxZoom={1.6}
      nodesDraggable={false}
      nodesConnectable={false}
      edgesFocusable={false}
      onNodeClick={(_, node) => onSelect(node.id)}
      onNodeDoubleClick={(_, node) => onOpen(node.data.item)}
      onPaneClick={() => onSelect(null)}
      onEdgeClick={(_, edge) => onSelect(edge.source)}
      proOptions={{ hideAttribution: false }}
    >
      <Background
        variant={BackgroundVariant.Dots}
        gap={24}
        size={1}
        color="var(--border)"
      />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}

export default function GraphCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  )
}
