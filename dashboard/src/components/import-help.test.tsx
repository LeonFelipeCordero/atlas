import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { ImportHelp } from './import-help'
import { indexCommand } from '@/lib/api'

test('index instructions render the registered name as a literal shell argument', () => {
  for (const repositoryName of [
    "Engineer's École $app",
    '$(exit 12) `exit 13` "$HOME"; exit 14',
    'line one\nline two',
    '--project',
  ]) {
    const markup = renderToStaticMarkup(
      <ImportHelp repositoryName={repositoryName} />,
    )
    expect(markup).toContain(
      renderToStaticMarkup(<code>{indexCommand(repositoryName)}</code>),
    )
    expect(markup).toContain('aria-label="Copy index command"')
  }
})
