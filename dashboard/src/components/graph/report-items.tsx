import { useState } from 'react'
import { ReportItem } from './report-item'
import type { ArtifactNode } from '@/lib/architecture-artifact'
import type { GraphView } from '@/lib/graph-data'
import type { GraphNode } from '@/lib/project-graph'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export type ReportItemProps = {
  view: GraphView
  selected: string | null
  onSelect: (id: string | null) => void
  onOpen: (node: GraphNode) => void
  onExplore: (node?: GraphNode) => void
}

export function ReportItems(props: ReportItemProps) {
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('all')
  const { view } = props
  const lookup = new Map(view.graph.nodes.map((node) => [node.id, node]))
  const matches = view.details.nodes.filter(
    (node) =>
      `${node.name} ${node.path} ${node.qualifiedName ?? ''}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (kind === 'all' ||
        (kind === 'boundary'
          ? lookup.get(node.stableKey)?.role === 'boundary'
          : node.level === kind)),
  )
  const local = matches.filter(
    (node) => lookup.get(node.stableKey)?.role !== 'boundary',
  )
  const boundary = matches.filter(
    (node) => lookup.get(node.stableKey)?.role === 'boundary',
  )
  return (
    <section aria-label="Item measurements" className="report-measurements">
      <h3>Item measurements</h3>
      <p className="sidebar-hint">
        Open an item for actual values, source location, and connections. Use
        its report link to inspect the next level without opening the graph.
      </p>
      <div className="report-controls">
        <label>
          Find an item
          <Input
            placeholder="Name, path, or qualified name"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label>
          Item type
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            <option value="all">All items</option>
            <option value="module">Folders</option>
            <option value="file">Files</option>
            <option value="callable">Functions and methods</option>
            <option value="boundary">Outside scope</option>
          </select>
        </label>
      </div>
      <p className="report-result-count" role="status">
        {matches.length} of {view.details.nodes.length} items
      </p>
      {!matches.length && (
        <p>No matching items. Change the search or item type.</p>
      )}
      <ItemGroup title="In this scope" nodes={local} {...props} />
      <ItemGroup
        title="Outside scope · outgoing references"
        nodes={boundary}
        {...props}
      />
    </section>
  )
}

function ItemGroup({
  title,
  nodes,
  ...props
}: ReportItemProps & { title: string; nodes: Array<ArtifactNode> }) {
  if (!nodes.length) return null
  return (
    <section className="report-item-group">
      <h4>
        {title} · {nodes.length}
      </h4>
      {nodes.map((node) => (
        <ItemRecord key={node.stableKey} node={node} {...props} />
      ))}
    </section>
  )
}

function ItemRecord({
  node,
  view,
  selected,
  onSelect,
  onOpen,
  onExplore,
}: ReportItemProps & { node: ArtifactNode }) {
  const item = view.graph.nodes.find((entry) => entry.id === node.stableKey)
  const expanded = selected === node.stableKey
  return (
    <details className="report-record" open={expanded}>
      <summary
        onClick={(event) => {
          event.preventDefault()
          onSelect(expanded ? null : node.stableKey)
        }}
      >
        <strong>{node.name}</strong>
        <span>{node.path || node.qualifiedName || node.kind}</span>
        <small>
          {node.kind}
          {node.properties?.cyclomaticComplexity !== undefined &&
            ` · Weighted complexity ${node.properties.cyclomaticComplexity}`}
          {node.properties?.lineCount !== undefined &&
            ` · ${node.properties.lineCount} lines`}
        </small>
      </summary>
      {expanded && (
        <>
          <ReportItem
            node={node}
            item={item}
            view={view}
            onExplore={onExplore}
          />
          {item?.scope && (
            <Button
              className="report-drill"
              variant="outline"
              size="sm"
              onClick={() => onOpen(item)}
            >
              Report on {node.name}
            </Button>
          )}
        </>
      )}
    </details>
  )
}
