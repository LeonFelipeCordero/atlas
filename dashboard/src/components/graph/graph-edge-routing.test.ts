import { expect, test } from 'bun:test'
import { getGraphEdgeHandles } from './graph-edge-routing'

test.each([
  [
    'forward above',
    { x: 0, y: 100 },
    { x: 200, y: 0 },
    'source-right',
    'target-left',
  ],
  [
    'forward level',
    { x: 0, y: 0 },
    { x: 200, y: 0 },
    'source-right',
    'target-left',
  ],
  [
    'forward below',
    { x: 0, y: 0 },
    { x: 200, y: 100 },
    'source-right',
    'target-left',
  ],
  [
    'back above',
    { x: 200, y: 100 },
    { x: 0, y: 0 },
    'source-right',
    'target-top',
  ],
  [
    'back level',
    { x: 200, y: 0 },
    { x: 0, y: 0 },
    'source-right',
    'target-top',
  ],
  [
    'back below',
    { x: 200, y: 0 },
    { x: 0, y: 100 },
    'source-bottom',
    'target-left',
  ],
  [
    'same column above',
    { x: 0, y: 100 },
    { x: 0, y: 0 },
    'source-right',
    'target-top',
  ],
  [
    'same column below',
    { x: 0, y: 0 },
    { x: 0, y: 100 },
    'source-bottom',
    'target-top',
  ],
  ['self loop', { x: 0, y: 0 }, { x: 0, y: 0 }, 'source-right', 'target-top'],
  ['missing source', undefined, { x: 0, y: 0 }, 'source-right', 'target-left'],
  ['missing target', { x: 0, y: 0 }, undefined, 'source-right', 'target-left'],
] as const)(
  'preserves historical routing: %s',
  (_, source, target, sourceHandle, targetHandle) => {
    expect(getGraphEdgeHandles(source, target)).toEqual({
      sourceHandle,
      targetHandle,
    })
  },
)
