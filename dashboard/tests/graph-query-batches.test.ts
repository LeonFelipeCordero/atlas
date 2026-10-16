import { expect, test } from 'bun:test'
import { selectedRows } from '../src/lib/persistence/repositories/graph-queries'

test('selected rows skip empty reads and bound complete key batches at 500 parameters', () => {
  const emptyCalls: Array<Array<string>> = []
  expect(
    selectedRows([], (batch) => {
      emptyCalls.push(batch)
      return []
    }),
  ).toEqual([])
  expect(emptyCalls).toEqual([])
  for (const size of [1, 499, 500, 501, 1000, 1001]) {
    const keys = Array.from({ length: size }, (_, index) => `key:${index}`)
    const batches: Array<Array<string>> = []
    const result = selectedRows(keys, (batch) => {
      expect(batches.length).toBeLessThan(Math.ceil(size / 500))
      batches.push(batch)
      return batch.map((key) => ({ key }))
    })
    expect(result).toEqual(keys.map((key) => ({ key })))
    expect(batches).toHaveLength(Math.ceil(size / 500))
    expect(batches.flat()).toEqual(keys)
    expect(
      batches.every((batch) => batch.length > 0 && batch.length <= 500),
    ).toBe(true)
  }
})
