import { describe, expect, test } from 'bun:test'
import { parseArtifact } from './architecture-artifact'
import { largeArtifact } from './imported-artifact-fixture'
import type { Artifact, ArtifactNode } from './architecture-artifact'

function fixture(): Artifact {
  const root: ArtifactNode = {
    stableKey: 'repository',
    type: 'repository',
    kind: 'repository',
    level: 'repository',
    name: 'example',
    path: '.',
    language: null,
    parentStableKey: null,
    ancestorStableKeys: [],
    depth: 0,
  }
  const file: ArtifactNode = {
    ...root,
    stableKey: 'file:main.ts',
    type: 'file',
    kind: 'file',
    level: 'file',
    name: 'main.ts',
    path: 'main.ts',
    language: 'typescript',
    parentStableKey: root.stableKey,
    ancestorStableKeys: [root.stableKey],
    depth: 1,
  }
  return {
    schemaVersion: 2,
    repository: { name: 'example' },
    nodes: [root, file],
    edges: [
      {
        sourceStableKey: root.stableKey,
        targetStableKey: file.stableKey,
        type: 'CONTAINS',
        confidence: 'EXTRACTED',
      },
    ],
    views: { future: { opaque: true } },
    diagnostics: [{ message: 'kept' }],
    stats: { nodes: 2 },
    metadata: { revision: 'abc' },
    custom: { retained: true },
  }
}

test('preserves cycle analysis and rejects malformed cycle metadata', () => {
  const value = fixture()
  const key = 'file:main.ts'
  const edge = {
    sourceStableKey: key,
    targetStableKey: key,
    type: 'IMPORTS',
    confidence: 'EXTRACTED' as const,
  }
  value.edges.push(edge)
  value.circularDependencies = {
    version: 1,
    groups: [
      {
        id: 'self',
        nodeStableKeys: [key],
        exampleCycle: [key, key],
        edges: [edge],
      },
    ],
  }
  expect(parseArtifact(value)).toBe(value)
  for (const mutate of [
    (copy: Artifact) => {
      copy.circularDependencies!.groups[0].nodeStableKeys = ['missing']
    },
    (copy: Artifact) => {
      copy.circularDependencies!.groups[0].exampleCycle = [key, 'repository']
    },
    (copy: Artifact) => {
      copy.circularDependencies!.groups[0].edges[0].type = 'CALLS'
    },
    (copy: Artifact) => {
      copy.circularDependencies!.groups.push(
        copy.circularDependencies!.groups[0],
      )
    },
  ]) {
    const copy = structuredClone(value)
    mutate(copy)
    expect(() => parseArtifact(copy)).toThrow('circularDependencies')
  }
})

function rejectMutation(mutate: (value: Artifact) => void, message: string) {
  const value = fixture()
  mutate(value)
  expect(() => parseArtifact(value)).toThrow(message)
}

test('parses every node and edge in a large JSON artifact, preserving the whole artifact', () => {
  const raw: unknown = JSON.parse(JSON.stringify(largeArtifact()))
  const artifact = parseArtifact(raw)
  expect(raw).toBe(artifact)
  expect(artifact.nodes.length).toBeGreaterThan(1800)
  expect(artifact.edges.length).toBeGreaterThan(6000)
  expect(artifact.nodes).toHaveLength(2022)
  expect(artifact.edges).toHaveLength(8421)
  expect(artifact.views).toEqual({ fixture: { preserved: true } })
  expect(artifact.stats).toEqual({ nodes: 2022, edges: 8421 })
  expect(artifact.diagnostics).toEqual([])
})

test('preserves opaque reporting fields and accepts minimal/empty imports', () => {
  const value = fixture()
  expect(parseArtifact(value)).toBe(value)
  expect(parseArtifact(value).metadata).toEqual({ revision: 'abc' })
  const minimal: Artifact = {
    schemaVersion: 2,
    repository: { name: 'empty' },
    nodes: [],
    edges: [],
  }
  expect(parseArtifact(minimal)).toBe(minimal)
})

