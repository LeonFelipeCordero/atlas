import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { GraphNavigation } from '../src/components/graph/graph-navigation'
import type { GraphTrail } from '../src/components/graph/graph-navigation'

const trail: Array<GraphTrail> = [
  { label: 'Repository', scope: { kind: 'repository' } },
  { label: 'Source', scope: { kind: 'folder', key: 'src' } },
  { label: 'File', scope: { kind: 'file', key: 'file' } },
]

test('breadcrumbs separate ancestors and mark only the current scope', () => {
  const navigation = GraphNavigation({ trail, navigate: () => {} })
  expect(
    navigation.props.children.map((child: { key: string }) => child.key),
  ).toEqual(['root', 'src', 'file'])
  const html = renderToStaticMarkup(navigation)
  expect(html.match(/lucide-chevron-right/g)).toHaveLength(2)
  expect(html).toContain('<button aria-current="location">File</button>')
  expect(html).toContain('<button>Repository</button>')
  expect(html).toContain('<button>Source</button>')
  const single = renderToStaticMarkup(
    <GraphNavigation trail={trail.slice(0, 1)} navigate={() => {}} />,
  )
  expect(single).not.toContain('lucide-chevron-right')
  expect(single).toContain(
    '<button aria-current="location">Repository</button>',
  )
})
