import { expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { Button } from './button'
import { Badge } from './badge'

test('button keeps native props, handlers, variants and focus/disabled styling', () => {
  const onClick = () => {}
  const element = Button({
    children: 'Refresh',
    type: 'button',
    disabled: true,
    'aria-label': 'Refresh graph',
    variant: 'outline',
    size: 'sm',
    className: 'custom-button',
    onClick,
  })
  expect(element.type).toBe('button')
  expect(element.props.onClick).toBe(onClick)
  const html = renderToStaticMarkup(element)
  for (const attribute of [
    'type="button"',
    'disabled=""',
    'aria-label="Refresh graph"',
    'data-slot="button"',
    'data-variant="outline"',
    'data-size="sm"',
    'custom-button',
    'focus-visible:ring-[3px]',
    'disabled:pointer-events-none',
    '>Refresh</button>',
  ])
    expect(html).toContain(attribute)
})

test('badge keeps native attributes, children and variant styling', () => {
  const element = Badge({
    children: 'Ready',
    title: 'Indexed snapshot',
    variant: 'secondary',
    className: 'custom-badge',
  })
  expect(element.type).toBe('span')
  const html = renderToStaticMarkup(element)
  for (const attribute of [
    'title="Indexed snapshot"',
    'data-slot="badge"',
    'data-variant="secondary"',
    'bg-secondary',
    'custom-badge',
    '>Ready</span>',
  ])
    expect(html).toContain(attribute)
})
