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
  onSelect: (id: string | null) => void
  onOpen: (node: GraphNode) => void
}

function canvasEdges(graph: ProjectGraph, selected: string | null) {
  return graph.edges.map((edge) =>
    canvasEdge({
      edge,
      active: edge.source === selected || edge.target === selected,
      hasSelection: Boolean(selected),
    }),
  )
}

type CanvasEdgeOptions = {
  edge: GraphEdge
  active: boolean
  hasSelection: boolean
}

function canvasEdge({ edge, active, hasSelection }: CanvasEdgeOptions) {
  const color = active ? 'var(--primary)' : 'var(--graph-edge)'
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'default',
    markerEnd: { type: MarkerType.ArrowClosed, color },
    label: edge.count > 1 ? String(edge.count) : undefined,
    labelStyle: { fill: 'var(--muted-foreground)', fontSize: 11 },
    labelBgStyle: { fill: 'var(--background)' },
    style: {
      stroke: color,
      strokeWidth: active ? 2.5 : 1.4,
      opacity: hasSelection && !active ? 0.12 : 0.75,
    },
    ariaLabel: `${edge.count} relationships from ${edge.source} to ${edge.target}`,
  }
}

type CanvasNodeOptions = {
  item: GraphNode
  position: { x: number; y: number }
  onOpen: Props['onOpen']
  selected: string | null
  related: Set<string>
}

function canvasNode({
  item,
  position,
  onOpen,
  selected,
  related,
}: CanvasNodeOptions) {
  return {
    id: item.id,
    type: 'code' as const,
    position,
    data: {
      item,
      open: onOpen,
      muted: Boolean(selected && selected !== item.id && !related.has(item.id)),
    },
    selected: item.id === selected,
    ariaLabel: `${item.kind}: ${item.path || item.label}.${item.role === 'boundary' ? ' Outside scope dependency.' : ''} Select to inspect connections.`,
  }
}

function Canvas({ graph, selected, focusId, onSelect, onOpen }: Props) {
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
    const position = focusId ? positions.get(focusId) : undefined
    if (position) {
      void setCenter(position.x + 110, position.y + 39, { zoom: 1 })
      return
    }
    void fitView({ padding: 0.15, minZoom: 0.85, maxZoom: 1 })
  }, [focusId, positions, setCenter, fitView])
  const nodes = useMemo(
    () =>
      graph.nodes.map((item) =>
        canvasNode({
          item,
          position: positions.get(item.id)!,
          onOpen,
          selected,
          related,
        }),
      ),
    [graph, positions, onOpen, selected, related],
  )
  const edges = useMemo(() => canvasEdges(graph, selected), [graph, selected])
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.15, minZoom: 0.85, maxZoom: 1 }}
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
      <Controls
        showInteractive={false}
        fitViewOptions={{ padding: 0.15, minZoom: 0.03 }}
      />
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
