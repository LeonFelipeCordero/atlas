import { expect, test } from 'bun:test'
import { getGraphEdgeHandles } from './graph-edge-routing'

 test.each([
  [
    'forward left',
    { x: 100, y: 0 },
    { x: 0, y: 200 },
    'source-bottom',
    'target-top',
  ],
  [
    'forward aligned',
    { x: 0, y: 0 },
    { x: 0, y: 200 },
    'source-bottom',
    'target-top',
  ],
  [
    'forward right',
    { x: 0, y: 0 },
    { x: 100, y: 200 },
    'source-bottom',
    'target-top',
  ],
  [
    'back left',
    { x: 100, y: 200 },
    { x: 0, y: 0 },
    'source-bottom',
    'target-left',
  ],
  [
    'back aligned',
    { x: 0, y: 200 },
    { x: 0, y: 0 },
    'source-bottom',
    'target-left',
  ],
  [
    'back right',
    { x: 0, y: 200 },
    { x: 100, y: 0 },
    'source-right',
    'target-top',
  ],
  [
    'same row left',
    { x: 100, y: 0 },
    { x: 0, y: 0 },
    'source-bottom',
    'target-left',
  ],
  [
    'same row right',
    { x: 0, y: 0 },
    { x: 100, y: 0 },
    'source-right',
    'target-left',
  ],
  ['self loop', { x: 0, y: 0 }, { x: 0, y: 0 }, 'source-bottom', 'target-left'],
  ['missing source', undefined, { x: 0, y: 0 }, 'source-bottom', 'target-top'],
  ['missing target', { x: 0, y: 0 }, undefined, 'source-bottom', 'target-top'],
] as const)(
  'routes top-to-bottom dependencies: %s',
  (_, source, target, sourceHandle, targetHandle) => {
    expect(getGraphEdgeHandles(source, target)).toEqual({
      sourceHandle,
      targetHandle,
    })
  },
)