test('rejects sparse arrays instead of silently skipping invalid entries', () => {
  rejectMutation((artifact) => {
    artifact.nodes.length++
  }, 'nodes[2] must be an object')
  rejectMutation((artifact) => {
    artifact.edges.length++
  }, 'edges[1] must be an object')
  rejectMutation((artifact) => {
    Reflect.deleteProperty(artifact.nodes[1].ancestorStableKeys, 0)
  }, 'ancestorStableKeys')
  rejectMutation((artifact) => {
    artifact.repository.languages = new Array<string>(1)
  }, 'repository.languages')
})

function registerInvalidEnvelope(key: string) {
  for (const value of [undefined, null, {}, 'array']) {
    test(`rejects ${key} ${JSON.stringify(value)}`, () => {
      expect(() => parseArtifact({ ...fixture(), [key]: value })).toThrow(
        `${key} must be an array`,
      )
    })
  }
}

function registerInvalidFields(
  key: string,
  values: Array<unknown>,
  collection: 'nodes' | 'edges',
  index: number,
) {
  for (const value of values) {
    test(`rejects ${key} ${JSON.stringify(value)}`, () => {
      rejectMutation((artifact) => {
        Object.assign(artifact[collection][index], { [key]: value })
      }, `${collection}[${index}].${key}`)
    })
  }
}

describe('malformed import envelopes', () => {
  for (const value of [null, undefined, [], 'json', 2]) {
    test(`rejects non-object ${JSON.stringify(value)}`, () => {
      expect(() => parseArtifact(value)).toThrow('document must be an object')
    })
  }
  for (const version of [undefined, null, '2', 1, 3]) {
    test(`rejects schemaVersion ${version}`, () => {
      expect(() =>
        parseArtifact({ ...fixture(), schemaVersion: version }),
      ).toThrow('schemaVersion must be 2')
    })
  }
  for (const repository of [
    undefined,
    null,
    [],
    {},
    { name: 4 },
    { name: ' ' },
  ]) {
    test(`rejects repository ${JSON.stringify(repository)}`, () => {
      expect(() => parseArtifact({ ...fixture(), repository })).toThrow(
        'repository',
      )
    })
  }
  for (const key of ['nodes', 'edges']) registerInvalidEnvelope(key)
  for (const [key, value] of [
    ['path', 1],
    ['indexedAt', null],
    ['languages', 'typescript'],
    ['languages', [1]],
  ]) {
    test(`validates repository.${key} ${JSON.stringify(value)}`, () => {
      rejectMutation((artifact) => {
        Object.assign(artifact.repository, { [key as string]: value })
      }, `repository.${key}`)
    })
  }
})

describe('node fields', () => {
  for (const key of [
    'stableKey',
    'type',
    'kind',
    'level',
    'name',
    'path',
    'language',
    'parentStableKey',
    'ancestorStableKeys',
    'depth',
  ]) {
    test(`requires ${key}`, () => {
      rejectMutation((artifact) => {
        Reflect.deleteProperty(artifact.nodes[1], key)
      }, `nodes[1].${key}`)
    })
  }
  for (const [key, values] of Object.entries({
    stableKey: ['', ' ', 3],
    type: ['', null],
    kind: ['', {}],
    level: ['', false],
    name: [null, 1],
    path: [3, []],
    language: [false],
    parentStableKey: ['', 1],
    ancestorStableKeys: [null, 'repository', [3]],
    depth: [-1, 0.5, NaN, Infinity, '1'],
    qualifiedName: [3, null],
    signature: [3],
    properties: [null, []],
    startLine: [0, -1, 0.5, '1', NaN],
    endLine: [0],
    startColumn: [-1],
    endColumn: [Infinity],
  })) {
    registerInvalidFields(key, values, 'nodes', 1)
  }
  test('rejects null nodes and duplicate keys', () => {
    rejectMutation((artifact) => {
      Object.assign(artifact.nodes, { 0: null })
    }, 'nodes[0] must be an object')
    rejectMutation((artifact) => {
      artifact.nodes.push({ ...artifact.nodes[1] })
    }, 'duplicates key "file:main.ts"')
  })
  test('validates source ranges, allowing absent/null positions and zero-based columns', () => {
    rejectMutation((artifact) => {
      Object.assign(artifact.nodes[1], { startLine: 4, endLine: 2 })
    }, 'endLine must not precede')
    rejectMutation((artifact) => {
      Object.assign(artifact.nodes[1], {
        startLine: 4,
        endLine: 4,
        startColumn: 2,
        endColumn: 1,
      })
    }, 'endColumn must not precede')
    const artifact = fixture()
    Object.assign(artifact.nodes[1], {
      startLine: null,
      endLine: null,
      startColumn: 0,
      signature: null,
    })
    expect(parseArtifact(artifact)).toBe(artifact)
  })
})

