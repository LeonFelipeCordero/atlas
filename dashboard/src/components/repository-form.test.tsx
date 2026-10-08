import { expect, test } from 'bun:test'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { RepositoryForm } from './repository-form'

test('registration explains folder-based indexing rather than URL metadata', () => {
  const markup = renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <RepositoryForm onCreated={() => {}} />
    </QueryClientProvider>,
  )
  expect(markup).toContain('Local folder path')
  expect(markup).toContain('placeholder="/path/to/project"')
  expect(markup).toContain('Use the folder you will index with -f')
  expect(markup).not.toContain('URL or local path')
})
