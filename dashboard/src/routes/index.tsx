import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { ArrowRight, FolderGit2, Plus, X } from 'lucide-react'
import { repositoriesQuery } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { RepositoryRow } from '@/components/repository-row'
import { RepositoryForm } from '@/components/repository-form'

export const Route = createFileRoute('/')({ component: RepositoriesPage })

function RepositoriesPage() {
  const repositories = useQuery(repositoriesQuery)
  const [showForm, setShowForm] = useState(false)
  const isEmpty = repositories.data?.length === 0
  return (
    <main id="main" className="page repositories-page">
      {(showForm || isEmpty) && (
        <RepositoryForm onCreated={() => setShowForm(false)} />
      )}
      <section
        aria-labelledby="repositories-title"
        className="repository-section"
      >
        <div className="section-heading">
          <h1 id="repositories-title">
            Your repositories <span>{repositories.data?.length ?? ''}</span>
          </h1>
          {!isEmpty && (
            <Button
              variant={showForm ? 'outline' : 'default'}
              onClick={() => setShowForm(!showForm)}
            >
              {showForm ? <X /> : <Plus />}
              {showForm ? 'Cancel' : 'Add repository'}
            </Button>
          )}
        </div>
        {repositories.isPending && (
          <div className="loading-state" role="status">
            Loading repositories…
          </div>
        )}
        {repositories.error && (
          <div className="error-message" role="alert">
            {repositories.error.message}{' '}
            <Button
              variant="outline"
              onClick={() => void repositories.refetch()}
            >
              Try again
            </Button>
          </div>
        )}
        {isEmpty && (
          <div className="empty-repositories">
            <FolderGit2 size={30} />
            <h3>A clearer view starts here.</h3>
            <p>
              Add your first repository above. Your indexed graph will be ready
              to explore here.
            </p>
            <div className="level-preview">
              Folders at any depth <ArrowRight /> Files <ArrowRight /> Functions
            </div>
          </div>
        )}
        <div className="repository-list">
          {repositories.data?.map((repository) => (
            <RepositoryRow key={repository.id} repository={repository} />
          ))}
        </div>
      </section>
    </main>
  )
}
