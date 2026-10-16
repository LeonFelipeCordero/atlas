import { expect, test } from 'bun:test'
import { compareKeys } from '../src/lib/graph-analysis'

test('stable keys use code-point order with equal and prefix boundaries', () => {
  expect(compareKeys('', '')).toBe(0)
  expect(compareKeys('same', 'same')).toBe(0)
  expect(compareKeys('', 'a')).toBeLessThan(0)
  expect(compareKeys('a', '')).toBeGreaterThan(0)
  expect(compareKeys('ab', 'abc')).toBeLessThan(0)
  expect(compareKeys('abc', 'ab')).toBeGreaterThan(0)
  expect(compareKeys('a', 'z')).toBeLessThan(0)
  expect(compareKeys('z', 'a')).toBeGreaterThan(0)
  expect(compareKeys('\uE000', '😀')).toBeLessThan(0)
  expect(['😀', 'a', '\uE000', 'ab', ''].sort(compareKeys)).toEqual([
    '',
    'a',
    'ab',
    '\uE000',
    '😀',
  ])
})
