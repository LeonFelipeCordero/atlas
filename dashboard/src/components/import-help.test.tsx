import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { ImportHelp } from './import-help'
import { indexCommand } from '@/lib/api'

test('index instructions render the registered folder as a literal shell argument', () => {
  for (const repositoryLocation of [
    "/source/Engineer's École $app",
    '/source/$(exit 12) `exit 13` "$HOME"; exit 14',
    '/source/line one\nline two',
    '/source/--project',
  ]) {
    const markup = renderToStaticMarkup(
      <ImportHelp repositoryLocation={repositoryLocation} />,
    )
    expect(markup).toContain(
      renderToStaticMarkup(<code>{indexCommand(repositoryLocation)}</code>),
    )
    expect(markup).toContain('aria-label="Copy index command"')
    expect(markup).toContain('registered location')
    expect(markup).not.toContain('&lt;repository-path&gt;')
  }
})

test('legacy URL and relative locations explain how to index a local checkout', () => {
  for (const repositoryLocation of [
    'https://example.com/project',
    './source',
  ]) {
    const markup = renderToStaticMarkup(
      <ImportHelp repositoryLocation={repositoryLocation} />,
    )
    expect(markup).toContain('This saved location is')
    expect(markup).toContain('open it from All repositories')
    expect(markup).toContain(
      renderToStaticMarkup(
        <code>{indexCommand('/path/to/local/checkout')}</code>,
      ),
    )
    expect(markup).not.toContain(repositoryLocation)
  }
})
