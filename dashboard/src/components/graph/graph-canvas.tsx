import { useEffect, useMemo } from 'react'
import {
  Background,
  BackgroundVariant,
  BaseEdge,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react'
import { ArrowRight, Braces, FileCode2, Folder } from 'lucide-react'
import {
  GRAPH_NODE_HEIGHT,
  GRAPH_NODE_WIDTH,
  layoutGraph,
} from './graph-layout'
import {
  getGraphEdgeChannels,
  getGraphEdgeHandles,
  getGraphEdgePath,
} from './graph-edge-routing'
import type { EdgeChannels } from './graph-edge-routing'
import type { Edge, EdgeProps, Node, NodeProps } from '@xyflow/react'
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
      <Handle id="target-top" type="target" position={Position.Top} />
      <Handle id="target-left" type="target" position={Position.Left} />
      <div className="code-node-heading">
        <Icon size={18} />
        <strong title={data.item.label}>{data.item.label}</strong>
      </div>
      <CodeNodeAction item={data.item} open={data.open} />
      <Handle id="source-right" type="source" position={Position.Right} />
      <Handle id="source-bottom" type="source" position={Position.Bottom} />
    </div>
  )
}

function CodeGraphEdge(props: EdgeProps<Edge<EdgeChannels>>) {
  if (!props.data) return null
  const path = getGraphEdgePath(
    { x: props.sourceX, y: props.sourceY },
    { x: props.targetX, y: props.targetY },
    props.sourcePosition,
    props.targetPosition,
    props.data,
  )
  return (
    <BaseEdge
      id={props.id}
      path={path}
      markerEnd={props.markerEnd}
      style={props.style}
    />
  )
}

const nodeTypes = { code: CodeGraphNode }
const edgeTypes = { code: CodeGraphEdge }
// Include the 40 px outer corridors at the maximum 1.6 zoom.
const fitViewOptions = { padding: '72px' as const }
type Props = {
  graph: ProjectGraph
  selected: string | null
  focusId: string | null
  onSelect: (id: string | null) => void
  onOpen: (node: GraphNode) => void
}

function canvasEdges(
  graph: ProjectGraph,
  selected: string | null,
  positions: ReturnType<typeof layoutGraph>,
) {
  return graph.edges.map((edge) => {
    const active = edge.source === selected || edge.target === selected
    return canvasEdge({
      edge,
      handles: getGraphEdgeHandles(
        positions.get(edge.source),
        positions.get(edge.target),
      ),
      channels: getGraphEdgeChannels(
        positions.get(edge.source)!,
        positions.get(edge.target)!,
        positions,
      ),
      active,
      hasSelection: Boolean(selected),
    })
  })
}

type CanvasEdgeOptions = {
  edge: GraphEdge
  handles: ReturnType<typeof getGraphEdgeHandles>
  channels: EdgeChannels
  active: boolean
  hasSelection: boolean
}

function canvasEdge({
  edge,
  handles,
  channels,
  active,
  hasSelection,
}: CanvasEdgeOptions) {
  const color = active ? 'var(--primary)' : 'var(--graph-edge)'
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    ...handles,
    type: 'code',
    data: channels,
    markerEnd: { type: MarkerType.ArrowClosed, color },
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
      void setCenter(
        position.x + GRAPH_NODE_WIDTH / 2,
        position.y + GRAPH_NODE_HEIGHT / 2,
        { zoom: 1 },
      )
      return
    }
    void fitView(fitViewOptions)
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
  const edges = useMemo(
    () => canvasEdges(graph, selected, positions),
    [graph, selected, positions],
  )
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={fitViewOptions}
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
