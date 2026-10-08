import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, createFileRoute } from '@tanstack/react-router'
import { ArrowLeft, Network, RefreshCw, Terminal } from 'lucide-react'
import type { UseQueryResult } from '@tanstack/react-query'
import type { ImportedGraph } from '@/lib/api'
import { api, formatDate, repositoriesQuery } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ImportHelp } from '@/components/import-help'
import { GraphExplorer } from '@/components/graph/graph-explorer'

export const Route = createFileRoute('/graph/$repositoryId')({
  component: GraphPage,
})

function GraphPage() {
  const { repositoryId } = Route.useParams()
  const repositories = useQuery(repositoriesQuery)
  const graph = useQuery({
    queryKey: ['graph', repositoryId],
    queryFn: () =>
      api<ImportedGraph | null>(
        `/api/architecture?repositoryId=${encodeURIComponent(repositoryId)}`,
      ),
    retry: false,
  })
  const repository = repositories.data?.find(
    (entry) => entry.id === repositoryId,
  )
  const [showImport, setShowImport] = useState(false)
  const refresh = () => {
    void graph.refetch()
    void repositories.refetch()
  }
  return (
    <main id="main" className="page graph-page">
      <Link to="/" className="back-link">
        <ArrowLeft size={15} />
        All repositories
      </Link>
      <div className="graph-page-heading">
        <div>
          <h1>
            {repository?.name ??
              graph.data?.artifact.repository.name ??
              'Repository'}
          </h1>
          <p className="repository-location">{repository?.location}</p>
        </div>
        <div className="graph-actions">
          <Button
            variant="outline"
            onClick={() => setShowImport(!showImport)}
            aria-expanded={showImport}
          >
            <Terminal />
            Index instructions
          </Button>
          <Button
            variant="outline"
            onClick={refresh}
            disabled={graph.isFetching}
          >
            <RefreshCw className={graph.isFetching ? 'refreshing' : ''} />
            {graph.isFetching ? 'Refreshing…' : 'Refresh graph'}
          </Button>
        </div>
      </div>
      {showImport && repository && (
        <ImportHelp repositoryName={repository.name} />
      )}
      <GraphContent
        graph={graph}
        repositoryId={repositoryId}
        repositoryName={repository?.name}
        showImport={showImport}
        refresh={refresh}
      />
    </main>
  )
}

function GraphContent({
  graph,
  repositoryId,
  repositoryName,
  showImport,
  refresh,
}: {
  graph: UseQueryResult<ImportedGraph | null>
  repositoryId: string
  repositoryName: string | undefined
  showImport: boolean
  refresh: () => void
}) {
  return (
    <>
      {graph.isPending && (
        <div className="loading-state graph-loading" role="status">
          Loading the repository graph…
        </div>
      )}
      {graph.error && (
        <div className="error-message" role="alert">
          <h2>Couldn’t load this graph</h2>
          <p>{graph.error.message}</p>
          <Button variant="outline" onClick={refresh}>
            Try again
          </Button>
        </div>
      )}
      {graph.data === null && !graph.error && repositoryName && (
        <WaitingForImport
          repositoryName={repositoryName}
          showImport={showImport}
        />
      )}
      {graph.data && (
        <>
          <div className="import-status">
            <span className="status-dot" />
            Indexed {formatDate(graph.data.importedAt)}
          </div>
          <GraphExplorer
            key={`${repositoryId}:${graph.data.importedAt}`}
            artifact={graph.data.artifact}
          />
        </>
      )}
    </>
  )
}

function WaitingForImport({
  repositoryName,
  showImport,
}: {
  repositoryName: string
  showImport: boolean
}) {
  return (
    <section className="waiting-for-import">
      <div>
        <span className="waiting-icon">
          <Network size={32} />
        </span>
        <h2>Your repository is registered.</h2>
        <p>
          Run the Python indexer on your local source directory to see how the
          code connects. The graph saves directly to the database.
        </p>
      </div>
      {!showImport && <ImportHelp repositoryName={repositoryName} />}
    </section>
  )
}
