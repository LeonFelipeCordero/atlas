import { useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Braces,
  ChevronRight,
  FileCode2,
  Folder,
  Search,
} from 'lucide-react'
import { GraphComplexity } from './graph-complexity'
import { GraphDependencyMetrics } from './graph-dependency-metrics'
import { GraphFileComplexity } from './graph-file-complexity'
import { GraphCycles } from './graph-cycles'
import type { CycleProps } from './graph-cycles'
import type { Artifact, ArtifactNode } from '@/lib/architecture-artifact'
import type { GraphNode, GraphScope, ProjectGraph } from '@/lib/project-graph'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type Props = CycleProps & {
  graph: ProjectGraph
  artifact: Artifact
  selected: string | null
  scope?: GraphScope
  onSelect: (id: string | null) => void
  onOpen: (node: GraphNode) => void
}

export function GraphSidebar({
  graph,
  artifact,
  selected,
  scope,
  onSelect,
  onOpen,
  ...cycleProps
}: Props) {
  const [search, setSearch] = useState('')
  const item = graph.nodes.find((node) => node.id === selected)
  if (item)
    return (
      <NodeDetails
        {...cycleProps}
        item={item}
        graph={graph}
        artifact={artifact}
        onSelect={onSelect}
        onOpen={onOpen}
      />
    )
  const localItems = graph.nodes.filter((node) => node.role !== 'boundary')
  const fileKey =
    scope?.kind === 'file'
      ? scope.key
      : localItems.length === 1 && localItems[0].kind === 'file'
        ? localItems[0].id
        : null
  const file = artifact.nodes.find((node) => node.stableKey === fileKey)
  const matches = graph.nodes.filter((node) =>
    `${node.label} ${node.path}`.toLowerCase().includes(search.toLowerCase()),
  )
  return (
    <aside className="graph-sidebar" aria-label="Graph contents">
      {file && (
        <div className="sidebar-file-summary">
          <p className="eyebrow">{file.name}</p>
          <GraphFileComplexity artifact={artifact} fileKey={file.stableKey} />
          <GraphDependencyMetrics node={file} />
        </div>
      )}
      <div className="sidebar-heading">
        <h3>In this view</h3>
        <span>{graph.nodes.length}</span>
      </div>
      <div className="search-field">
        <Search size={16} />
        <Input
          aria-label="Find in this view"
          placeholder="Find a folder, file, or function"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <div className="scope-items">
        {matches.map((node) => (
          <ScopeItem
            key={node.id}
            node={node}
            onSelect={onSelect}
            onOpen={onOpen}
          />
        ))}
        {!matches.length && (
          <p className="sidebar-hint">
            {search
              ? 'No matching items. Try another name or path.'
              : 'No items at this level.'}
          </p>
        )}
      </div>
      <GraphCycles artifact={artifact} {...cycleProps} />
    </aside>
  )
}

function ScopeItem({
  node,
  onSelect,
  onOpen,
}: {
  node: GraphNode
  onSelect: Props['onSelect']
  onOpen: Props['onOpen']
}) {
  const Icon =
    node.kind === 'folder' ? Folder : node.kind === 'file' ? FileCode2 : Braces
  return (
    <div className="scope-item">
      <button
        className="scope-select"
        onClick={() => onSelect(node.id)}
        title={node.path}
      >
        <Icon size={16} />
        <span>
          <strong>{node.label}</strong>
          <small>
            {node.role === 'boundary' ? 'Outside scope · ' : ''}
            {node.path || node.detail}
          </small>
        </span>
      </button>
      {(node.scope || node.destination) && (
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => onOpen(node)}
          aria-label={`Open ${node.path || node.label}`}
        >
          <ChevronRight />
        </Button>
      )}
    </div>
  )
}

function nodeTitle(item: GraphNode, original: ArtifactNode | undefined) {
  if (item.kind !== 'function' || !item.path) return item.path || item.label
  return `${item.path}${original?.startLine ? `:${original.startLine}` : ''} · ${item.label}`
}

function NodeSummary({
  item,
  artifact,
  original,
  onOpen,
}: {
  item: GraphNode
  artifact: Artifact
  original: ArtifactNode | undefined
  onOpen: Props['onOpen']
}) {
  return (
    <>
      <h3>{nodeTitle(item, original)}</h3>
      <p className="eyebrow">
        {item.kind}
        {item.role === 'boundary' ? ' · Outside scope' : ''}
      </p>
      {(item.scope || item.destination) && (
        <Button className="open-selected" onClick={() => onOpen(item)}>
          {item.destination ? 'Go to function' : `Explore ${item.kind}`}
          <ArrowRight />
        </Button>
      )}
      {item.kind === 'file' && (
        <GraphFileComplexity artifact={artifact} fileKey={item.id} />
      )}
      <NodeMetrics node={original} />
    </>
  )
}

function NodeMetrics({ node }: { node: ArtifactNode | undefined }) {
  if (!node) return null
  return (
    <>
      {['function', 'method'].includes(node.type) && (
        <GraphComplexity properties={node.properties} />
      )}
      {['module', 'file', 'type', 'callable'].includes(node.level) && (
        <GraphDependencyMetrics node={node} />
      )}
    </>
  )
}

function NodeDetails({
  item,
  graph,
  artifact,
  onSelect,
  onOpen,
  ...cycleProps
}: Omit<Props, 'selected'> & { item: GraphNode }) {
  const original = artifact.nodes.find((node) => node.stableKey === item.id)
  const connections = graph.edges.filter(
    (edge) => edge.source === item.id || edge.target === item.id,
  )
  const lookup = new Map(graph.nodes.map((node) => [node.id, node]))
  return (
    <aside className="graph-sidebar node-details" aria-label="Selected item">
      <Button
        variant="ghost"
        size="sm"
        className="back-to-list"
        onClick={() => onSelect(null)}
      >
        <ArrowLeft />
        All items
      </Button>
      <NodeSummary
        item={item}
        artifact={artifact}
        original={original}
        onOpen={onOpen}
      />
      <div className="section-heading">
        <h4>Connections</h4>
        <span>{connections.length}</span>
      </div>
      <div className="connection-list">
        {connections.map((edge) => {
          const outgoing = edge.source === item.id
          const other = lookup.get(outgoing ? edge.target : edge.source)!
          return (
            <button
              key={edge.id}
              className="connection"
              onClick={() => onSelect(other.id)}
              title={other.path}
            >
              <span>
                {outgoing ? <ArrowRight size={15} /> : <ArrowLeft size={15} />}
                {outgoing ? 'Uses' : 'Used by'} <strong>{other.label}</strong>
              </span>
            </button>
          )
        })}
        {!connections.length && (
          <p className="sidebar-hint">
            No connections recorded here. This doesn’t imply the item is unused.
          </p>
        )}
      </div>
      <GraphCycles artifact={artifact} item={item} {...cycleProps} />
    </aside>
  )
}
