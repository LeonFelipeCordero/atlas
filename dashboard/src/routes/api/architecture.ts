import { createFileRoute } from '@tanstack/react-router'
import {
  getArchitecture,
  repositoryErrorResponse,
} from '@/lib/repositories.servers'

export const Route = createFileRoute('/api/architecture')({
  server: {
    handlers: {
      GET: ({ request }) => {
        const repositoryId = new URL(request.url).searchParams.get(
          'repositoryId',
        )
        if (!repositoryId?.trim())
          return Response.json(
            { error: 'repositoryId is required' },
            { status: 400 },
          )
        try {
          return Response.json(getArchitecture(repositoryId))
        } catch (error) {
          return repositoryErrorResponse(error)
        }
      },
    },
  },
})
