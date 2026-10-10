import { createFileRoute } from '@tanstack/react-router'
import {
  architectureScope,
  getArchitecture,
  repositoryErrorResponse,
} from '@/lib/repositories.servers'

export const Route = createFileRoute('/api/architecture')({
  server: {
    handlers: {
      GET: ({ request }) => {
        const parameters = new URL(request.url).searchParams
        const repositoryId = parameters.get('repositoryId')
        if (!repositoryId?.trim())
          return Response.json(
            { error: 'repositoryId is required' },
            { status: 400 },
          )
        try {
          return Response.json(
            getArchitecture(repositoryId, architectureScope(parameters)),
          )
        } catch (error) {
          return repositoryErrorResponse(error)
        }
      },
    },
  },
})
