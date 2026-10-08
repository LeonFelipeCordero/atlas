import { createFileRoute } from '@tanstack/react-router'
import {
  listRepositories,
  registerRepository,
  repositoryErrorResponse,
} from '@/lib/repositories.servers'

export const Route = createFileRoute('/api/repositories')({
  server: {
    handlers: {
      GET: () => {
        try {
          return Response.json(listRepositories())
        } catch (error) {
          return repositoryErrorResponse(error)
        }
      },
      POST: async ({ request }) => {
        let input: unknown
        try {
          input = await request.json()
        } catch {
          return Response.json({ error: 'Invalid JSON body' }, { status: 400 })
        }
        try {
          return Response.json(registerRepository(input), { status: 201 })
        } catch (error) {
          return repositoryErrorResponse(error)
        }
      },
    },
  },
})