describe('hierarchy integrity', () => {
  test('rejects dangling parents and self/multi-node cycles', () => {
    rejectMutation((artifact) => {
      artifact.nodes[1].parentStableKey = 'missing'
    }, 'references missing node "missing"')
    rejectMutation((artifact) => {
      artifact.nodes[1].parentStableKey = artifact.nodes[1].stableKey
    }, 'parent cycle')
    rejectMutation((artifact) => {
      artifact.nodes[0].parentStableKey = artifact.nodes[1].stableKey
    }, 'parent cycle')
  })
  test('rejects inconsistent ancestor references and depths', () => {
    for (const ancestors of [
      [],
      ['missing'],
      ['file:main.ts'],
      ['repository', 'repository'],
    ]) {
      rejectMutation((artifact) => {
        artifact.nodes[1].ancestorStableKeys = ancestors
      }, 'ancestorStableKeys must match')
    }
    rejectMutation((artifact) => {
      artifact.nodes[1].depth = 2
    }, 'depth must match')
  })
  test('accepts unsorted node arrays and prototype-like stable keys', () => {
    const artifact = fixture()
    artifact.nodes[0].stableKey = '__proto__'
    artifact.nodes[1].parentStableKey = '__proto__'
    artifact.nodes[1].ancestorStableKeys = ['__proto__']
    artifact.edges[0].sourceStableKey = '__proto__'
    artifact.nodes.reverse()
    expect(parseArtifact(artifact)).toBe(artifact)
  })
})

describe('direct edges', () => {
  for (const key of [
    'sourceStableKey',
    'targetStableKey',
    'type',
    'confidence',
  ]) {
    test(`requires ${key}`, () => {
      rejectMutation((artifact) => {
        Reflect.deleteProperty(artifact.edges[0], key)
      }, `edges[0].${key}`)
    })
  }
  for (const [key, values] of Object.entries({
    sourceStableKey: [null, 2, '', 'missing'],
    targetStableKey: [[], '', 'missing'],
    type: [null, 3, ' '],
    confidence: ['unknown', 1, null],
    path: [3],
    evidence: [{}],
    line: [-1, 0, 0.5, '1', Infinity],
    sourceType: [1],
    sourceKind: [false],
    sourceLevel: [[]],
    targetType: [null],
    targetKind: [3],
    targetLevel: [''],
  })) {
    registerInvalidFields(key, values, 'edges', 0)
  }
  test('rejects non-object edges but permits repeated observations', () => {
    rejectMutation((artifact) => {
      Object.assign(artifact.edges, { 0: [] })
    }, 'edges[0] must be an object')
    const artifact = fixture()
    artifact.edges.push({
      ...artifact.edges[0],
      confidence: 'INFERRED',
      path: null,
      line: null,
      evidence: null,
    })
    expect(parseArtifact(artifact)).toBe(artifact)
  })
})
