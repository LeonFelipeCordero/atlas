import type { Artifact } from './architecture-artifact'

export type Repository = {
  id: string
  name: string
  location: string
  createdAt: number
  importedAt: number | null
}

export type ImportedGraph = {
  repositoryId: string
  importedAt: number
  artifact: Artifact
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options)
  const data = await response.json()
  if (!response.ok)
    throw new Error(data.error ?? 'Something went wrong. Please try again.')
  return data as T
}

export const repositoriesQuery = {
  queryKey: ['repositories'],
  queryFn: () => api<Array<Repository>>('/api/repositories'),
}

export const formatDate = (timestamp: number) =>
  new Date(timestamp).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

export const indexCommand = (name: string) =>
  `bun run architecture:index <repository-path> --project '${name.replaceAll("'", "'\\''")}'`
