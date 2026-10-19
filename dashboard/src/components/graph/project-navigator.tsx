import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Braces,
  ChevronDown,
  ChevronRight,
  FileCode2,
  Folder,
  Search,
} from 'lucide-react'
import type { Architecture, GraphView } from '@/lib/graph-data'
import type { GraphNode, GraphScope } from '@/lib/project-graph'
import { api } from '@/lib/api'
import { Input } from '@/components/ui/input'

export function scopeQuery(initial: GraphView, scope: GraphScope) {
  return {
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
  }
}

type Props = {
  initial: GraphView
  scope: GraphScope
  trail: GraphView['trail']
  selected: string | null
  onScope: (scope: GraphScope) => void
  onOpen: (node: GraphNode) => void
  onSelect: (id: string | null) => void
}

function NavigatorBranch({
  node,
  ownerScope,
  ...props
}: Props & { node: GraphNode; ownerScope?: GraphScope }) {
  const [expanded, setExpanded] = useState(false)
  const destination = node.destination?.scope ?? node.scope
  const current =
    destination && JSON.stringify(destination) === JSON.stringify(props.scope)
  const inTrail = props.trail.some(
    (entry) => JSON.stringify(entry.scope) === JSON.stringify(destination),
  )
  useEffect(() => {
    if (inTrail) setExpanded(true)
  }, [inTrail])
  const children = useQuery({
    ...scopeQuery(props.initial, destination ?? props.scope),
    enabled: Boolean(destination && expanded),
  })
  const Icon =
    node.kind === 'folder' ? Folder : node.kind === 'file' ? FileCode2 : Braces
  return (
    <li>
      <div
        className="navigator-row"
        data-current={current || props.selected === node.id}
      >
        {destination ? (
          <button
            className="navigator-toggle"
            aria-label={`${expanded ? 'Collapse' : 'Expand'} ${node.path || node.label}`}
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        ) : (
          <span className="navigator-spacer" />
        )}
        <button
          className="navigator-item"
          aria-current={current ? 'location' : undefined}
          title={node.path || node.label}
          onClick={() => {
            if (destination) {
              setExpanded(true)
              props.onOpen(node)
            } else {
              if (ownerScope) props.onScope(ownerScope)
              props.onSelect(node.id)
            }
          }}
        >
          <Icon size={15} />
          <span>{node.label}</span>
        </button>
      </div>
      {expanded && destination && (
        <ul>
          {children.isPending && (
            <li className="navigator-message" role="status">
              Loading…
            </li>
          )}
          {(children.error ||
            (children.data && children.data.state !== 'ready') ||
            children.data === null) && (
            <li className="navigator-message">
              <button onClick={() => void children.refetch()}>
                Could not load. Retry
              </button>
            </li>
          )}
          {children.data?.state === 'ready' &&
            children.data.graph.nodes
              .filter((item) => item.role !== 'boundary')
              .map((item) => (
                <NavigatorBranch
                  key={item.id}
                  node={item}
                  ownerScope={destination}
                  {...props}
                />
              ))}
          {children.data?.state === 'ready' &&
            !children.data.graph.nodes.some(
              (item) => item.role !== 'boundary',
            ) && <li className="navigator-message">No indexed items</li>}
        </ul>
      )}
    </li>
  )
}

export function ProjectNavigator(props: Props) {
  const [search, setSearch] = useState('')
  const roots = props.initial.graph.nodes.filter(
    (node) => node.role !== 'boundary',
  )
  const matches = roots.filter((node) =>
    `${node.path} ${node.label}`.toLowerCase().includes(search.toLowerCase()),
  )
  return (
    <nav className="project-navigator" aria-label="Project navigator">
      <div className="navigator-heading">
        <h2>Project</h2>
        <span>Files & folders</span>
      </div>
      <div className="search-field">
        <Search size={16} />
        <Input
          aria-label="Filter project roots"
          placeholder="Filter project roots…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <button
        className="navigator-root"
        aria-current={
          props.scope.kind === 'repository' ? 'location' : undefined
        }
        onClick={() => props.onScope({ kind: 'repository' })}
      >
        <Folder size={16} />
        {props.initial.rootName || props.initial.trail[0].label}
      </button>
      <ul className="navigator-tree">
        {matches.map((node) => (
          <NavigatorBranch key={node.id} node={node} {...props} />
        ))}
      </ul>
      {!matches.length && (
        <p className="navigator-message">
          {search ? 'No matching project roots.' : 'No indexed items.'}
        </p>
      )}
      <p className="navigator-note">
        Indexed structure only.
        <br />
        Expand folders to browse their contents.
      </p>
    </nav>
  )
}
